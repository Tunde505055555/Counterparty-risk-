"""Behavioural tests against a running GenLayer node (gltest).

These exercise the deterministic surface: intake validation, the evidence
allowlist, lifecycle guards, access control and view shapes. Rounds that call
`assess`/`challenge` consume LLM and web access, so they are marked `slow` and
assert on the *shape* of the ruling rather than on a specific score.

    gltest                       # all
    gltest -m "not slow"         # deterministic only
"""

from __future__ import annotations

import json

import pytest

from conftest import ALLOWED_DOMAINS, CRITERIA, REVIEWER

CONTEXT = "Prepayment of USD 250,000 to a first-time supplier, no escrow."


def open_default(contract, **overrides):
    args = {
        "subject_name": "Acme Industrial Supply Ltd",
        "subject_domain": "acme-industrial.example",
        "context": CONTEXT,
        "criteria": CRITERIA,
        "evidence_urls": json.dumps(
            ["https://companieshouse.gov.uk/search?q=acme+industrial"]
        ),
        "reviewer": REVIEWER,
    }
    args.update(overrides)
    contract.open_case(args=list(args.values())).transact()
    return contract.cases_of(args=[contract.account.address]).call()[-1]


# --- configuration ------------------------------------------------------------


def test_config_exposes_the_consensus_contract(contract):
    cfg = contract.config(args=[]).call()
    assert cfg["allowed_domains"] == json.loads(ALLOWED_DOMAINS)
    assert cfg["risk_levels"][-1] == "INSUFFICIENT_EVIDENCE"
    assert cfg["max_rounds"] == len(cfg["score_tolerance_by_round"])
    # The ladder must be exhaustible by the authorized challengers, otherwise
    # DEADLOCKED and reviewer_ruling are unreachable.
    assert cfg["max_rounds"] == cfg["max_parties"] == 3
    assert cfg["score_tolerance_by_round"][-1] == 0
    assert len(cfg["risk_flags"]) >= 10


def test_allowlist_is_owner_only(contract):
    with pytest.raises(Exception):
        contract.set_allowed_domains(args=['["evil.example"]']).transact(
            from_account=contract.other_account
        )


# --- intake -------------------------------------------------------------------


def test_open_case_stores_criteria_and_seeds_subject_url(contract):
    case_id = open_default(contract)
    case = contract.get_case(args=[case_id]).call()
    assert case["status"] == 0
    assert case["criteria"] == json.loads(CRITERIA)
    assert case["evidence_urls"][0] == "https://acme-industrial.example/"
    assert case["round_index"] == 0
    assert case["rounds_recorded"] == 0


def test_open_case_requires_criteria(contract):
    with pytest.raises(Exception):
        open_default(contract, criteria="[]")


def test_open_case_requires_context(contract):
    with pytest.raises(Exception):
        open_default(contract, context="   ")


def test_evidence_must_be_allowlisted(contract):
    with pytest.raises(Exception):
        open_default(contract, evidence_urls='["https://random-blog.example/post"]')


def test_evidence_must_be_https(contract):
    with pytest.raises(Exception):
        open_default(contract, evidence_urls='["http://sec.gov/x"]')


def test_subject_domain_is_always_allowed_for_its_own_case(contract):
    case_id = open_default(
        contract, evidence_urls='["https://acme-industrial.example/about"]'
    )
    urls = contract.get_case(args=[case_id]).call()["evidence_urls"]
    assert "https://acme-industrial.example/about" in urls


def test_anyone_may_widen_evidence_within_the_allowlist(contract):
    case_id = open_default(contract)
    contract.submit_evidence(
        args=[case_id, "https://trustpilot.com/review/acme-industrial.example"]
    ).transact(from_account=contract.other_account)
    urls = contract.get_case(args=[case_id]).call()["evidence_urls"]
    assert any("trustpilot.com" in u for u in urls)


def test_duplicate_evidence_is_idempotent(contract):
    case_id = open_default(contract)
    before = contract.get_case(args=[case_id]).call()["evidence_urls"]
    contract.submit_evidence(args=[case_id, before[0]]).transact()
    assert contract.get_case(args=[case_id]).call()["evidence_urls"] == before


def test_unknown_case_is_rejected(contract):
    with pytest.raises(Exception):
        contract.get_case(args=[9999]).call()


# --- lifecycle guards ---------------------------------------------------------


def test_challenge_requires_a_standing_ruling(contract):
    case_id = open_default(contract)
    with pytest.raises(Exception):
        contract.challenge(args=[case_id]).transact()


def test_finalize_requires_a_standing_ruling(contract):
    case_id = open_default(contract)
    with pytest.raises(Exception):
        contract.finalize(args=[case_id]).transact()


def test_request_finalize_requires_a_standing_ruling(contract):
    case_id = open_default(contract)
    with pytest.raises(Exception):
        contract.request_finalize(args=[case_id]).transact()


def test_reviewer_ruling_requires_deadlock(contract):
    case_id = open_default(contract)
    with pytest.raises(Exception):
        contract.reviewer_ruling(
            args=[case_id, 10, 0, "[]", "[]", "looks fine"]
        ).transact()


def test_assessment_is_null_before_any_round(contract):
    case_id = open_default(contract)
    result = contract.get_assessment(args=[case_id]).call()
    assert result["ruling"] is None


# --- rounds (LLM + web) -------------------------------------------------------


@pytest.mark.slow
def test_assess_produces_a_structured_ruling(contract):
    case_id = open_default(contract)
    contract.assess(args=[case_id]).transact()

    case = contract.get_case(args=[case_id]).call()
    assert case["status"] == 1
    assert case["rounds_recorded"] == 1

    ruling = contract.get_assessment(args=[case_id]).call()
    assert 0 <= ruling["risk_score"] <= 100
    assert ruling["risk_level_name"] in {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        "INSUFFICIENT_EVIDENCE",
    }
    assert isinstance(ruling["flags"], list)
    assert all(isinstance(f, str) for f in ruling["flags"])
    for unmet in ruling["unmet_criteria"]:
        assert unmet["criterion"] in json.loads(CRITERIA)
    assert ruling["reasoning"]
    assert ruling["by_reviewer"] is False


@pytest.mark.slow
def test_no_footprint_never_resolves_to_low(contract):
    case_id = open_default(
        contract,
        subject_name="Northwind Capital Partners",
        subject_domain="nonexistent-counterparty-98f2a.example",
        evidence_urls="[]",
    )
    contract.assess(args=[case_id]).transact()
    ruling = contract.get_assessment(args=[case_id]).call()
    assert ruling["risk_level_name"] != "LOW"


@pytest.mark.slow
def test_assess_cannot_run_twice(contract):
    case_id = open_default(contract)
    contract.assess(args=[case_id]).transact()
    with pytest.raises(Exception):
        contract.assess(args=[case_id]).transact()


@pytest.mark.slow
def test_challenge_appends_a_stricter_round(contract):
    case_id = open_default(contract)
    contract.assess(args=[case_id]).transact()
    contract.challenge(args=[case_id]).transact()

    history = contract.get_rulings(args=[case_id]).call()
    assert len(history) == 2
    assert [r["round"] for r in history] == [0, 1]


@pytest.mark.slow
def test_finalize_needs_two_party_assent(contract):
    """A single address cannot close a case while challenges remain: it must be
    requested by one party and confirmed by a different one."""
    case_id = open_default(contract)
    contract.assess(args=[case_id]).transact()

    with pytest.raises(Exception):
        contract.finalize(args=[case_id]).transact()

    contract.request_finalize(args=[case_id]).transact()
    assert (
        contract.get_case(args=[case_id]).call()["finalize_requested_by"] != ""
    )

    # Same party confirming its own request is not assent.
    with pytest.raises(Exception):
        contract.finalize(args=[case_id]).transact()
    assert contract.get_case(args=[case_id]).call()["status"] == 1


@pytest.mark.slow
def test_one_challenge_per_address(contract):
    case_id = open_default(contract)
    contract.assess(args=[case_id]).transact()
    contract.challenge(args=[case_id]).transact()

    case = contract.get_case(args=[case_id]).call()
    assert len(case["challengers"]) == 1
    with pytest.raises(Exception):
        contract.challenge(args=[case_id]).transact()
