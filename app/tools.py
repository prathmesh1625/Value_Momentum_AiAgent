"""External lookups used by the Risk Enrichment Agent.

- geocode(): real call to OpenStreetMap Nominatim (free, 1 request/second, no key).
- hazard_profile(): MOCK catastrophe data. A real carrier would call a vendor such as a
  flood-zone or wildfire-score API here; the function signature stays the same.
"""
from __future__ import annotations

import requests

from app import config

COASTAL_HURRICANE_CITIES = {"galveston", "corpus christi", "port arthur", "miami", "tampa",
                            "key west", "new orleans", "panama city", "pensacola", "naples"}
HIGH_FLOOD_CITIES = {"galveston", "new orleans", "miami", "key west", "houston"}


def geocode(address: str) -> dict:
    if not config.ENABLE_GEOCODING or not address:
        return {"lat": None, "lon": None, "source": "disabled"}
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": "submission-triage-demo/0.1"},
            timeout=6,
        )
        r.raise_for_status()
        hits = r.json()
        if hits:
            return {"lat": float(hits[0]["lat"]), "lon": float(hits[0]["lon"]), "source": "nominatim"}
        return {"lat": None, "lon": None, "source": "nominatim:not_found"}
    except requests.RequestException as e:
        return {"lat": None, "lon": None, "source": f"error:{type(e).__name__}"}


def hazard_profile(state: str | None, city: str | None) -> dict[str, str]:
    """MOCK hazard scores by state/city. Values: low / moderate / high."""
    st = (state or "").upper()
    c = (city or "").lower()
    hz = {"hurricane": "low", "wildfire": "low", "flood": "low", "hail": "low", "earthquake": "low"}
    if st in {"FL", "LA"} or (st == "TX" and c in COASTAL_HURRICANE_CITIES):
        hz["hurricane"] = "high"
    elif st in {"TX", "MS", "AL", "GA", "SC", "NC"}:
        hz["hurricane"] = "moderate"
    if st == "CA":
        hz["wildfire"], hz["earthquake"] = "high", "high"
    elif st in {"CO", "OR", "NV", "AZ"}:
        hz["wildfire"] = "moderate"
    if c in HIGH_FLOOD_CITIES:
        hz["flood"] = "high"
    if st in {"TX", "CO", "OK", "KS", "NE"}:
        hz["hail"] = "moderate"
    return hz
