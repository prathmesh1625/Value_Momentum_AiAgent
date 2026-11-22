"""Underwriter workbench.  Run:  streamlit run ui/streamlit_app.py"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# On a hosting platform the key comes from its secret store, never from the code.
# This must run before app.config is imported, because config reads the environment.
try:
    for key in ("GROQ_API_KEY", "GROQ_MODEL", "POLICYCENTER_URL", "ENABLE_GEOCODING", "MAX_RUNS_PER_SESSION"):
        if key in st.secrets:
            os.environ.setdefault(key, str(st.secrets[key]))
except Exception:  # no secrets file locally: .env is used instead
    pass

from app import audit, config  # noqa: E402
from app.graph import build_graph, resume, start  # noqa: E402

st.set_page_config(page_title="Submission Triage Agent", layout="wide")
MAX_RUNS = int(os.getenv("MAX_RUNS_PER_SESSION", "10"))  # protects the free LLM quota on a public demo


@st.cache_resource
def refresh_samples() -> bool:
    """Regenerate samples once per server start so effective dates stay relative to today.
    Otherwise S001's date would slip into the past and the demo results would change."""
    spec = importlib.util.spec_from_file_location("generate_samples", ROOT / "scripts" / "generate_samples.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()
    return True


@st.cache_resource
def graph():
    return build_graph()


refresh_samples()


PRIORITY_COLOR = {"P1-hot": "green", "P2-standard": "orange", "P3-low": "gray", "decline": "red"}

st.title("Commercial Submission Intake & Triage")
st.caption("Multi-agent workflow (LangGraph): intake → validation → clearance → enrichment → appetite → triage → underwriter → PolicyCenter")

# ---------- Sidebar: choose input ----------
with st.sidebar:
    st.header("1. Submission")
    mode = st.radio("Source", ["Sample", "Upload"], horizontal=True)
    folder: Path | None = None
    if mode == "Sample":
        samples = sorted(p.name for p in config.SUBMISSIONS_DIR.iterdir() if p.is_dir())
        labels = {s: f"{s} - {json.loads((config.SUBMISSIONS_DIR / s / 'meta.json').read_text())['scenario']}"
                  for s in samples}
        choice = st.selectbox("Sample", samples, format_func=labels.get)
        folder = config.SUBMISSIONS_DIR / choice
        with st.expander("Broker email"):
            st.text((folder / "email.txt").read_text(encoding="utf-8"))
    else:
        email = st.text_area("Paste broker email", height=150)
        pdfs = st.file_uploader("Attachments (PDF)", type="pdf", accept_multiple_files=True)
        if email and pdfs:
            folder = config.RUNTIME_DIR / "uploads" / uuid.uuid4().hex[:8]
            st.session_state["pending_upload"] = (folder, email, [(f.name, f.getvalue()) for f in pdfs])
    runs_used = st.session_state.get("runs_used", 0)
    limit_hit = runs_used >= MAX_RUNS
    run_clicked = st.button("Run agents", type="primary", disabled=folder is None or limit_hit, width="stretch")
    st.caption(f"Runs this session: {runs_used}/{MAX_RUNS}"
               + (" (limit reached: refresh the page later)" if limit_hit else ""))
    st.caption("Demo with fictional data. Please don't upload real personal or customer documents.")

if run_clicked:
    st.session_state["runs_used"] = st.session_state.get("runs_used", 0) + 1
    if mode == "Upload":
        folder, email, files = st.session_state.pop("pending_upload")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "email.txt").write_text(email, encoding="utf-8")
        for name, data in files:
            (folder / Path(name).name).write_bytes(data)
    with st.status("Agents working...", expanded=False) as status:
        try:
            run_id, state = start(graph(), folder)
            st.session_state.update(run_id=run_id, state=state, final=None)
            status.update(label=f"Ready for review: {run_id}", state="complete")
        except Exception as e:  # show the error instead of a blank page
            status.update(label="Run failed", state="error")
            st.exception(e)

state = st.session_state.get("state")
if not state:
    st.info("Pick a submission in the sidebar and click **Run agents**.")
    st.stop()

# ---------- Results ----------
t = state["triage"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Priority", t["priority"])
c2.metric("Score", t["score"])
SHORT = {"in_appetite": "In", "refer": "Refer", "out_of_appetite": "Out", "skipped": "Skipped",
         "clear": "Clear", "possible_duplicate": "Duplicate?"}
c3.metric("Appetite", SHORT[(state.get("appetite") or {}).get("decision", "skipped")])
c4.metric("Clearance", SHORT[state["clearance"]["status"]])

left, right = st.columns([3, 2])
with left:
    st.subheader("Underwriter brief")
    st.markdown(f":{PRIORITY_COLOR[t['priority']]}[**{t['priority']}**] — {t['recommended_action']}")
    st.markdown(t["underwriter_summary"])
    tabs = st.tabs(["Extracted data", "Validation", "Appetite rules", "Enrichment", "Documents"])
    with tabs[0]:
        st.json({k: v for k, v in state["extracted"].items() if v not in (None, [], "")})
    with tabs[1]:
        issues = state["validation_issues"]
        st.dataframe(pd.DataFrame(issues), width="stretch", hide_index=True) if issues else st.success("Complete")
    with tabs[2]:
        if state.get("appetite"):
            st.write(state["appetite"]["explanation"])
            st.dataframe(pd.DataFrame(state["appetite"]["rule_hits"]), width="stretch", hide_index=True)
        else:
            st.warning("Skipped: possible duplicate, held for clearance.")
    with tabs[3]:
        enr = state.get("enrichment")
        if enr:
            st.json(enr)
            if enr.get("latitude"):
                st.map(pd.DataFrame([{"lat": enr["latitude"], "lon": enr["longitude"]}]))
        else:
            st.write("Skipped.")
    with tabs[4]:
        for d in state["documents"]:
            with st.expander(f"{d['name']} ({d['type']})"):
                st.text(d["text"])

with right:
    st.subheader("Score breakdown")
    lines = ["| Factor | Points |", "|---|---:|"]
    lines += [f"| {k.replace('_', ' ').capitalize()} | {v:+d} |" for k, v in t["score_breakdown"].items()]
    lines.append(f"| **Total** (kept within 0-100) | **{t['score']}** |")
    st.markdown("\n".join(lines))
    st.subheader("2. Underwriter decision")
    final = st.session_state.get("final")
    if final is None:
        with st.form("decision"):
            uw = st.text_input("Underwriter", "demo-uw")
            action = st.radio("Action", ["approve", "request_info", "decline"], horizontal=True)
            notes = st.text_area("Notes")
            if st.form_submit_button("Submit decision", type="primary"):
                with st.spinner("Finalizing..."):
                    st.session_state["final"] = resume(graph(), st.session_state["run_id"], action, notes, uw)
                st.rerun()
    else:
        out = final["outcome"]
        if "policycenter" in out:
            st.success(f"Created in PolicyCenter: **{out['policycenter']['submissionNumber']}**")
        if "error" in out:
            st.error(out["error"])
        if "email_draft" in out:
            st.text_area("Email draft to broker (review before sending)", out["email_draft"], height=260)

    st.subheader("Audit trail")
    hist = pd.DataFrame(audit.history(st.session_state["run_id"]))
    if not hist.empty:
        hist["time (UTC)"] = hist["ts"].str[11:19]
        st.dataframe(hist[["time (UTC)", "actor", "event"]], width="stretch", hide_index=True)
        with st.expander("Full audit details"):
            st.dataframe(hist[["ts", "actor", "event", "detail"]], width="stretch", hide_index=True)
