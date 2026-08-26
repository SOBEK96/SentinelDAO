"""GenLayer Integration Test Suite for SentinelDAO Whistleblower Escrow."""

import pytest
from gltest import get_contract_factory
from gltest.assertions import tx_execution_succeeded


def test_sentinel_dao_integration_flow():
    factory = get_contract_factory("SentinelDAO")
    contract = factory.deploy(args=[])

    # 1. Create Whistleblower Campaign
    tx_camp = contract.create_campaign(
        args=[
            "camp-int-01",
            "MegaCorp Carbon Offset Laundering",
            "ESG_GREENWASHING",
            "Report fraudulent phantom carbon offsets claimed in 2025 audit.",
            1750000000,
        ],
        value=50 * 10**18,
    ).transact()
    assert tx_execution_succeeded(tx_camp)

    # 2. Whistleblower Submits Encrypted Evidence Report
    tx_submit = contract.submit_disclosure(
        args=[
            "disc-int-01",
            "camp-int-01",
            "0x70997970c51812dc3a010c7d01b50e0d17dc79c8",  # Stealth address
            "ipfs://bafybeihdwdcefgh456internal-ledger-offsets.enc",
            "https://registry.verra.org/api/v1/carbon-credits/audit",
        ]
    ).transact()
    assert tx_execution_succeeded(tx_submit)

    # 3. Read State via .call()
    disc = contract.get_disclosure(args=["disc-int-01"]).call()
    assert disc["disclosure_id"] == "disc-int-01"
    assert disc["status"] == "PENDING_AUDIT"
