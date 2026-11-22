"""Triage Agent: scores the submission and writes the underwriter's one-page brief.

The score is a transparent formula (every point is explained in `score_breakdown`), and the
LLM only writes the narrative. Underwriters trust numbers they can check.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app import llm
from app.schemas import (AppetiteResult, ClearanceResult, Enrichment, ExtractedSubmission,
                         TriageResult, ValidationIssue)


def score(sub: ExtractedSubmission, issues: list[ValidationIssue], clearance: ClearanceResult,
          appetite: AppetiteResult | None, enr: Enrichment | None, preferred: bool,
          today: date | None = None) -> tuple[str, int, dict[str, int]]:
    today = today or date.today()
    b: dict[str, int] = {"base": 50}
    if appetite is not None:
        b["appetite"] = {"in_appetite": 20, "refer": 0, "out_of_appetite": -50}[appetite.decision]
    blocking = sum(1 for i in issues if i.severity == "blocking")
    if blocking:
        b["missing_info"] = -min(30, 10 * blocking)
    n = len(sub.prior_losses)
    if any(i.field == "loss_runs" for i in issues):
        b["loss_history"] = 0  # unknown: no loss runs, so "no losses" proves nothing
    else:
        b["loss_history"] = 15 if n == 0 else 5 if n <= 2 else -10
    if preferred:
        b["preferred_class"] = 10
    if sub.effective_date:
        try:
            days = (date.fromisoformat(sub.effective_date) - today).days
            if 7 <= days <= 30:
                b["effective_soon"] = 10  # guideline 7.2: likely to bind
        except ValueError:
            pass
    if enr and "high" in enr.hazards.values():
        b["cat_exposure"] = -10
    if clearance.status == "possible_duplicate":
        b["clearance_hold"] = -40
    total = max(0, min(100, sum(b.values())))
    if appetite is not None and appetite.decision == "out_of_appetite":
        priority = "decline"
    elif total >= 75:
        priority = "P1-hot"
    elif total >= 50:
        priority = "P2-standard"
    else:
        priority = "P3-low"
    return priority, total, b


class Narrative(BaseModel):
    underwriter_summary: str = Field(description="5-8 short bullet lines (each starting with '- ') an underwriter can read in 30 seconds")
    recommended_action: str = Field(description="One sentence starting with one of: 'Quote', 'Refer to senior underwriter', "
                                                "'Request information', 'Hold for clearance', 'Decline'. Never say bind.")


SYSTEM = """You write briefs for commercial insurance underwriters. Be factual and concise. Use only
the facts given. Mention the business, values, loss history, appetite flags (with rule ids),
missing information and clearance status. Do not invent numbers. If a validation issue says loss
runs are missing, write "loss history unknown (no loss runs)" - never "no prior losses"."""


def run(sub, issues, clearance, appetite, enr, preferred) -> TriageResult:
    priority, total, breakdown = score(sub, issues, clearance, appetite, enr, preferred)
    facts = {
        "submission": sub.model_dump(exclude_none=True),
        "validation_issues": [i.model_dump() for i in issues],
        "clearance": clearance.model_dump(),
        "appetite": appetite.model_dump() if appetite else "skipped (clearance hold)",
        "hazards": enr.hazards if enr else "skipped",
        "priority": priority,
        "score": total,
        "score_breakdown": breakdown,
    }
    n = llm.structured(Narrative, SYSTEM, f"Facts (JSON):\n{facts}")
    return TriageResult(priority=priority, score=total, score_breakdown=breakdown,
                        underwriter_summary=n.underwriter_summary, recommended_action=n.recommended_action)
