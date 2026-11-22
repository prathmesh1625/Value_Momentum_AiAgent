"""Load a submission folder: the broker email plus every attached PDF, as plain text."""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def classify(name: str, text: str) -> str:
    """Rule-based document type. Cheap and predictable, so no LLM call is spent here."""
    t = text.lower()
    if "loss run" in t or "loss history" in t:
        return "loss_run"
    if "application" in t or "acord" in t or "named insured" in t:
        return "application"
    if "statement of values" in t or "sov" in name.lower():
        return "statement_of_values"
    return "other"


def load_submission(folder: Path) -> tuple[str, list[dict]]:
    email_path = folder / "email.txt"
    email = email_path.read_text(encoding="utf-8") if email_path.exists() else ""
    docs = []
    for pdf in sorted(folder.glob("*.pdf")):
        text = pdf_text(pdf)
        docs.append({"name": pdf.name, "type": classify(pdf.name, text), "text": text})
    return email, docs
