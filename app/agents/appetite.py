"""Appetite Agent: "does this carrier want to write this risk?"

Hybrid design:
- Numeric rules (revenue, values, losses, CAT zones) are checked in code. They must be exact
  and explainable, and an LLM should not do arithmetic on money.
- Business-class judgment ("is a fireworks warehouse a prohibited class?") is fuzzy, so the LLM
  decides it, grounded in guideline sections retrieved with RAG, and must cite them.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app import llm, rag
from app.schemas import AppetiteResult, AppetiteRuleHit, Enrichment, ExtractedSubmission

RANK = {"pass": 0, "refer": 1, "decline": 2}


def rule_engine(sub: ExtractedSubmission, enr: Enrichment, today: date | None = None,
                loss_runs_provided: bool = True) -> list[AppetiteRuleHit]:
    today = today or date.today()
    hits: list[AppetiteRuleHit] = []

    def add(rule: str, outcome: str, detail: str) -> None:
        hits.append(AppetiteRuleHit(rule_id=rule, outcome=outcome, detail=detail))

    rev = sub.annual_revenue
    if rev is not None:
        if 250_000 <= rev <= 25_000_000:
            add("1.1", "pass", f"Revenue ${rev:,.0f} is within $250K-$25M")
        else:
            add("1.1", "decline", f"Revenue ${rev:,.0f} is outside $250K-$25M")

    yib = sub.years_in_business
    if yib is not None:
        if yib < 1:
            add("1.3", "decline", f"Only {yib} year(s) in business")
        elif yib < 3:
            add("1.3", "refer", f"New venture: {yib} year(s) in business")

    tiv = (sub.building_value or 0) + (sub.contents_value or 0)
    if tiv:
        if tiv > 15_000_000:
            add("3.1", "decline", f"TIV ${tiv:,.0f} exceeds $15M maximum")
        elif tiv > 10_000_000:
            add("3.1", "refer", f"TIV ${tiv:,.0f} is above $10M")
        else:
            add("3.1", "pass", f"TIV ${tiv:,.0f} is within limits")
        if tiv > 5_000_000 and sub.sprinklered is False:
            add("3.3", "refer", f"Unsprinklered with TIV ${tiv:,.0f} above $5M")

    if sub.construction_type and "frame" in sub.construction_type.lower() and "metal" not in sub.construction_type.lower() \
            and sub.year_built and sub.year_built < 1960:
        add("3.2", "refer", f"Frame building built in {sub.year_built}; needs inspection")

    hz = enr.hazards
    if hz.get("hurricane") == "high":
        add("4.1", "refer", "High hurricane zone: refer, minimum 2% wind deductible")
    if hz.get("wildfire") == "high":
        add("4.2", "refer", "High wildfire zone")
    if hz.get("flood") == "high":
        add("4.3", "refer", "High flood zone: exclude flood, place separately")

    losses = sub.prior_losses
    n = len(losses)
    total = sum(l.amount_paid or 0 for l in losses)
    if n >= 3:
        add("5.1", "refer", f"{n} claims in 5 years")
    if total > 250_000:
        add("5.2", "refer", f"Total paid losses ${total:,.0f} exceed $250K")
    for l in losses:
        if (l.amount_paid or 0) > 500_000:
            add("5.3", "refer", f"Single loss ${l.amount_paid:,.0f} in {l.year}")
        if l.cause and "fire" in l.cause.lower() and l.year and today.year - l.year <= 3:
            add("5.3", "refer", f"Fire loss in {l.year}: needs explanation of fixes")
    if n == 0 and loss_runs_provided:
        add("5.1", "pass", "No losses reported")
    return hits


class ClassJudgment(BaseModel):
    outcome: Literal["pass", "refer", "decline"] = Field(
        description="decline = prohibited class (section 2); refer = needs underwriter judgment; pass = acceptable or preferred class")
    is_preferred_class: bool = Field(description="True if the business matches a preferred class in rule 1.2")
    reason: str = Field(description="One or two sentences, citing rule ids like [2.1]")
    cited_sections: list[str] = Field(description="Rule ids used, e.g. ['1.2', '2.1']")


SYSTEM = """You are a commercial underwriting assistant. Decide whether the applicant's business
CLASS is acceptable under the carrier guidelines provided. Judge only the type of business, not
money amounts or loss history (those are checked elsewhere). Use only the guideline text given,
and cite the rule ids you relied on."""


def judge_class(sub: ExtractedSubmission) -> tuple[ClassJudgment, list[dict]]:
    query = f"{sub.business_description or ''} {sub.insured_name or ''} prohibited preferred classes target market"
    rules = rag.search(query, k=6)
    ids = {r["id"] for r in rules}
    for must in ("1.2", "2.1", "2.2"):  # always show the class lists themselves
        if must not in ids:
            rules += [r for r in rag.load_rules() if r["id"] == must]
    user = (f"Applicant: {sub.insured_name}\nBusiness description: {sub.business_description}\n"
            f"NAICS: {sub.naics_code}\n\nGuidelines:\n{rag.format_rules(rules)}")
    return llm.structured(ClassJudgment, SYSTEM, user), rules


def run(sub: ExtractedSubmission, enr: Enrichment, loss_runs_provided: bool = True) -> tuple[AppetiteResult, bool]:
    hits = rule_engine(sub, enr, loss_runs_provided=loss_runs_provided)
    judgment, _ = judge_class(sub)
    hits.insert(0, AppetiteRuleHit(rule_id="class", outcome=judgment.outcome, detail=judgment.reason))
    worst = max((RANK[h.outcome] for h in hits), default=0)
    decision = {0: "in_appetite", 1: "refer", 2: "out_of_appetite"}[worst]
    flagged = [h for h in hits if h.outcome != "pass"]
    explanation = judgment.reason
    if flagged:
        explanation += " Flags: " + "; ".join(f"[{h.rule_id}] {h.detail}" for h in flagged if h.rule_id != "class")
    cited = sorted({*judgment.cited_sections, *(h.rule_id for h in flagged if h.rule_id != "class")})
    return AppetiteResult(decision=decision, rule_hits=hits, explanation=explanation.strip(),
                          cited_sections=cited), judgment.is_preferred_class
