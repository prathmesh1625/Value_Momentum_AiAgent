"""Run one submission end to end from the terminal.

    python run_cli.py S001                 # pauses and asks you for the underwriter decision
    python run_cli.py S003 --auto decline  # non-interactive
"""
from __future__ import annotations

import argparse
import json
import sys

from app import config
from app.graph import build_graph, resume, start


def show(title: str, body) -> None:
    print(f"\n=== {title} ===")
    print(body if isinstance(body, str) else json.dumps(body, indent=2, default=str))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("submission", help="Folder name under data/submissions, e.g. S001")
    p.add_argument("--auto", choices=["approve", "request_info", "decline"], help="Skip the prompt")
    p.add_argument("--notes", default="")
    args = p.parse_args()

    folder = config.SUBMISSIONS_DIR / args.submission
    if not folder.exists():
        sys.exit(f"No such submission folder: {folder}")

    graph = build_graph()
    run_id, s = start(graph, folder)
    show("Run", run_id)
    show("Extracted", {k: v for k, v in s["extracted"].items() if v not in (None, [], "")})
    show("Validation issues", s["validation_issues"] or "none")
    show("Clearance", s["clearance"])
    if s.get("enrichment"):
        show("Hazards", s["enrichment"]["hazards"])
    if s.get("appetite"):
        show("Appetite", {"decision": s["appetite"]["decision"], "explanation": s["appetite"]["explanation"]})
    t = s["triage"]
    show(f"Triage: {t['priority']} (score {t['score']})", t["score_breakdown"])
    show("Underwriter brief", t["underwriter_summary"] + "\n\nNext step: " + t["recommended_action"])

    action = args.auto
    while action not in ("approve", "request_info", "decline"):
        action = input("\nDecision [approve / request_info / decline]: ").strip()
    notes = args.notes or ("" if args.auto else input("Notes (optional): ").strip())

    final = resume(graph, run_id, action, notes)
    show("Outcome", final["outcome"].get("policycenter") or final["outcome"].get("error") or "")
    if "email_draft" in final["outcome"]:
        show("Email draft to broker", final["outcome"]["email_draft"])
    show("Audit trail", [f"{e['ts']} {e['actor']}: {e['event']}" for e in final["audit_log"]])


if __name__ == "__main__":
    main()
