"""Measure the agents against the hand-written answer key (data/submissions/*/expected.json).

    python scripts/evaluate.py               # all samples
    python scripts/evaluate.py --only S007 S009

Reports:
  - field accuracy: did the Intake Agent extract each value correctly?
  - hallucinations: did it invent a value that is not in the documents?
  - decision accuracy: appetite, clearance, priority, blocking issues, conflict detection
Writes eval/results.md (for the README) and eval/results.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402
from app.agents.clearance import normalize_name  # noqa: E402
from app.graph import build_graph, start  # noqa: E402

MONEY = {"annual_revenue", "building_value", "contents_value", "loss_total"}
EXACT = {"year_built", "sprinklered", "effective_date", "loss_count"}
FIELDS = ["insured_name", "annual_revenue", "building_value", "contents_value", "construction_type",
          "year_built", "sprinklered", "state", "effective_date", "loss_count", "loss_total"]
DECISIONS = ["appetite", "clearance", "priority", "blocking", "conflict"]


def norm(s: str) -> str:
    return " ".join(s.lower().replace("-", " ").split())


def field_ok(field: str, want, got) -> bool:
    if want is None or got is None:
        return want is None and got is None
    if field in MONEY:
        return abs(float(got) - float(want)) <= 0.005 * max(1.0, float(want))
    if field in EXACT:
        return got == want
    if field == "insured_name":
        return SequenceMatcher(None, normalize_name(want), normalize_name(got)).ratio() >= 0.9
    if field == "state":
        return str(got).upper() == str(want).upper()
    return norm(want) in norm(got) or norm(got) in norm(want)  # construction_type


def actual_values(state: dict) -> dict:
    x = state["extracted"]
    loc = x.get("location_address") or {}
    losses = x.get("prior_losses") or []
    return {
        "insured_name": x.get("insured_name"), "annual_revenue": x.get("annual_revenue"),
        "building_value": x.get("building_value"), "contents_value": x.get("contents_value"),
        "construction_type": x.get("construction_type"), "year_built": x.get("year_built"),
        "sprinklered": x.get("sprinklered"), "state": loc.get("state"), "effective_date": x.get("effective_date"),
        "loss_count": len(losses), "loss_total": sum(l.get("amount_paid") or 0 for l in losses),
        # decisions
        "appetite": (state.get("appetite") or {}).get("decision"),
        "clearance": state["clearance"]["status"],
        "priority": state["triage"]["priority"],
        "blocking": sorted(i["field"] for i in state["validation_issues"] if i["severity"] == "blocking"),
        "conflict": bool(x.get("data_conflicts")),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*")
    p.add_argument("--pause", type=float, default=2.0, help="seconds between samples (free-tier rate limits)")
    args = p.parse_args()

    folders = sorted(f for f in config.SUBMISSIONS_DIR.iterdir() if (f / "expected.json").exists())
    if args.only:
        folders = [f for f in folders if f.name in args.only]
    graph = build_graph()
    rows, field_hits, field_total, halluc, nulls = [], 0, 0, 0, 0
    dec_hits = {d: 0 for d in DECISIONS}

    for i, folder in enumerate(folders):
        if i:
            time.sleep(args.pause)
        want = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
        t0 = time.perf_counter()
        try:
            _, state = start(graph, folder)
        except Exception as e:
            print(f"{folder.name}: FAILED - {e}")
            rows.append({"id": folder.name, "error": str(e)[:200]})
            continue
        secs = time.perf_counter() - t0
        got = actual_values(state)
        wrong = []
        for f in FIELDS:
            ok = field_ok(f, want[f], got[f])
            field_hits += ok
            field_total += 1
            if want[f] is None:
                nulls += 1
                halluc += got[f] is not None
            if not ok:
                wrong.append(f"{f}: want {want[f]!r}, got {got[f]!r}")
        for d in DECISIONS:
            ok = got[d] == want[d]
            dec_hits[d] += ok
            if not ok:
                wrong.append(f"{d}: want {want[d]!r}, got {got[d]!r}")
        rows.append({"id": folder.name, "seconds": round(secs, 1), "wrong": wrong,
                     "fields_ok": sum(field_ok(f, want[f], got[f]) for f in FIELDS)})
        print(f"{folder.name}: {rows[-1]['fields_ok']}/{len(FIELDS)} fields, {secs:.1f}s"
              + ("".join(f"\n    x {w}" for w in wrong) if wrong else "  all correct"))

    done = [r for r in rows if "error" not in r]
    n = len(done)
    summary = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "model": config.GROQ_MODEL,
        "samples": len(rows), "failed_runs": len(rows) - n,
        "field_accuracy": round(field_hits / field_total, 3) if field_total else None,
        "hallucinated_values": f"{halluc}/{nulls}",
        "decision_accuracy": {d: f"{dec_hits[d]}/{n}" for d in DECISIONS},
        "avg_seconds_per_submission": round(sum(r["seconds"] for r in done) / n, 1) if n else None,
    }
    out = ROOT / "eval"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    md = [f"# Evaluation results\n", f"Run {summary['run_at']} with `{summary['model']}` on {len(rows)} labelled submissions.\n",
          "| Metric | Result |", "|---|---|",
          f"| Field extraction accuracy ({len(FIELDS)} fields x {n}) | **{summary['field_accuracy']:.1%}** |" if n else "| Field accuracy | n/a |",
          f"| Invented values where the document had none | {summary['hallucinated_values']} |",
          *[f"| {d.capitalize()} correct | {v} |" for d, v in summary["decision_accuracy"].items()],
          f"| Average time per submission | {summary['avg_seconds_per_submission']}s |",
          f"| Failed runs | {summary['failed_runs']} |", "", "## Errors", ""]
    md += [f"- **{r['id']}**: " + "; ".join(r.get("wrong") or [r.get("error", "")]) for r in rows
           if r.get("wrong") or r.get("error")] or ["None."]
    (out / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n" + json.dumps(summary, indent=2))
    print(f"Wrote {out / 'results.md'}")


if __name__ == "__main__":
    main()
