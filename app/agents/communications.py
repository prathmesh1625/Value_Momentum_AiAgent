"""Drafts emails to the broker. Drafts only: a human sends them."""
from __future__ import annotations

from app import llm

SYSTEM = """You draft short, professional emails from a commercial underwriter to an insurance broker.
Plain text, under 150 words, with a greeting and sign-off "Underwriting Team". Use only the facts
given. Do not promise coverage or quote prices."""


def request_info(broker: str | None, insured: str | None, issues: list[dict], notes: str) -> str:
    missing = "\n".join(f"- {i['message']}" for i in issues if i["severity"] == "blocking")
    return llm.text(SYSTEM, f"Write to broker {broker or 'there'} about the submission for {insured}. "
                            f"We need these items before we can quote:\n{missing}\n"
                            f"Underwriter notes: {notes or 'none'}")


def decline(broker: str | None, insured: str | None, reason: str, notes: str) -> str:
    return llm.text(SYSTEM, f"Write to broker {broker or 'there'} declining the submission for {insured}. "
                            f"Reason (from our guidelines): {reason}\nUnderwriter notes: {notes or 'none'}")
