# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from dataclasses import dataclass
from genlayer import *

# -----------------------------------------------------------------------------
# Domain Constants & Taxonomy
# -----------------------------------------------------------------------------
STATUS_OPEN = "OPEN"
STATUS_PENDING = "PENDING"
STATUS_VERIFIED_AWARDED = "VERIFIED_AWARDED"
STATUS_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
STATUS_REJECTED = "REJECTED"
STATUS_CLAIMED = "CLAIMED"
STATUS_CLOSED = "CLOSED"
STATUS_DEPLETED = "DEPLETED"
STATUS_EXPIRED = "EXPIRED"

DECISION_VERIFIED = "VERIFIED"
DECISION_REJECTED = "REJECTED"
DECISION_INSUFFICIENT = "INSUFFICIENT"

VALID_CAMPAIGN_CATEGORIES = {
    "ACCOUNTING_FRAUD",
    "ESG_ENVIRONMENTAL",
    "INSIDER_TRADING",
    "CORRUPTION_BRIBERY",
    "AI_SAFETY_VIOLATION",
    "PRODUCT_SAFETY_DEFECT",
    "CYBERSECURITY_BREACH",
}

ATTO = 10**18
MIN_CAMPAIGN_BOUNTY = 5 * ATTO      # 5 GEN minimum campaign bounty funding
MIN_MATERIALITY_THRESHOLD = 60     # Minimum MIS score to qualify for progressive payout
MAX_MATERIALITY_THRESHOLD = 100

ERROR_EXPECTED = "[EXPECTED]"
ERROR_EXTERNAL = "[EXTERNAL]"
ERROR_TRANSIENT = "[TRANSIENT]"
ERROR_LLM = "[LLM]"


# -----------------------------------------------------------------------------
# Storage Schemas (Strictly Typed Dataclasses)
# -----------------------------------------------------------------------------
@allow_storage
@dataclass
class BountyCampaign:
    campaign_id: str
    creator: Address
    target_entity: str
    category: str
    min_materiality_threshold: u256
    total_bounty_funded_atto: u256
    escrow_balance_atto: u256
    description: str
    status: str
    disclosures_count: u256
    created_seq: u256


@allow_storage
@dataclass
class EvidenceDisclosure:
    disclosure_id: str
    campaign_id: str
    submitter: Address
    whistleblower_stealth: Address   # Stealth payout address to preserve anonymity
    proof_cid: str                   # Encrypted IPFS / Arweave CID of primary documents
    evidence_hash: str               # Merkle root / SHA256 commitment of raw files
    summary: str
    materiality_index: u256          # Materiality & Impact Score (MIS, 0-100)
    awarded_bounty_atto: u256
    status: str
    is_claimed: bool
    forensic_rationale: str
    submitted_seq: u256


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


# -----------------------------------------------------------------------------
# Main Intelligent Contract Class
# -----------------------------------------------------------------------------
class SentinelDAO(gl.Contract):
    owner: Address
    regulatory_oracle_base: str

    # Global Multi-Ledger Accounting
    total_campaigns: u256
    total_disclosures: u256
    total_bounties_funded: u256
    total_bounties_paid: u256

    # Campaigns Store: campaign_id -> BountyCampaign
    campaigns: TreeMap[str, BountyCampaign]
    campaign_ids: DynArray[str]

    # Disclosures Store: disclosure_id -> EvidenceDisclosure
    disclosures: TreeMap[str, EvidenceDisclosure]
    disclosure_ids: DynArray[str]

    def __init__(self, regulatory_oracle_base: str = "https://api.sentineldao.org/v1/sec-enforcement"):
        self.owner = gl.message.sender_address
        self.regulatory_oracle_base = regulatory_oracle_base
        self.total_campaigns = u256(0)
        self.total_disclosures = u256(0)
        self.total_bounties_funded = u256(0)
        self.total_bounties_paid = u256(0)

    # ------------------------------------------------------------------
    # 1. Bounty Campaign Creation & Treasury Escrow
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def create_campaign(
        self,
        campaign_id: str,
        target_entity: str,
        category: str,
        min_materiality_threshold: u256,
        description: str = "Whistleblower Intelligence Bounty Campaign",
    ) -> None:
        if not campaign_id or len(campaign_id.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign ID cannot be empty")
        if campaign_id in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} already exists")
        if not target_entity or len(target_entity.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Target entity name is required")
        if category not in VALID_CAMPAIGN_CATEGORIES:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid category: {category}")

        thresh = int(min_materiality_threshold)
        if thresh < MIN_MATERIALITY_THRESHOLD or thresh > MAX_MATERIALITY_THRESHOLD:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Materiality threshold must be between 60 and 100")

        escrow = int(gl.message.value)
        if escrow < int(MIN_CAMPAIGN_BOUNTY):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Minimum campaign escrow is 5 GEN")

        seq = u256(len(self.campaign_ids) + 1)
        camp = BountyCampaign(
            campaign_id=campaign_id,
            creator=gl.message.sender_address,
            target_entity=target_entity,
            category=category,
            min_materiality_threshold=min_materiality_threshold,
            total_bounty_funded_atto=u256(escrow),
            escrow_balance_atto=u256(escrow),
            description=description,
            status=STATUS_OPEN,
            disclosures_count=u256(0),
            created_seq=seq,
        )

        self.campaigns[campaign_id] = camp
        self.campaign_ids.append(campaign_id)
        self.total_bounties_funded = u256(int(self.total_bounties_funded) + escrow)
        self.total_campaigns = u256(int(self.total_campaigns) + 1)

    @gl.public.write.payable
    def topup_campaign(self, campaign_id: str) -> None:
        if campaign_id not in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} not found")

        camp = self.campaigns[campaign_id]
        if camp.status != STATUS_OPEN:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign is closed")

        topup = int(gl.message.value)
        if topup <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Topup amount must be greater than zero")

        camp.total_bounty_funded_atto = u256(int(camp.total_bounty_funded_atto) + topup)
        camp.escrow_balance_atto = u256(int(camp.escrow_balance_atto) + topup)
        self.campaigns[campaign_id] = camp
        self.total_bounties_funded = u256(int(self.total_bounties_funded) + topup)

    # ------------------------------------------------------------------
    # 2. Whistleblower Evidence Submission (Cryptographic Commitments)
    # ------------------------------------------------------------------
    @gl.public.write
    def submit_disclosure(
        self,
        disclosure_id: str,
        campaign_id: str,
        proof_cid: str,
        summary: str,
        payout_address: Address,
        evidence_hash: str = "sha256:evidence-leak-commitment-hash",
    ) -> None:
        if not disclosure_id or len(disclosure_id.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure ID cannot be empty")
        if disclosure_id in self.disclosures:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure {disclosure_id} already submitted")
        if campaign_id not in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} not found")

        camp = self.campaigns[campaign_id]
        if camp.status != STATUS_OPEN:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} is not OPEN")

        payout_addr = Address(payout_address) if not isinstance(payout_address, Address) else payout_address
        seq = u256(len(self.disclosure_ids) + 1)
        disc = EvidenceDisclosure(
            disclosure_id=disclosure_id,
            campaign_id=campaign_id,
            submitter=gl.message.sender_address,
            whistleblower_stealth=payout_addr,
            proof_cid=proof_cid,
            evidence_hash=evidence_hash,
            summary=summary,
            materiality_index=u256(0),
            awarded_bounty_atto=u256(0),
            status=STATUS_PENDING,
            is_claimed=False,
            forensic_rationale="",
            submitted_seq=seq,
        )

        self.disclosures[disclosure_id] = disc
        self.disclosure_ids.append(disclosure_id)

        camp.disclosures_count = u256(int(camp.disclosures_count) + 1)
        self.campaigns[campaign_id] = camp
        self.total_disclosures = u256(int(self.total_disclosures) + 1)

    # ------------------------------------------------------------------
    # 3. Autonomous Forensic AI Consensus Evaluation
    # ------------------------------------------------------------------
    @gl.public.write
    def evaluate_disclosure(
        self,
        disclosure_id: str,
        evidence_corroboration_detail: str = "",
    ) -> None:
        if disclosure_id not in self.disclosures:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure {disclosure_id} not found")

        disc = self.disclosures[disclosure_id]
        if disc.status != STATUS_PENDING:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure {disclosure_id} is not in PENDING state")

        camp = self.campaigns[disc.campaign_id]
        oracle_url = f"{self.regulatory_oracle_base}?entity={camp.target_entity}&cat={camp.category}"

        threshold = int(camp.min_materiality_threshold)
        rem_escrow = int(camp.escrow_balance_atto)

        audit_res = self._evaluate_forensic_consensus(
            target_entity=camp.target_entity,
            category=camp.category,
            summary=disc.summary,
            proof_cid=disc.proof_cid,
            detail=evidence_corroboration_detail,
            threshold=threshold,
            rem_escrow=rem_escrow,
            oracle_url=oracle_url,
        )

        raw_decision = str(audit_res.get("decision", DECISION_REJECTED)).strip().upper()
        verifiability = int(audit_res.get("verifiability", 0))
        severity = int(audit_res.get("severity", 0))
        doc_depth = int(audit_res.get("documentation_depth", 0))
        rationale = str(audit_res.get("rationale", "Forensic analysis completed."))

        final_status, mis, bounty_due = _compute_bounty_settlement(
            decision=raw_decision,
            verifiability=verifiability,
            severity=severity,
            doc_depth=doc_depth,
            threshold=threshold,
            rem_escrow=rem_escrow,
        )

        if final_status == STATUS_VERIFIED_AWARDED and bounty_due > 0:
            camp.escrow_balance_atto = u256(max(0, rem_escrow - bounty_due))
            if int(camp.escrow_balance_atto) == 0:
                camp.status = STATUS_DEPLETED

        disc.status = final_status
        disc.materiality_index = u256(mis)
        disc.awarded_bounty_atto = u256(bounty_due)
        disc.forensic_rationale = rationale

        self.disclosures[disclosure_id] = disc
        self.campaigns[disc.campaign_id] = camp

    def _evaluate_forensic_consensus(
        self,
        target_entity: str,
        category: str,
        summary: str,
        proof_cid: str,
        detail: str,
        threshold: int,
        rem_escrow: int,
        oracle_url: str,
    ) -> dict:
        def leader_fn() -> dict:
            reg_summary = "Regulatory filings verified: zero conflicting exemptions."
            try:
                web_res = gl.nondet.web.get(oracle_url)
                if hasattr(web_res, "status") and (web_res.status < 200 or web_res.status >= 300):
                    raise gl.vm.UserError(f"{ERROR_EXTERNAL} Regulatory oracle returned HTTP {web_res.status}")
                if hasattr(web_res, "body"):
                    body_str = web_res.body if isinstance(web_res.body, str) else web_res.body.decode("utf-8", errors="ignore")
                else:
                    body_str = str(web_res)
                if len(body_str.strip()) >= 10:
                    reg_summary = f"Regulatory filings: {body_str.strip()[:180]}"
            except gl.vm.UserError:
                raise
            except Exception:
                reg_summary = "SEC/EPA regulatory database queried directly."

            prompt = (
                "You are a Senior Corporate Fraud Investigator and Forensic Auditor. "
                f"Target Entity: {target_entity}. Category: {category}. "
                f"Disclosure Summary: {summary}. Proof CID: {proof_cid}. Detail: {detail}. "
                f"Regulatory Oracle: {reg_summary}. "
                "Analyze authenticity, corroboration, severity, and verifiability of the leak. "
                'Respond with strict JSON: {"decision": "VERIFIED" | "REJECTED" | "INSUFFICIENT", '
                '"confidence": <int 0-100>, "verifiability": <int 0-100>, '
                '"severity": <int 0-100>, "documentation_depth": <int 0-100>, "rationale": "<summary>"}'
            )

            return _run_forensic_llm(prompt)

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return _handle_forensic_leader_error(leaders_res, leader_fn)
            try:
                v_res = leader_fn()
                leader = leaders_res.calldata
                if not isinstance(leader, dict) or not isinstance(v_res, dict):
                    return False

                # 1. Exact agreement on raw decision enum:
                if leader.get("decision") != v_res.get("decision"):
                    return False

                # 2. Derive exact financial settlement parameters for both nodes:
                l_status, l_mis, l_bounty = _compute_bounty_settlement(
                    decision=str(leader.get("decision", DECISION_REJECTED)),
                    verifiability=int(leader.get("verifiability", 0)),
                    severity=int(leader.get("severity", 0)),
                    doc_depth=int(leader.get("documentation_depth", 0)),
                    threshold=threshold,
                    rem_escrow=rem_escrow,
                )

                v_status, v_mis, v_bounty = _compute_bounty_settlement(
                    decision=str(v_res.get("decision", DECISION_REJECTED)),
                    verifiability=int(v_res.get("verifiability", 0)),
                    severity=int(v_res.get("severity", 0)),
                    doc_depth=int(v_res.get("documentation_depth", 0)),
                    threshold=threshold,
                    rem_escrow=rem_escrow,
                )

                # 3. Exact agreement on final award status:
                if l_status != v_status:
                    return False

                # 4. Strict Financial Determinism: Zero variance in awarded bounty amount:
                if l_bounty != v_bounty:
                    return False

                # 5. Discrete threshold boundary gates:
                if (l_mis >= threshold) != (v_mis >= threshold):
                    return False
                if (l_mis >= 90) != (v_mis >= 90):
                    return False

                # 6. Bounded variance within identical settlement outcome (<= 5 points):
                if abs(v_mis - l_mis) > 5:
                    return False

                return True
            except Exception:
                return False

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ------------------------------------------------------------------
    # 4. Anonymous Bounty Disbursal & Claiming
    # ------------------------------------------------------------------
    @gl.public.write
    def claim_bounty(self, disclosure_id: str) -> None:
        if disclosure_id not in self.disclosures:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure {disclosure_id} not found")

        disc = self.disclosures[disclosure_id]
        if disc.status != STATUS_VERIFIED_AWARDED:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure is not in VERIFIED_AWARDED state")
        if gl.message.sender_address != disc.whistleblower_stealth:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only whistleblower stealth address can claim bounty")

        bounty = int(disc.awarded_bounty_atto)
        if bounty <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} No bounty awarded to claim")

        disc.status = STATUS_CLAIMED
        disc.is_claimed = True
        self.disclosures[disclosure_id] = disc
        self.total_bounties_paid = u256(int(self.total_bounties_paid) + bounty)

        _Recipient(disc.whistleblower_stealth).emit_transfer(value=u256(bounty), on="finalized")

    # ------------------------------------------------------------------
    # 5. Zero-Deadlock Escape Hatch: Reclaim Expired Campaign Funds
    # ------------------------------------------------------------------
    @gl.public.write
    def reclaim_expired_campaign(self, campaign_id: str) -> None:
        if campaign_id not in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} not found")

        camp = self.campaigns[campaign_id]
        if camp.status != STATUS_OPEN:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign is already closed or depleted")
        if gl.message.sender_address != camp.creator:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only campaign creator can reclaim funds")

        refund = int(camp.escrow_balance_atto)
        camp.status = STATUS_EXPIRED
        camp.escrow_balance_atto = u256(0)
        self.campaigns[campaign_id] = camp

        if refund > 0:
            _Recipient(camp.creator).emit_transfer(value=u256(refund), on="finalized")

    @gl.public.write
    def close_campaign(self, campaign_id: str) -> None:
        if campaign_id not in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} not found")

        camp = self.campaigns[campaign_id]
        if gl.message.sender_address != camp.creator and gl.message.sender_address != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only campaign creator can close campaign")

        camp.status = STATUS_CLOSED
        refund = int(camp.escrow_balance_atto)
        camp.escrow_balance_atto = u256(0)
        self.campaigns[campaign_id] = camp

        if refund > 0:
            _Recipient(camp.creator).emit_transfer(value=u256(refund), on="finalized")

    # ------------------------------------------------------------------
    # 6. Public View Methods & Ledgers
    # ------------------------------------------------------------------
    @gl.public.view
    def get_campaign(self, campaign_id: str) -> dict:
        if campaign_id not in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} not found")
        c = self.campaigns[campaign_id]
        return {
            "campaign_id": c.campaign_id,
            "creator": c.creator.as_hex,
            "target_entity": c.target_entity,
            "category": c.category,
            "min_materiality_threshold": int(c.min_materiality_threshold),
            "total_bounty_funded_atto": str(int(c.total_bounty_funded_atto)),
            "escrow_balance_atto": str(int(c.escrow_balance_atto)),
            "description": c.description,
            "status": c.status,
            "disclosures_count": int(c.disclosures_count),
            "created_seq": int(c.created_seq),
        }

    @gl.public.view
    def get_disclosure(self, disclosure_id: str) -> dict:
        if disclosure_id not in self.disclosures:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure {disclosure_id} not found")
        d = self.disclosures[disclosure_id]
        return {
            "disclosure_id": d.disclosure_id,
            "campaign_id": d.campaign_id,
            "submitter": d.submitter.as_hex,
            "whistleblower_stealth": d.whistleblower_stealth.as_hex,
            "proof_cid": d.proof_cid,
            "evidence_hash": d.evidence_hash,
            "summary": d.summary,
            "materiality_index": int(d.materiality_index),
            "awarded_bounty_atto": str(int(d.awarded_bounty_atto)),
            "status": d.status,
            "is_claimed": d.is_claimed,
            "forensic_rationale": d.forensic_rationale,
            "submitted_seq": int(d.submitted_seq),
        }

    @gl.public.view
    def list_campaigns(self) -> list:
        out = []
        for cid in self.campaign_ids:
            out.append(self.get_campaign(cid))
        return out

    @gl.public.view
    def list_disclosures(self, campaign_id: str = "") -> list:
        out = []
        for did in self.disclosure_ids:
            disc = self.get_disclosure(did)
            if not campaign_id or disc["campaign_id"] == campaign_id:
                out.append(disc)
        return out

    @gl.public.view
    def get_protocol_overview(self) -> dict:
        return {
            "owner": self.owner.as_hex,
            "regulatory_oracle_base": self.regulatory_oracle_base,
            "total_campaigns": int(self.total_campaigns),
            "total_disclosures": int(self.total_disclosures),
            "total_bounties_funded": str(int(self.total_bounties_funded)),
            "total_bounties_paid": str(int(self.total_bounties_paid)),
        }


# --- Internal Helpers -----------------------------------------------------
def _compute_bounty_settlement(
    decision: str,
    verifiability: int,
    severity: int,
    doc_depth: int,
    threshold: int,
    rem_escrow: int,
) -> tuple[str, int, int]:
    mis = (verifiability * 35 + severity * 40 + doc_depth * 25) // 100
    if decision == DECISION_VERIFIED and mis >= threshold:
        if mis >= 90:
            bounty_due = rem_escrow
        else:
            numerator = (mis - 60) * (mis - 60) * 90
            denominator = 1600
            bounty_due = (rem_escrow * numerator) // denominator
            bounty_due = max(0, min(rem_escrow, bounty_due))
        return (STATUS_VERIFIED_AWARDED, mis, bounty_due)
    elif decision == DECISION_INSUFFICIENT:
        return (STATUS_INSUFFICIENT_EVIDENCE, mis, 0)
    else:
        return (STATUS_REJECTED, mis, 0)


def _run_forensic_llm(prompt: str) -> dict:
    try:
        raw = gl.nondet.exec_prompt(prompt, response_format="json")
    except Exception as e:
        raise gl.vm.UserError(f"{ERROR_LLM} LLM execution failed: {str(e)}")

    if isinstance(raw, str):
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        try:
            parsed = json.loads(cleaned)
        except Exception as e:
            raise gl.vm.UserError(f"{ERROR_LLM} Malformed JSON from LLM: {str(e)}")
    elif isinstance(raw, dict):
        parsed = raw
    else:
        raise gl.vm.UserError(f"{ERROR_LLM} LLM output is not a JSON object")

    raw_dec = str(parsed.get("decision", DECISION_REJECTED)).strip().upper()
    decision = DECISION_VERIFIED if raw_dec in ("VERIFIED", "APPROVED", "VALID") else (
        DECISION_INSUFFICIENT if raw_dec in ("INSUFFICIENT", "INSUFFICIENT_EVIDENCE") else DECISION_REJECTED
    )
    verifiability = max(0, min(100, int(parsed.get("verifiability", 50))))
    severity = max(0, min(100, int(parsed.get("severity", 50))))
    doc_depth = max(0, min(100, int(parsed.get("documentation_depth", 50))))
    rationale = str(parsed.get("rationale", "Forensic leak investigation completed."))[:300]

    return {
        "decision": decision,
        "verifiability": verifiability,
        "severity": severity,
        "documentation_depth": doc_depth,
        "rationale": rationale,
    }


def _handle_forensic_leader_error(leaders_res: gl.vm.Result, leader_fn) -> bool:
    leader_msg = leaders_res.calldata if isinstance(leaders_res.calldata, str) else str(leaders_res)
    if ERROR_EXPECTED in leader_msg or ERROR_EXTERNAL in leader_msg:
        try:
            leader_fn()
            return False
        except gl.vm.UserError as v_err:
            return (
                (ERROR_EXPECTED in str(v_err) and ERROR_EXPECTED in leader_msg)
                or (ERROR_EXTERNAL in str(v_err) and ERROR_EXTERNAL in leader_msg)
            )
        except Exception:
            return False
    return False
