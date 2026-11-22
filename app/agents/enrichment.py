"""Risk Enrichment Agent: adds outside data the broker did not send (location + hazards)."""
from __future__ import annotations

from app import tools
from app.schemas import Enrichment, ExtractedSubmission


def run(sub: ExtractedSubmission) -> Enrichment:
    loc = sub.location_address
    geo = tools.geocode(loc.one_line() if loc else "")
    hz = tools.hazard_profile(loc.state if loc else None, loc.city if loc else None)
    return Enrichment(latitude=geo["lat"], longitude=geo["lon"], geocode_source=geo["source"],
                      hazards=hz, hazard_source="mock (replace with a CAT data vendor API)")
