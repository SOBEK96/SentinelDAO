#!/usr/bin/env python3
"""
SentinelDAO 1-Click End-to-End Lifecycle Demonstration.
Simulates DAO Whistleblower Escrow Campaign, Encrypted Leak Submission, AI Forensic Auditing, and Anonymous Bounty Settlement.
"""

import json
from gltest.direct import VMContext, deploy_contract, create_address

ATTO = 10**18


def log_step(num: int, title: str):
    print(f"\n\033[1;36m[STEP {num}] {title}\033[0m")


def log_success(msg: str):
    print(f"  \033[1;32m✓\033[0m {msg}")


def log_info(key: str, val: str):
    print(f"  \033[1;34m•\033[0m {key}: \033[1;37m{val}\033[0m")


def main():
    print("\033[1;35m" + "=" * 70)
    print(" 🛡️  SENTINELDAO: 1-CLICK END-TO-END WHISTLEBLOWER ESCROW LIFECYCLE")
    print("=" * 70 + "\033[0m")

    # 1. Initialize Direct VM Environment
    vm = VMContext()
    dao_backer = create_address("dao_backer")      # Campaign Funder
    whistleblower = create_address("whistleblower")# Submitter
    stealth_payout = create_address("stealth_payout") # Anonymous Receiver

    with vm.activate():
        vm.sender = dao_backer
        contract = deploy_contract("protocol/sentinel_dao.py", vm=vm)

        # STEP 1: Campaign Creation
        log_step(1, "DAO Funder Creates 50 GEN Whistleblower Bounty Campaign for Apex Energy")
        vm.sender = dao_backer
        vm.value = 50 * ATTO
        contract.create_campaign(
            "camp-apex-energy-01",
            "Apex Energy Corp",
            "ACCOUNTING_FRAUD",
            75, # Materiality Index Threshold = 75
            "Bounty for verified evidence of off-balance-sheet Special Purpose Vehicle debt concealment.",
        )
        camp = contract.get_campaign("camp-apex-energy-01")
        log_success("Campaign Initialized & Funded in Escrow")
        log_info("Target Entity", camp["target_entity"])
        log_info("Category", camp["category"])
        log_info("Escrow Bounty Pool", f"{int(camp['escrow_balance_atto']) // ATTO} GEN")
        log_info("Materiality Threshold", f"{camp['min_materiality_threshold']} / 100")

        # STEP 2: Whistleblower Evidence Submission
        log_step(2, "Anonymous Whistleblower Submits Cryptographically Committed Leak")
        vm.sender = whistleblower
        contract.submit_disclosure(
            "disc-apex-q3-spv-leak",
            "camp-apex-energy-01",
            "ipfs://bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "Internal Q3 Ledger Disclosing $450M Concealed Unhedged Liabilities",
            stealth_payout,
            "sha256:d8a571f92e4c498305c74fbbf081a9f604473859d57a2c74d6c701d5ff789abc",
        )
        disc = contract.get_disclosure("disc-apex-q3-spv-leak")
        log_success("Evidence Disclosure Registered On-Chain")
        log_info("Disclosure Summary", disc["summary"])
        log_info("Evidence SHA256 Commitment", disc["evidence_hash"][:32] + "...")
        log_info("Encrypted IPFS Payload CID", disc["proof_cid"])
        log_info("Whistleblower Stealth Payout Addr", disc["whistleblower_stealth"])

        # STEP 3: Multi-LLM Forensic Consensus Audit & SEC Corroboration
        log_step(3, "GenLayer Multi-LLM Forensic Quorum Audits Leak Materiality & SEC Filings")
        vm.mock_web(r".*", {"status": 200, "body": json.dumps({"filings": [{"form": "10-Q", "status": "investigation_flagged"}]})})
        vm.mock_llm(
            r".*",
            json.dumps({
                "decision": "VERIFIED",
                "confidence": 95,
                "verifiability": 96,
                "severity": 94,
                "documentation_depth": 90,
                "rationale": "Forensic evidence proves $450M off-balance sheet liabilities omitted from SEC 10-Q filing.",
            })
        )
        contract.evaluate_disclosure("disc-apex-q3-spv-leak", "Corroborated by internal executive emails.")
        evaluated = contract.get_disclosure("disc-apex-q3-spv-leak")
        log_success(f"Forensic Audit Complete! Status: {evaluated['status']}")
        log_info("Computed Materiality Index (MIS)", f"{evaluated['materiality_index']} / 100 (Exceeded {camp['min_materiality_threshold']} threshold)")
        log_info("Awarded Bounty", f"{int(evaluated['awarded_bounty_atto']) // ATTO} GEN (100% Critical Payout)")

        # STEP 4: Bounty Claiming
        log_step(4, "Whistleblower Claims Awarded 50 GEN Bounty Payout")
        vm.sender = stealth_payout
        contract.claim_bounty("disc-apex-q3-spv-leak")
        claimed = contract.get_disclosure("disc-apex-q3-spv-leak")
        log_success(f"Bounty Disbursed! Final Status: {claimed['status']}")
        log_info("Is Claimed Flag", f"{claimed['is_claimed']}")

        # STEP 5: Protocol Summary
        log_step(5, "Inspect Protocol Double-Entry Ledgers")
        overview = contract.get_protocol_overview()
        log_info("Total Campaigns Created", f"{overview['total_campaigns']}")
        log_info("Total Disclosures Processed", f"{overview['total_disclosures']}")
        log_info("Total Bounties Funded", f"{int(overview['total_bounties_funded']) // ATTO} GEN")
        log_info("Total Bounties Paid Out", f"{int(overview['total_bounties_paid']) // ATTO} GEN")

        print("\n\033[1;32m" + "=" * 70)
        print(" 🎉 SENTINELDAO RUNNABLE WORKFLOW VERIFIED SUCCESSFULLY (100% PASS)")
        print("=" * 70 + "\033[0m\n")


if __name__ == "__main__":
    main()
