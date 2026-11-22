"""Tests for the deterministic parts (no API key needed): run with  pytest -q"""
from datetime import date

from app import rag
from app.agents import appetite, clearance, triage, validation
from app.schemas import (Address, AppetiteResult, ClearanceResult, Enrichment, ExtractedSubmission,
                         LossRecord)
from app.tools import hazard_profile

TODAY = date(2026, 11, 20)


def good_sub(**kw) -> ExtractedSubmission:
    base = dict(
        insured_name="Bright Smile Dental Care LLC", business_description="Dental office",
        annual_revenue=2_400_000, years_in_business=12, building_value=1_850_000, contents_value=620_000,
        construction_type="Joisted masonry", year_built=2004, sprinklered=True,
        lines_requested=["Property", "General Liability"], effective_date="2026-12-11",
        location_address=Address(street="4410 Burnet Rd", city="Austin", state="TX", zip_code="78756"),
    )
    base.update(kw)
    return ExtractedSubmission(**base)


def test_validation_complete_submission_has_no_blocking_issues():
    issues = validation.check(good_sub(), ["application", "loss_run"], TODAY)
    assert not [i for i in issues if i.severity == "blocking"]


def test_validation_flags_missing_fields_and_loss_runs():
    issues = validation.check(good_sub(construction_type=None, year_built=None), ["application"], TODAY)
    fields = {i.field for i in issues if i.severity == "blocking"}
    assert {"construction_type", "year_built", "loss_runs"} <= fields


def test_validation_warns_on_short_effective_date():
    issues = validation.check(good_sub(effective_date="2026-11-23"), ["application", "loss_run"], TODAY)
    assert any(i.field == "effective_date" and i.severity == "warning" for i in issues)


def test_validation_turns_conflicts_into_warnings():
    sub = good_sub(data_conflicts=["annual_revenue: email says 3200000, application says 2400000"])
    issues = validation.check(sub, ["application", "loss_run"], TODAY)
    assert any(i.field == "conflict" and i.severity == "warning" for i in issues)


def test_null_lists_from_llm_become_empty_lists():
    sub = ExtractedSubmission(prior_losses=None, lines_requested=None, data_conflicts=None)
    assert sub.prior_losses == [] and sub.lines_requested == [] and sub.data_conflicts == []


def test_construction_codes_are_expanded():
    assert ExtractedSubmission(construction_type="JM").construction_type == "Joisted masonry"
    assert ExtractedSubmission(construction_type="Frame").construction_type == "Frame"


def test_clearance_matches_despite_formatting_differences():
    existing = [{"submission_id": "EX-1", "insured_name": "Riverside Auto Parts, Inc.",
                 "address": "880 West Broad Street, Columbus, OH 43222", "broker": "B", "received": "2026-11-02"}]
    sub = good_sub(insured_name="Riverside Auto Parts Inc.",
                   location_address=Address(street="880 W Broad St", city="Columbus", state="OH", zip_code="43222"))
    assert clearance.check(sub, existing).status == "possible_duplicate"


def test_clearance_clear_for_new_business():
    existing = [{"submission_id": "EX-1", "insured_name": "Lakeview Pediatrics PC",
                 "address": "77 Lake Shore Dr, Chicago, IL 60611", "broker": "B", "received": "2026-10-28"}]
    assert clearance.check(good_sub(), existing).status == "clear"


def test_hazards_coastal_texas_is_high_hurricane():
    assert hazard_profile("TX", "Galveston")["hurricane"] == "high"
    assert hazard_profile("TX", "Austin")["hurricane"] == "moderate"


def test_appetite_rules_refer_bad_loss_history():
    losses = [LossRecord(year=2022, cause="injury", amount_paid=22000),
              LossRecord(year=2023, cause="theft", amount_paid=15000),
              LossRecord(year=2024, cause="Fire in finishing area", amount_paid=310000)]
    hits = appetite.rule_engine(good_sub(prior_losses=losses), Enrichment(hazards={}), TODAY)
    referred = {h.rule_id for h in hits if h.outcome == "refer"}
    assert {"5.1", "5.2", "5.3"} <= referred


def test_appetite_rules_decline_tiv_over_limit():
    hits = appetite.rule_engine(good_sub(building_value=14_000_000, contents_value=2_000_000),
                                Enrichment(hazards={}), TODAY)
    assert any(h.rule_id == "3.1" and h.outcome == "decline" for h in hits)


def test_triage_clean_preferred_risk_is_p1():
    app = AppetiteResult(decision="in_appetite")
    priority, score, _ = triage.score(good_sub(), [], ClearanceResult(status="clear"), app,
                                      Enrichment(hazards={"hurricane": "moderate"}), True, TODAY)
    assert priority == "P1-hot" and score >= 75


def test_triage_out_of_appetite_is_decline():
    app = AppetiteResult(decision="out_of_appetite")
    priority, _, _ = triage.score(good_sub(), [], ClearanceResult(status="clear"), app, None, False, TODAY)
    assert priority == "decline"


def test_rag_finds_prohibited_class_rule():
    ids = [r["id"] for r in rag.search("fireworks explosives manufacturing", k=3)]
    assert "2.1" in ids
