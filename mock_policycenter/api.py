"""A tiny mock of a policy administration system (Guidewire PolicyCenter-style).

Not the real Guidewire Cloud API - it only shows the integration pattern: the agent creates a
submission record in the core system through a REST call, and gets back a system-issued number.

Run:  uvicorn mock_policycenter.api:app --port 8001
Docs: http://127.0.0.1:8001/docs
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

STORE = Path(__file__).resolve().parents[1] / "runtime" / "policycenter_submissions.json"
STORE.parent.mkdir(exist_ok=True)

app = FastAPI(title="Mock PolicyCenter", version="0.1")


class Account(BaseModel):
    name: str
    address: Optional[dict[str, Any]] = None
    naics: Optional[str] = None
    annualRevenue: Optional[float] = None


class SubmissionIn(BaseModel):
    account: Account
    producer: dict[str, Optional[str]]
    lines: list[str]
    effectiveDate: Optional[str] = None
    triage: dict[str, Any]
    appetite: Optional[str] = None
    sourceRunId: str


def _load() -> list[dict]:
    return json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else []


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/submissions", status_code=201)
def create_submission(body: SubmissionIn) -> dict:
    if not body.lines:
        raise HTTPException(422, "At least one line of business is required")
    rows = _load()
    if any(r["sourceRunId"] == body.sourceRunId for r in rows):
        raise HTTPException(409, "Submission already created for this run")
    number = f"PC-SUB-{len(rows) + 1:06d}"
    row = {"submissionNumber": number, "status": "Draft",
           "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), **body.model_dump()}
    rows.append(row)
    STORE.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return {"submissionNumber": number, "status": "Draft"}


@app.get("/api/v1/submissions")
def list_submissions() -> list[dict]:
    return _load()
