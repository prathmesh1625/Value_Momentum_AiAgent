"""Validation Agent: checks completeness against guideline section 6 (pure rules, no LLM)."""
from __future__ import annotations

from datetime import date

from app.schemas import ExtractedSubmission, ValidationIssue

REQUIRED = {  # guideline 6.1
    "insured_name": "Insured legal name",
    "business_description": "Business description",
    "annual_revenue": "Annual revenue",
    "building_value": "Building value",
    "contents_value": "Contents value",
    "construction_type": "Construction type",
    "year_built": "Year built",
    "effective_date": "Requested effective date",
}


def check(sub: ExtractedSubmission, doc_types: list[str], today: date | None = None) -> list[ValidationIssue]:
    today = today or date.today()
    issues: list[ValidationIssue] = []
    for field, label in REQUIRED.items():
        if getattr(sub, field) in (None, ""):
            issues.append(ValidationIssue(field=field, severity="blocking", message=f"{label} is missing (rule 6.1)"))
    loc = sub.location_address
    if not loc or not (loc.street and loc.state):
        issues.append(ValidationIssue(field="location_address", severity="blocking",
                                      message="Location address is missing or incomplete (rule 6.1)"))
    if not sub.lines_requested:
        issues.append(ValidationIssue(field="lines_requested", severity="blocking",
                                      message="Lines of coverage requested are missing (rule 6.1)"))
    if "loss_run" not in doc_types:
        issues.append(ValidationIssue(field="loss_runs", severity="blocking",
                                      message="5-year loss runs not attached (rule 6.2)"))
    if sub.effective_date:
        try:
            days = (date.fromisoformat(sub.effective_date) - today).days
            if days < 7:
                issues.append(ValidationIssue(field="effective_date", severity="warning",
                                              message=f"Effective date is only {days} day(s) away; minimum is 7 (rule 6.3)"))
        except ValueError:
            issues.append(ValidationIssue(field="effective_date", severity="warning",
                                          message=f"Could not read effective date '{sub.effective_date}'"))
    for c in sub.data_conflicts:
        issues.append(ValidationIssue(field="conflict", severity="warning",
                                      message=f"Email and documents disagree - confirm with broker: {c}"))
    if sub.sprinklered is None:
        issues.append(ValidationIssue(field="sprinklered", severity="warning",
                                      message="Sprinkler status not stated (needed for rule 3.3)"))
    return issues
