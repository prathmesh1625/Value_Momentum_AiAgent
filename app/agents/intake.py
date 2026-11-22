"""Intake Agent: turns a messy broker email + PDFs into a structured submission."""
from __future__ import annotations

from app import llm
from app.schemas import ExtractedSubmission

SYSTEM = """You are an insurance submission intake specialist at a commercial P&C carrier.
Extract the submission into the given schema from the broker email and attached documents.

Rules:
- Copy values exactly as written. Convert money to plain numbers ("$2,400,000" -> 2400000,
  "$4.5M" -> 4500000, "1.2 million" -> 1200000, "700K" -> 700000).
- Forms may use abbreviations: Insd = insured, Bldg = building, BPP = contents, Constr = construction,
  JM = joisted masonry, Sprk = sprinklered (Y/N), LOB = lines of business, Prop = Property.
- If a value is not present anywhere, leave it null. Never guess or invent a value.
- A value given only in the email (not on the application) is still valid: use it.
- If the email and the application disagree on a value, use the APPLICATION value and record the
  disagreement in `data_conflicts`. Only record real disagreements, not missing values.
- Dates must be YYYY-MM-DD.
- `prior_losses` comes only from the loss run. If the loss run says there were no losses, return [].
- `sprinklered` is true for "Yes", false for "No", null if not stated."""


def build_prompt(email: str, docs: list[dict]) -> str:
    parts = [f"=== BROKER EMAIL ===\n{email}"]
    for d in docs:
        parts.append(f"=== ATTACHMENT: {d['name']} (type: {d['type']}) ===\n{d['text']}")
    return "\n\n".join(parts)


def run(email: str, docs: list[dict]) -> ExtractedSubmission:
    return llm.structured(ExtractedSubmission, SYSTEM, build_prompt(email, docs))
