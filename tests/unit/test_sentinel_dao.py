"""Comprehensive Direct Pytest Suite for SentinelDAO Whistleblower Protocol."""

import pytest
from conftest import (
    CONTRACT_PATH,
    mock_ai_forensic,
    mock_regulatory_oracle,
)

ATTO = 10**18


# -----------------------------------------------------------------------------
# 1. Protocol Overview & Initialization
# -----------------------------------------------------------------------------
def test_initial_protocol_overview(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    overview = contract.get_protocol_overview()
    assert overview["total_campaigns"] == 0
    assert overview["total_disclosures"] == 0
    assert overview["total_bounties_funded"] == "0"
    assert overview["total_bounties_paid"] == "0"


# -----------------------------------------------------------------------------
# 2. Campaign Creation & Funding Tests
# -----------------------------------------------------------------------------
def test_create_campaign_success(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 10 * ATTO

    contract.create_campaign(
        "camp-enron-v2",
        "Apex Energy Corp",
        "ACCOUNTING_FRAUD",
        75,
        "Investigating off-balance-sheet special purpose vehicles.",
    )

    camp = contract.get_campaign("camp-enron-v2")
    assert camp["campaign_id"] == "camp-enron-v2"
    assert camp["target_entity"] == "Apex Energy Corp"
    assert camp["category"] == "ACCOUNTING_FRAUD"
    assert camp["escrow_balance_atto"] == str(10 * ATTO)
    assert camp["min_materiality_threshold"] == 75
    assert camp["status"] == "OPEN"


def test_create_campaign_below_min_escrow_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 2 * ATTO  # Minimum is 5 GEN

    with pytest.raises(Exception) as exc:
        contract.create_campaign(
            "camp-low-escrow",
            "Target Corp",
            "ACCOUNTING_FRAUD",
            70,
            "Description",
        )
    assert "Minimum campaign escrow is 5 GEN" in str(exc.value)


def test_create_campaign_invalid_category_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 10 * ATTO

    with pytest.raises(Exception) as exc:
        contract.create_campaign(
            "camp-bad-cat",
            "Target Corp",
            "INVALID_CATEGORY",
            70,
            "Description",
        )
    assert "Invalid category" in str(exc.value)


def test_create_campaign_invalid_threshold_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 10 * ATTO

    with pytest.raises(Exception) as exc:
        contract.create_campaign(
            "camp-bad-thresh",
            "Target Corp",
            "ACCOUNTING_FRAUD",
            40,  # Below 60 floor
            "Description",
        )
    assert "Materiality threshold must be between 60 and 100" in str(exc.value)


def test_create_all_valid_categories(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    categories = [
        "ACCOUNTING_FRAUD",
        "ESG_ENVIRONMENTAL",
        "INSIDER_TRADING",
        "CORRUPTION_BRIBERY",
        "AI_SAFETY_VIOLATION",
    ]
    for idx, cat in enumerate(categories):
        cid = f"camp-cat-{idx}"
        direct_vm.value = 5 * ATTO
        contract.create_campaign(
            cid,
            f"Entity {idx}",
            cat,
            65,
            f"Description for {cat}",
        )
        camp = contract.get_campaign(cid)
        assert camp["category"] == cat


def test_topup_campaign_success(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 10 * ATTO
    contract.create_campaign(
        "camp-topup-test",
        "BioToxic Inc",
        "ESG_ENVIRONMENTAL",
        70,
        "Illegal wastewater dumping in river basin.",
    )

    # Bob tops up with 15 GEN
    direct_vm.sender = direct_bob
    direct_vm.value = 15 * ATTO
    contract.topup_campaign("camp-topup-test")

    camp = contract.get_campaign("camp-topup-test")
    assert camp["escrow_balance_atto"] == str(25 * ATTO)


# -----------------------------------------------------------------------------
# 3. Disclosure Submission Tests
# -----------------------------------------------------------------------------
def test_submit_disclosure_success(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    # Sponsor creates campaign
    direct_vm.sender = direct_alice
    direct_vm.value = 20 * ATTO
    contract.create_campaign(
        "camp-ai-leak",
        "OmniAI Labs",
        "AI_SAFETY_VIOLATION",
        80,
        "Unauthorized deployment of self-replicating autonomous model.",
    )

    # Whistleblower submits proof under stealth address (Charlie)
    direct_vm.sender = direct_bob
    contract.submit_disclosure(
        "disc-ai-01",
        "camp-ai-leak",
        "ipfs://bafybeievidenceweightsandchatlogs2026",
        "Internal server logs proving model bypassed containment safeguards.",
        direct_charlie,
    )

    disc = contract.get_disclosure("disc-ai-01")
    assert disc["disclosure_id"] == "disc-ai-01"
    assert disc["campaign_id"] == "camp-ai-leak"
    assert disc["whistleblower_stealth"].lower().removeprefix("0x") == direct_charlie.hex().lower()
    assert disc["status"] == "PENDING"


def test_submit_disclosure_closed_campaign_rejection(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 10 * ATTO
    contract.create_campaign(
        "camp-to-close",
        "Target",
        "ACCOUNTING_FRAUD",
        70,
        "Description",
    )
    contract.close_campaign("camp-to-close")

    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.submit_disclosure(
            "disc-rejected",
            "camp-to-close",
            "ipfs://proof",
            "Summary",
            direct_charlie,
        )
    assert "is not OPEN" in str(exc.value)


# -----------------------------------------------------------------------------
# 4. Forensic Evaluation & Bounty Awards
# -----------------------------------------------------------------------------
def test_evaluate_disclosure_critical_breach_100_percent_payout(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    # Alice funds 50 GEN escrow
    direct_vm.sender = direct_alice
    direct_vm.value = 50 * ATTO
    contract.create_campaign(
        "camp-critical",
        "MegaChem Corp",
        "ESG_ENVIRONMENTAL",
        75,
        "Dumping toxic PFAS compounds into public reservoir.",
    )

    # Bob submits disclosure
    direct_vm.sender = direct_bob
    contract.submit_disclosure(
        "disc-critical-pfas",
        "camp-critical",
        "ipfs://pfas-soil-samples-and-internal-emails",
        "Water laboratory spectrometry proofs verifying 500x legal PFAS limits.",
        direct_charlie,
    )

    # Mock Web2 EPA registry & Multi-LLM Forensic Quorum (MIS >= 90 -> Critical)
    mock_regulatory_oracle(direct_vm, {"status": "clean", "investigations": []})
    mock_ai_forensic(
        direct_vm,
        decision="VERIFIED",
        confidence=96,
        verifiability=95,
        severity=96,
        documentation_depth=90,  # MIS = (95*0.35 + 96*0.40 + 90*0.25) = 33.25 + 38.4 + 22.5 = 94.15 -> 94
        rationale="Overwhelming documentary proof of deliberate contamination.",
    )

    contract.evaluate_disclosure(
        "disc-critical-pfas",
        "Spectrometry lab sheets, geotagged pipe outflow drone footage, executive signoffs.",
    )

    disc = contract.get_disclosure("disc-critical-pfas")
    assert disc["status"] == "VERIFIED_AWARDED"
    assert int(disc["materiality_index"]) >= 90
    assert disc["awarded_bounty_atto"] == str(50 * ATTO)  # 100% of escrow

    camp = contract.get_campaign("camp-critical")
    assert camp["escrow_balance_atto"] == "0"
    assert camp["status"] == "DEPLETED"


def test_evaluate_disclosure_progressive_payout_75_mis(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    direct_vm.value = 100 * ATTO
    contract.create_campaign(
        "camp-insider-trading",
        "FinTech Global",
        "INSIDER_TRADING",
        65,
        "Executive options dumping prior to earnings miss.",
    )

    direct_vm.sender = direct_bob
    contract.submit_disclosure(
        "disc-insider-01",
        "camp-insider-trading",
        "ipfs://trade-logs",
        "Brokerage execution timestamps coinciding with internal board meetings.",
        direct_charlie,
    )

    mock_regulatory_oracle(direct_vm)
    # MIS calculation: 75 -> Quadratic scale = ((75 - 60) / 40)^2 * 0.90 = (15/40)^2 * 0.90 = (0.375)^2 * 0.90 = 0.140625 * 0.90 = 0.1265625 (12.65% of 100 GEN)
    mock_ai_forensic(
        direct_vm,
        decision="VERIFIED",
        confidence=90,
        verifiability=80,
        severity=75,
        documentation_depth=70,  # MIS = (80*0.35 + 75*0.40 + 70*0.25) = 28 + 30 + 17.5 = 75.5 -> 75
        rationale="Substantial evidence of front-running quarterly filings.",
    )

    contract.evaluate_disclosure(
        "disc-insider-01",
        "Detailed broker confirmation statements.",
    )

    disc = contract.get_disclosure("disc-insider-01")
    assert disc["status"] == "VERIFIED_AWARDED"
    assert int(disc["awarded_bounty_atto"]) > 0


def test_evaluate_disclosure_low_materiality_insufficient(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    direct_vm.value = 50 * ATTO
    contract.create_campaign(
        "camp-weak-evidence",
        "Target Corp",
        "ACCOUNTING_FRAUD",
        80,  # Required 80
        "Description",
    )

    direct_vm.sender = direct_bob
    contract.submit_disclosure(
        "disc-weak",
        "camp-weak-evidence",
        "ipfs://weak-proof",
        "Anonymous rumor about expense accounts.",
        direct_charlie,
    )

    mock_regulatory_oracle(direct_vm)
    mock_ai_forensic(
        direct_vm,
        decision="INSUFFICIENT",
        confidence=60,
        verifiability=40,
        severity=30,
        documentation_depth=30,
        rationale="Unsubstantiated hearsay without primary source documents.",
    )

    contract.evaluate_disclosure("disc-weak", "Unverified claims.")

    disc = contract.get_disclosure("disc-weak")
    assert disc["status"] == "INSUFFICIENT_EVIDENCE"
    assert disc["awarded_bounty_atto"] == "0"


def test_evaluate_disclosure_rejected_fraudulent(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    direct_vm.value = 50 * ATTO
    contract.create_campaign(
        "camp-fake",
        "Target Corp",
        "CORRUPTION_BRIBERY",
        70,
        "Description",
    )

    direct_vm.sender = direct_bob
    contract.submit_disclosure(
        "disc-fake",
        "camp-fake",
        "ipfs://fake-proof",
        "Fabricated invoice screenshots.",
        direct_charlie,
    )

    mock_regulatory_oracle(direct_vm)
    mock_ai_forensic(
        direct_vm,
        decision="REJECTED",
        confidence=98,
        verifiability=10,
        severity=10,
        documentation_depth=10,
        rationale="Photoshop manipulation artifacts detected in invoice headers.",
    )

    contract.evaluate_disclosure("disc-fake", "Fake invoice.")

    disc = contract.get_disclosure("disc-fake")
    assert disc["status"] == "REJECTED"
    assert disc["awarded_bounty_atto"] == "0"


# -----------------------------------------------------------------------------
# 5. Bounty Claiming Tests
# -----------------------------------------------------------------------------
def test_claim_bounty_success(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    direct_vm.value = 50 * ATTO
    contract.create_campaign(
        "camp-claim-test",
        "Target Corp",
        "ACCOUNTING_FRAUD",
        70,
        "Description",
    )

    direct_vm.sender = direct_bob
    contract.submit_disclosure(
        "disc-claim-01",
        "camp-claim-test",
        "ipfs://proof",
        "Summary",
        direct_charlie,
    )

    mock_regulatory_oracle(direct_vm)
    mock_ai_forensic(direct_vm, decision="VERIFIED", confidence=95, verifiability=95, severity=95, documentation_depth=95)
    contract.evaluate_disclosure("disc-claim-01", "Technical evidence")

    # Charlie (stealth address) claims bounty
    direct_vm.sender = direct_charlie
    contract.claim_bounty("disc-claim-01")

    disc = contract.get_disclosure("disc-claim-01")
    assert disc["is_claimed"] is True


def test_claim_bounty_unauthorized_rejection(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    direct_vm.value = 50 * ATTO
    contract.create_campaign(
        "camp-unauth-test",
        "Target Corp",
        "ACCOUNTING_FRAUD",
        70,
        "Description",
    )

    direct_vm.sender = direct_bob
    contract.submit_disclosure(
        "disc-unauth-01",
        "camp-unauth-test",
        "ipfs://proof",
        "Summary",
        direct_charlie,
    )

    mock_regulatory_oracle(direct_vm)
    mock_ai_forensic(direct_vm, decision="VERIFIED", confidence=95, verifiability=95, severity=95, documentation_depth=95)
    contract.evaluate_disclosure("disc-unauth-01", "Evidence")

    # Bob (not the stealth address Charlie) tries to claim
    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.claim_bounty("disc-unauth-01")
    assert "Only whistleblower stealth address can claim" in str(exc.value)


# -----------------------------------------------------------------------------
# 6. Campaign Closure & Listing Tests
# -----------------------------------------------------------------------------
def test_close_campaign_success(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 25 * ATTO
    contract.create_campaign(
        "camp-close-refund",
        "Target Corp",
        "ACCOUNTING_FRAUD",
        70,
        "Description",
    )

    contract.close_campaign("camp-close-refund")
    camp = contract.get_campaign("camp-close-refund")
    assert camp["status"] == "CLOSED"
    assert camp["escrow_balance_atto"] == "0"


def test_list_campaigns_and_disclosures(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 10 * ATTO
    contract.create_campaign(
        "camp-list-test",
        "Target Corp",
        "ACCOUNTING_FRAUD",
        70,
        "Description",
    )

    direct_vm.sender = direct_bob
    contract.submit_disclosure(
        "disc-list-test",
        "camp-list-test",
        "ipfs://proof",
        "Summary",
        direct_charlie,
    )

    camps = contract.list_campaigns()
    assert len(camps) == 1
    assert camps[0]["campaign_id"] == "camp-list-test"

    discs = contract.list_disclosures("camp-list-test")
    assert len(discs) == 1
    assert discs[0]["disclosure_id"] == "disc-list-test"


def test_grounded_web_fetch_failure_rejection(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    direct_vm.value = 20 * ATTO
    contract.create_campaign(
        "camp-grounded-test",
        "Target Corp",
        "ACCOUNTING_FRAUD",
        70,
        "Description",
    )

    direct_vm.sender = direct_bob
    contract.submit_disclosure(
        "disc-grounded-fail",
        "camp-grounded-test",
        "ipfs://proof",
        "Summary",
        direct_charlie,
    )

    # Mock web returning HTTP 500
    direct_vm.mock_web(r".*", {"status": 500, "body": "Internal Server Error"})

    with pytest.raises(Exception) as exc:
        contract.evaluate_disclosure("disc-grounded-fail")
    assert "[EXTERNAL]" in str(exc.value) or "500" in str(exc.value)
