"""The LangGraph workflow.

intake -> validation -> clearance --(duplicate)--> triage
                                  \\--(clear)----> enrichment -> appetite -> triage
triage -> human_review (pauses with interrupt) -> finalize -> END

State is checkpointed in SQLite, so a run can pause for the underwriter and resume later,
even from a different process (CLI or Streamlit).
"""
from __future__ import annotations

import operator
import sqlite3
import uuid
from pathlib import Path
from typing import Annotated, Any, Optional, TypedDict

import requests
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app import audit, config
from app.agents import appetite, clearance, communications, enrichment, intake, triage, validation
from app.documents import load_submission
from app.schemas import (AppetiteResult, ClearanceResult, Enrichment, ExtractedSubmission,
                         ValidationIssue)


class State(TypedDict, total=False):
    run_id: str
    submission_dir: str
    email: str
    documents: list[dict]
    extracted: dict
    validation_issues: list[dict]
    clearance: dict
    enrichment: Optional[dict]
    appetite: Optional[dict]
    preferred_class: bool
    triage: dict
    human_decision: dict
    outcome: dict
    audit_log: Annotated[list[dict], operator.add]


def _sub(state: State) -> ExtractedSubmission:
    return ExtractedSubmission.model_validate(state["extracted"])


def node_intake(state: State) -> dict:
    email, docs = load_submission(Path(state["submission_dir"]))
    sub = intake.run(email, docs)
    log = audit.event(state["run_id"], "IntakeAgent", "extracted",
                      {"documents": [f"{d['name']}:{d['type']}" for d in docs], "insured": sub.insured_name})
    return {"email": email, "documents": docs, "extracted": sub.model_dump(), "audit_log": [log]}


def node_validation(state: State) -> dict:
    issues = validation.check(_sub(state), [d["type"] for d in state["documents"]])
    log = audit.event(state["run_id"], "ValidationAgent", "checked",
                      {"blocking": sum(i.severity == "blocking" for i in issues), "warnings": sum(i.severity == "warning" for i in issues)})
    return {"validation_issues": [i.model_dump() for i in issues], "audit_log": [log]}


def node_clearance(state: State) -> dict:
    res = clearance.check(_sub(state))
    log = audit.event(state["run_id"], "ClearanceAgent", res.status, res.model_dump())
    return {"clearance": res.model_dump(), "audit_log": [log]}


def route_after_clearance(state: State) -> str:
    # Don't spend enrichment calls or underwriting time on a likely duplicate.
    return "triage" if state["clearance"]["status"] == "possible_duplicate" else "enrichment"


def node_enrichment(state: State) -> dict:
    enr = enrichment.run(_sub(state))
    log = audit.event(state["run_id"], "EnrichmentAgent", "enriched", enr.model_dump())
    return {"enrichment": enr.model_dump(), "audit_log": [log]}


def node_appetite(state: State) -> dict:
    has_loss_run = any(d["type"] == "loss_run" for d in state["documents"])
    res, preferred = appetite.run(_sub(state), Enrichment.model_validate(state["enrichment"]), has_loss_run)
    log = audit.event(state["run_id"], "AppetiteAgent", res.decision,
                      {"cited": res.cited_sections, "explanation": res.explanation})
    return {"appetite": res.model_dump(), "preferred_class": preferred, "audit_log": [log]}


def node_triage(state: State) -> dict:
    app_res = AppetiteResult.model_validate(state["appetite"]) if state.get("appetite") else None
    enr = Enrichment.model_validate(state["enrichment"]) if state.get("enrichment") else None
    res = triage.run(_sub(state), [ValidationIssue.model_validate(i) for i in state["validation_issues"]],
                     ClearanceResult.model_validate(state["clearance"]), app_res, enr,
                     state.get("preferred_class", False))
    log = audit.event(state["run_id"], "TriageAgent", res.priority, {"score": res.score, "breakdown": res.score_breakdown})
    return {"triage": res.model_dump(), "audit_log": [log]}


def node_human_review(state: State) -> dict:
    # Pauses the graph. The UI/CLI resumes it with Command(resume={...}).
    decision = interrupt({
        "question": "Underwriter decision required",
        "options": ["approve", "request_info", "decline"],
        "priority": state["triage"]["priority"],
    })
    log = audit.event(state["run_id"], f"Underwriter:{decision.get('underwriter', 'unknown')}",
                      f"decision:{decision['action']}", {"notes": decision.get("notes", "")})
    return {"human_decision": decision, "audit_log": [log]}


def push_to_policycenter(sub: ExtractedSubmission, state: State) -> dict:
    payload = {
        "account": {"name": sub.insured_name, "address": sub.location_address.model_dump() if sub.location_address else None,
                    "naics": sub.naics_code, "annualRevenue": sub.annual_revenue},
        "producer": {"name": sub.broker_name, "email": sub.broker_email},
        "lines": sub.lines_requested,
        "effectiveDate": sub.effective_date,
        "triage": {"priority": state["triage"]["priority"], "score": state["triage"]["score"]},
        "appetite": (state.get("appetite") or {}).get("decision"),
        "sourceRunId": state["run_id"],
    }
    if config.POLICYCENTER_URL == "embedded":
        # Free hosts run one service, so the mock API runs in-process. It is still a real
        # HTTP request through FastAPI's routing and validation, just without a network hop.
        from fastapi.testclient import TestClient

        from mock_policycenter.api import app as policycenter_app
        r = TestClient(policycenter_app).post("/api/v1/submissions", json=payload)
    else:
        r = requests.post(f"{config.POLICYCENTER_URL}/api/v1/submissions", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def node_finalize(state: State) -> dict:
    sub = _sub(state)
    d = state["human_decision"]
    action, notes = d["action"], d.get("notes", "")
    outcome: dict[str, Any] = {"action": action}
    if action == "approve":
        try:
            outcome["policycenter"] = push_to_policycenter(sub, state)
        except Exception as e:  # requests or httpx (embedded mode) errors
            outcome["error"] = f"PolicyCenter API unavailable: {e}. Start it with: uvicorn mock_policycenter.api:app --port 8001"
    elif action == "request_info":
        outcome["email_draft"] = communications.request_info(sub.broker_name, sub.insured_name,
                                                             state["validation_issues"], notes)
    else:
        reason = (state.get("appetite") or {}).get("explanation") or state["clearance"].get("note", "")
        outcome["email_draft"] = communications.decline(sub.broker_name, sub.insured_name, reason, notes)
    log = audit.event(state["run_id"], "System", f"finalized:{action}",
                      {k: v for k, v in outcome.items() if k != "email_draft"})
    return {"outcome": outcome, "audit_log": [log]}


def build_graph():
    g = StateGraph(State)
    g.add_node("intake", node_intake)
    g.add_node("validation", node_validation)
    g.add_node("clearance", node_clearance)
    g.add_node("enrichment", node_enrichment)
    g.add_node("appetite", node_appetite)
    g.add_node("triage", node_triage)
    g.add_node("human_review", node_human_review)
    g.add_node("finalize", node_finalize)
    g.add_edge(START, "intake")
    g.add_edge("intake", "validation")
    g.add_edge("validation", "clearance")
    g.add_conditional_edges("clearance", route_after_clearance, {"triage": "triage", "enrichment": "enrichment"})
    g.add_edge("enrichment", "appetite")
    g.add_edge("appetite", "triage")
    g.add_edge("triage", "human_review")
    g.add_edge("human_review", "finalize")
    g.add_edge("finalize", END)
    conn = sqlite3.connect(config.CHECKPOINT_DB, check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))


def start(graph, submission_dir: str | Path) -> tuple[str, dict]:
    """Run until the human-review pause. Returns (run_id, state)."""
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    cfg = {"configurable": {"thread_id": run_id}}
    graph.invoke({"run_id": run_id, "submission_dir": str(submission_dir), "audit_log": []}, cfg)
    return run_id, graph.get_state(cfg).values


def resume(graph, run_id: str, action: str, notes: str = "", underwriter: str = "demo-uw") -> dict:
    cfg = {"configurable": {"thread_id": run_id}}
    graph.invoke(Command(resume={"action": action, "notes": notes, "underwriter": underwriter}), cfg)
    return graph.get_state(cfg).values
