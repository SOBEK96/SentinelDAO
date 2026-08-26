"""Shared fixtures and mock helpers for SentinelDAO direct-mode tests."""

import json

CONTRACT_PATH = "contracts/sentinel_dao.py"
FORENSIC_PROMPT_PATTERN = r".*Senior Corporate Fraud Investigator and Forensic Auditor.*"


def mock_ai_forensic(
    direct_vm,
    decision: str = "VERIFIED",
    confidence: int = 92,
    verifiability: int = 95,
    severity: int = 90,
    documentation_depth: int = 85,
    rationale: str = "Evidence documents severe material breach corroborated by internal ledgers.",
):
    """Mock the Multi-LLM Quorum call for whistleblower disclosures."""
    direct_vm.mock_llm(
        FORENSIC_PROMPT_PATTERN,
        json.dumps(
            {
                "decision": decision,
                "confidence": confidence,
                "verifiability": verifiability,
                "severity": severity,
                "documentation_depth": documentation_depth,
                "rationale": rationale,
            }
        ),
    )


def mock_regulatory_oracle(direct_vm, payload=None, status: int = 200):
    """Mock the Web2 regulatory database API (SEC / EPA / Courts)."""
    body = json.dumps(payload if payload is not None else {"status": "clean", "filings": []})
    direct_vm.mock_web(r".*", {"status": status, "body": body})
