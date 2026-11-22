"""Pydantic models for a commercial P&C insurance submission.

The Intake Agent fills `ExtractedSubmission` from the broker's email and PDFs.
Every field is Optional on purpose: a missing value is information the
Validation Agent needs, so the LLM must leave it null instead of guessing.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = Field(None, description="2-letter US state code, e.g. TX")
    zip_code: Optional[str] = None

    def one_line(self) -> str:
        parts = [self.street, self.city, self.state, self.zip_code]
        return ", ".join(p for p in parts if p)


class LossRecord(BaseModel):
    year: Optional[int] = None
    cause: Optional[str] = Field(None, description="e.g. water damage, slip and fall, fire")
    amount_paid: Optional[float] = Field(None, description="USD paid on the claim")


class ExtractedSubmission(BaseModel):
    # Broker
    broker_name: Optional[str] = None
    broker_email: Optional[str] = None
    # Applicant
    insured_name: Optional[str] = Field(None, description="Legal name of the business to be insured")
    business_description: Optional[str] = Field(None, description="What the business does, in a few words")
    naics_code: Optional[str] = Field(None, description="6-digit NAICS code if stated")
    years_in_business: Optional[int] = None
    annual_revenue: Optional[float] = Field(None, description="USD")
    employee_count: Optional[int] = None
    mailing_address: Optional[Address] = None
    # Property
    location_address: Optional[Address] = Field(None, description="Address of the insured building")
    building_value: Optional[float] = Field(None, description="Total insured value of the building, USD")
    contents_value: Optional[float] = Field(None, description="Business personal property value, USD")
    construction_type: Optional[str] = Field(None, description="e.g. frame, joisted masonry, fire resistive")
    year_built: Optional[int] = None
    sprinklered: Optional[bool] = None
    # Coverage
    # Lists accept null because open models often send null for "nothing found"; the validator
    # below turns that into [] so the rest of the code always sees a list.
    lines_requested: Optional[list[str]] = Field(default_factory=list, description="e.g. Property, General Liability")
    effective_date: Optional[str] = Field(None, description="Requested policy start date, YYYY-MM-DD")
    # History
    prior_losses: Optional[list[LossRecord]] = Field(default_factory=list, description="Claims in the last 5 years")
    # Data quality
    data_conflicts: Optional[list[str]] = Field(
        default_factory=list,
        description="Values that differ between the email and the attachments, e.g. "
                    "'annual_revenue: email says 3200000, application says 2800000'. Empty if none.")

    @field_validator("construction_type", mode="after")
    @classmethod
    def _expand_construction_code(cls, v):
        # Standard ISO construction class abbreviations used on property forms.
        codes = {"F": "Frame", "JM": "Joisted masonry", "NC": "Non-combustible",
                 "MNC": "Masonry non-combustible", "MFR": "Modified fire resistive", "FR": "Fire resistive"}
        return codes.get(v.strip().upper().replace(".", ""), v) if v else v

    @field_validator("lines_requested", "prior_losses", "data_conflicts", mode="after")
    @classmethod
    def _none_to_empty(cls, v):
        return v or []


class ValidationIssue(BaseModel):
    field: str
    severity: Literal["blocking", "warning"]
    message: str


class ClearanceResult(BaseModel):
    status: Literal["clear", "possible_duplicate"]
    matched_submission_id: Optional[str] = None
    matched_broker: Optional[str] = None
    similarity: float = 0.0
    note: str = ""


class AppetiteRuleHit(BaseModel):
    rule_id: str
    outcome: Literal["pass", "refer", "decline"]
    detail: str


class AppetiteResult(BaseModel):
    decision: Literal["in_appetite", "refer", "out_of_appetite"]
    rule_hits: list[AppetiteRuleHit] = Field(default_factory=list)
    explanation: str = Field("", description="Plain-English reasoning that cites guideline sections")
    cited_sections: list[str] = Field(default_factory=list)


class Enrichment(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geocode_source: str = "none"
    hazards: dict[str, str] = Field(default_factory=dict, description="peril -> low/moderate/high")
    hazard_source: str = "mock"


class TriageResult(BaseModel):
    priority: Literal["P1-hot", "P2-standard", "P3-low", "decline"]
    score: int = Field(..., ge=0, le=100)
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    underwriter_summary: str = ""
    recommended_action: str = ""
