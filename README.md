```
   ____             __  _            __ ____   ___   ____ 
  / __/ ___  ___   / /_(_)___  ___  / // __ \ / _ | / __ \
 _\ \  / -_)/ _ \ / __/ // _ \/ -_)/ // /_/ // __ |/ /_/ /
/___/  \__//_//_/ \__/_//_//_/\__//_//_____//_/ |_|\____/ 
```
# 🛡️ SentinelDAO: Trustless Whistleblower Bounty & Forensic Evidence Protocol

> **Autonomous On-Chain Intelligence Tribunal for Corporate Whistleblowing, Financial Fraud Auditing, and Anonymous Bounty Disbursals.**

![GenLayer StudioNet](https://img.shields.io/badge/Network-GenLayer_StudioNet-green?style=flat-square)
![Tests](https://img.shields.io/badge/Pytest_Direct-17%2F17_Passed-brightgreen?style=flat-square)
![License](https://img.shields.io/badge/License-GPL_3.0-orange?style=flat-square)
![Security Audit](https://img.shields.io/badge/Consensus-Non--Custodial_Escrow-blue?style=flat-square)

---

## ⚡ Executive Summary

Traditional whistleblowing channels suffer from three fatal flaws:
1. **Physical & Retaliatory Risk**: Leakers must reveal identities to centralized lawyers or hotlines.
2. **Payment Insecurity**: Payouts take years of litigation with zero guarantee of fund release.
3. **Subjective Gatekeeping**: Corporate defense attorneys delay or bury valid evidence.

**SentinelDAO** resolves these vulnerabilities by pairing **GenLayer Intelligent Contracts** with cryptographic evidence commitments and an automated Multi-LLM Forensic Quorum. DAOs and public interest foundations fund on-chain bounty campaigns. Anonymous whistleblowers submit encrypted disclosures using disposable stealth addresses. The protocol fetches live regulatory databases (SEC EDGAR, EPA ECHO, DOJ) and autonomously executes the **Materiality Impact Score ($\text{MIS}$)** to disburse non-custodial payouts in real time.

---

## 🛰️ Live Deployment (GenLayer StudioNet)

```yaml
Network: GenLayer StudioNet (Chain ID: 61999)
RPC Endpoint: https://studio.genlayer.com/api
Explorer: https://genlayer-explorer.vercel.app
Contract Address: "0x1666c04938399ca1ff6E016Fe9abcD865999A680"
Deployer Address: "0x6cb8693052cacd8240ca13eb26b14f0f76375828"
Deployment Tx: "0x604e201a7ead0220570edcadb6fab460cc4f3b28d47f4d5832328488d516302f"
```

---

## 🔐 Cryptographic Guarantee & Threat Model Matrix

| Attack Vector | Traditional Whistleblower System | SentinelDAO Intelligent Contract |
| :--- | :--- | :--- |
| **Identity De-anonymization** | High (KYC hotlines, bank wires) | **Zero Knowledge**: Disposable stealth payout addresses |
| **Evidence Tampering** | High (Subpoena leaks, lost files) | **Immutable**: SHA256 evidence commitments + IPFS CIDs |
| **Capital Deadlocks** | High (Trapped escrow funds) | **Zero-Deadlock**: Emergency timeout reclamation (`reclaim_expired_campaign`) |
| **Biased Human Arbitration** | High (Political / corporate influence) | **Autonomous**: Multi-LLM Quorum with cross-regulatory consensus |
| **Spam / Extortion Attacks** | High (Frivolous claims) | **Quadratic Slashing & Proof Thresholds**: $\text{MIS} \ge 60\%$ threshold |

---

## 🧮 Mathematical Model: Quadratic Bounty Curve

Bounties are calculated based on the **Materiality Impact Score ($\text{MIS}$)**:

$$\text{MIS} = \frac{V \times 0.35 + S \times 0.40 + D \times 0.25}{100}$$

- **$V$ (Verifiability)**: Corroboration against SEC EDGAR / EPA disclosures ($0 \le V \le 100$).
- **$S$ (Severity)**: Financial fraud magnitude or public safety impact ($0 \le S \le 100$).
- **$D$ (Depth)**: Primary internal ledgers and cryptographic signatures ($0 \le D \le 100$).

### 💰 Payout Schedule:
$$\text{Payout}(\text{MIS}) = \begin{cases}
0 & \text{MIS} < 60\% \\
\text{Escrow} \times \left(\frac{\text{MIS} - 60}{40}\right)^2 \times 0.90 & 60\% \le \text{MIS} < 90\% \quad \text{(Progressive Quadratic)} \\
\text{Escrow} \times 1.0 & \text{MIS} \ge 90\% \quad \text{(Critical Material Breach)}
\end{cases}$$

---

## ⚙️ Intelligent Contract Interface

### State Modifiers (Write Transactions)
```python
# 1. Initialize funded campaign escrow (min 5 GEN)
create_campaign(campaign_id: str, target_entity: str, category: str, min_materiality_threshold: u256, description: str)

# 2. Add liquidity to an active campaign
topup_campaign(campaign_id: str)

# 3. Submit cryptographic evidence under stealth address
submit_disclosure(disclosure_id: str, campaign_id: str, evidence_hash: str, executive_summary: str, whistleblower_stealth: str)

# 4. Trigger GenLayer Multi-LLM Quorum consensus & regulatory cross-referencing
evaluate_disclosure(disclosure_id: str, regulatory_cross_ref_url: str)

# 5. Non-custodial bounty claim by whistleblower stealth address
claim_bounty(disclosure_id: str)

# 6. Sponsor timeout escape hatch (refund expired campaign)
reclaim_expired_campaign(campaign_id: str)
```

### Protocol Introspection (View Calls)
```python
get_campaign(campaign_id: str) -> dict
get_disclosure(disclosure_id: str) -> dict
get_records(disclosure_id: str) -> list
list_campaigns() -> list
get_protocol_overview() -> dict
```

---

## 🧪 Terminal Verification & Direct Tests

### 1-Click End-to-End Lifecycle Simulation:
```bash
python scripts/e2e_demo.py
```

### Full Pytest Direct-Mode Suite (17/17 Passed):
```bash
.venv/bin/pytest tests/unit/ -v
```

```text
tests/unit/test_sentinel_dao.py::test_initial_protocol_overview PASSED
tests/unit/test_sentinel_dao.py::test_create_campaign_success PASSED
tests/unit/test_sentinel_dao.py::test_create_campaign_below_min_escrow_rejection PASSED
tests/unit/test_sentinel_dao.py::test_create_campaign_invalid_category_rejection PASSED
tests/unit/test_sentinel_dao.py::test_create_campaign_invalid_threshold_rejection PASSED
tests/unit/test_sentinel_dao.py::test_create_all_valid_categories PASSED
tests/unit/test_sentinel_dao.py::test_topup_campaign_success PASSED
tests/unit/test_sentinel_dao.py::test_submit_disclosure_success PASSED
tests/unit/test_sentinel_dao.py::test_submit_disclosure_closed_campaign_rejection PASSED
tests/unit/test_sentinel_dao.py::test_evaluate_disclosure_critical_breach_100_percent_payout PASSED
tests/unit/test_sentinel_dao.py::test_evaluate_disclosure_progressive_payout_75_mis PASSED
tests/unit/test_sentinel_dao.py::test_evaluate_disclosure_low_materiality_insufficient PASSED
tests/unit/test_sentinel_dao.py::test_evaluate_disclosure_rejected_fraudulent PASSED
tests/unit/test_sentinel_dao.py::test_claim_bounty_success PASSED
tests/unit/test_sentinel_dao.py::test_claim_bounty_unauthorized_rejection PASSED
tests/unit/test_sentinel_dao.py::test_reclaim_expired_campaign_success PASSED
tests/unit/test_sentinel_dao.py::test_list_campaigns_and_disclosures PASSED
============================== 17 passed in 0.28s ==============================
```
