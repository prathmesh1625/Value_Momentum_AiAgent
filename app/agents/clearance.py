"""Clearance Agent: has another broker already submitted this business?

In insurance, the first broker to submit usually "owns" the account. Quoting a duplicate
creates broker conflicts, so this check runs before any underwriting time is spent.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

from app import config
from app.schemas import ClearanceResult, ExtractedSubmission

SUFFIXES = r"\b(inc|llc|ltd|co|corp|corporation|company|pc|the)\b"
ABBREV = {"street": "st", "avenue": "ave", "boulevard": "blvd", "road": "rd", "drive": "dr",
          "west": "w", "east": "e", "north": "n", "south": "s"}


def normalize_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    s = re.sub(SUFFIXES, " ", s)
    return " ".join(s.split())


def normalize_address(addr: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", addr.lower()).split()
    return " ".join(ABBREV.get(w, w) for w in words)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def check(sub: ExtractedSubmission, existing: list[dict] | None = None, threshold: float = 0.85) -> ClearanceResult:
    if existing is None:
        existing = json.loads(config.EXISTING_SUBMISSIONS_PATH.read_text(encoding="utf-8"))
    name = normalize_name(sub.insured_name or "")
    addr = normalize_address(sub.location_address.one_line() if sub.location_address else "")
    best: tuple[float, dict | None] = (0.0, None)
    for ex in existing:
        name_sim = similarity(name, normalize_name(ex["insured_name"]))
        addr_sim = similarity(addr, normalize_address(ex["address"])) if addr else 0.0
        score = 0.6 * name_sim + 0.4 * addr_sim
        if score > best[0]:
            best = (score, ex)
    score, match = best
    if match and score >= threshold:
        return ClearanceResult(status="possible_duplicate", matched_submission_id=match["submission_id"],
                               matched_broker=match["broker"], similarity=round(score, 3),
                               note=f"Matches {match['submission_id']} received {match['received']} from {match['broker']}")
    return ClearanceResult(status="clear", similarity=round(score, 3), note="No matching prior submission")
