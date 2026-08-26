# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from dataclasses import dataclass
from genlayer import *

# -----------------------------------------------------------------------------
# Domain Constants & Taxonomy
# -----------------------------------------------------------------------------
CATEGORY_ACCOUNTING_FRAUD = "ACCOUNTING_FRAUD"
CATEGORY_ESG_ENVIRONMENTAL = "ESG_ENVIRONMENTAL"
CATEGORY_INSIDER_TRADING = "INSIDER_TRADING"
CATEGORY_CORRUPTION_BRIBERY = "CORRUPTION_BRIBERY"
CATEGORY_AI_SAFETY_VIOLATION = "AI_SAFETY_VIOLATION"

VALID_CATEGORIES = {
    CATEGORY_ACCOUNTING_FRAUD,
    CATEGORY_ESG_ENVIRONMENTAL,
    CATEGORY_INSIDER_TRADING,
    CATEGORY_CORRUPTION_BRIBERY,
    CATEGORY_AI_SAFETY_VIOLATION,
}

CAMPAIGN_STATUS_OPEN = "OPEN"
CAMPAIGN_STATUS_CLOSED = "CLOSED"
CAMPAIGN_STATUS_DEPLETED = "DEPLETED"

DISCLOSURE_STATUS_PENDING = "PENDING"
DISCLOSURE_STATUS_AWARDED = "VERIFIED_AWARDED"
DISCLOSURE_STATUS_REJECTED = "REJECTED"
DISCLOSURE_STATUS_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

DECISION_VERIFIED = "VERIFIED"
DECISION_REJECTED = "REJECTED"
DECISION_INSUFFICIENT = "INSUFFICIENT"

ATTO = 10**18
MIN_CAMPAIGN_ESCROW = 5 * ATTO   # 5 GEN min campaign escrow
MIN_CONFIDENCE_THRESHOLD = 80     # 80% AI confidence requirement
MIN_MATERIALITY_FLOOR = 60        # Minimum MIS score to receive any payout

ERROR_EXPECTED = "[EXPECTED]"
ERROR_EXTERNAL = "[EXTERNAL]"
ERROR_LLM = "[LLM]"


# -----------------------------------------------------------------------------
# Storage Schemas
# -----------------------------------------------------------------------------
@allow_storage
@dataclass
class CampaignData:
    campaign_id: str
    sponsor: Address
    target_entity: str
    category: str
    escrow_balance_atto: u256
    total_awarded_atto: u256
    min_materiality_threshold: u256
    description: str
    status: str
    registered_seq: u256


@allow_storage
@dataclass
class DisclosureData:
    disclosure_id: str
    campaign_id: str
    whistleblower_stealth: Address
    evidence_hash: str
    executive_summary: str
    status: str
    verifiability_score: u256
    severity_score: u256
    documentation_depth: u256
    materiality_index: u256
    confidence: u256
    awarded_bounty_atto: u256
    is_claimed: bool
    registered_seq: u256


@allow_storage
@dataclass
class ForensicAuditRecord:
    disclosure_id: str
    auditor_decision: str
    materiality_index: u256
    confidence: u256
    rationale: str
    regulatory_feed_summary: str
    timestamp_seq: u256


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


# -----------------------------------------------------------------------------
# Intelligent Contract Interface
# -----------------------------------------------------------------------------
class SentinelDAO(gl.Contract):
    owner: Address
    regulatory_oracle_base: str

    total_bounties_funded: u256
    total_bounties_paid: u256

    # Campaigns: campaign_id -> CampaignData
    campaigns: TreeMap[str, CampaignData]
    campaign_ids: DynArray[str]

    # Disclosures: disclosure_id -> DisclosureData
    disclosures: TreeMap[str, DisclosureData]
    disclosure_ids: DynArray[str]

    # Global Forensic Audit Trail
    records: DynArray[ForensicAuditRecord]

    def __init__(self, regulatory_oracle_base: str = "https://api.sentineldao.regulatory/v1/sec-epa"):
        self.owner = gl.message.sender_address
        self.regulatory_oracle_base = regulatory_oracle_base
        self.total_bounties_funded = u256(0)
        self.total_bounties_paid = u256(0)

    # ------------------------------------------------------------------
    # 1. Campaign Creation & Funding
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def create_campaign(
        self,
        campaign_id: str,
        target_entity: str,
        category: str,
        min_materiality_threshold: u256,
        description: str,
    ) -> None:
        if not campaign_id or len(campaign_id.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign ID cannot be empty")
        if campaign_id in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} already exists")
        if not target_entity or len(target_entity.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Target entity cannot be empty")
        if category not in VALID_CATEGORIES:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid category: {category}")

        escrow = int(gl.message.value)
        if escrow < int(MIN_CAMPAIGN_ESCROW):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Minimum campaign escrow is 5 GEN")

        thresh = int(min_materiality_threshold)
        if thresh < MIN_MATERIALITY_FLOOR or thresh > 100:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Materiality threshold must be between 60 and 100")

        seq = u256(len(self.campaign_ids) + 1)
        camp = CampaignData(
            campaign_id=campaign_id,
            sponsor=gl.message.sender_address,
            target_entity=target_entity,
            category=category,
            escrow_balance_atto=u256(escrow),
            total_awarded_atto=u256(0),
            min_materiality_threshold=min_materiality_threshold,
            description=description,
            status=CAMPAIGN_STATUS_OPEN,
            registered_seq=seq,
        )

        self.campaigns[campaign_id] = camp
        self.campaign_ids.append(campaign_id)
        self.total_bounties_funded = u256(int(self.total_bounties_funded) + escrow)

    @gl.public.write.payable
    def topup_campaign(self, campaign_id: str) -> None:
        if campaign_id not in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} not found")

        val = int(gl.message.value)
        if val <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Top-up amount must be greater than zero")

        camp = self.campaigns[campaign_id]
        if camp.status == CAMPAIGN_STATUS_CLOSED:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Cannot top-up a CLOSED campaign")

        camp.escrow_balance_atto = u256(int(camp.escrow_balance_atto) + val)
        if camp.status == CAMPAIGN_STATUS_DEPLETED:
            camp.status = CAMPAIGN_STATUS_OPEN

        self.campaigns[campaign_id] = camp
        self.total_bounties_funded = u256(int(self.total_bounties_funded) + val)

    # ------------------------------------------------------------------
    # 2. Whistleblower Disclosure Submission
    # ------------------------------------------------------------------
    @gl.public.write
    def submit_disclosure(
        self,
        disclosure_id: str,
        campaign_id: str,
        evidence_hash: str,
        executive_summary: str,
        whistleblower_stealth: Address,
    ) -> None:
        stealth_addr = Address(whistleblower_stealth) if not isinstance(whistleblower_stealth, Address) else whistleblower_stealth
        if not disclosure_id or len(disclosure_id.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure ID cannot be empty")
        if disclosure_id in self.disclosures:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure {disclosure_id} already registered")
        if campaign_id not in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} not found")

        camp = self.campaigns[campaign_id]
        if camp.status != CAMPAIGN_STATUS_OPEN:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} is not OPEN (status: {camp.status})")

        seq = u256(len(self.disclosure_ids) + 1)
        disc = DisclosureData(
            disclosure_id=disclosure_id,
            campaign_id=campaign_id,
            whistleblower_stealth=stealth_addr,
            evidence_hash=evidence_hash,
            executive_summary=executive_summary,
            status=DISCLOSURE_STATUS_PENDING,
            verifiability_score=u256(0),
            severity_score=u256(0),
            documentation_depth=u256(0),
            materiality_index=u256(0),
            confidence=u256(0),
            awarded_bounty_atto=u256(0),
            is_claimed=False,
            registered_seq=seq,
        )

        self.disclosures[disclosure_id] = disc
        self.disclosure_ids.append(disclosure_id)

    # ------------------------------------------------------------------
    # 3. Autonomous Forensic AI Consensus Evaluation
    # ------------------------------------------------------------------
    @gl.public.write
    def evaluate_disclosure(
        self,
        disclosure_id: str,
        technical_evidence: str,
        regulatory_cross_ref_url: str = "",
    ) -> None:
        if disclosure_id not in self.disclosures:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure {disclosure_id} not found")

        disc = self.disclosures[disclosure_id]
        if disc.status != DISCLOSURE_STATUS_PENDING:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure {disclosure_id} is not PENDING")

        camp = self.campaigns[disc.campaign_id]
        oracle_url = regulatory_cross_ref_url if regulatory_cross_ref_url else f"{self.regulatory_oracle_base}?entity={camp.target_entity}"

        audit_res = self._evaluate_forensic_consensus(
            target_entity=camp.target_entity,
            category=camp.category,
            summary=disc.executive_summary,
            evidence=technical_evidence,
            oracle_url=oracle_url,
        )

        decision = str(audit_res.get("decision", DECISION_INSUFFICIENT))
        confidence = int(audit_res.get("confidence", 70))
        v_score = int(audit_res.get("verifiability", 60))
        s_score = int(audit_res.get("severity", 60))
        d_score = int(audit_res.get("documentation_depth", 60))
        mis = int(audit_res.get("materiality_index", 60))
        rationale = str(audit_res.get("rationale", "Forensic analysis completed."))
        feed_summary = str(audit_res.get("regulatory_feed_summary", "Regulatory feed cross-referenced."))

        # Compute Bounty Award
        escrow = int(camp.escrow_balance_atto)
        target_thresh = int(camp.min_materiality_threshold)
        bounty = 0

        if decision == DECISION_VERIFIED and confidence >= MIN_CONFIDENCE_THRESHOLD and mis >= target_thresh:
            if mis >= 90:
                # 100% of escrow for critical breaches (capped at escrow balance)
                bounty = escrow
            else:
                # Progressive quadratic scaling: Escrow * ((MIS - 60) / 40)^2 * 0.90
                scale_num = (mis - 60) ** 2
                scale_den = 40 ** 2
                bounty = (escrow * scale_num * 90) // (scale_den * 100)
                bounty = min(escrow, max(0, bounty))

            disc.status = DISCLOSURE_STATUS_AWARDED
            camp.escrow_balance_atto = u256(escrow - bounty)
            camp.total_awarded_atto = u256(int(camp.total_awarded_atto) + bounty)
            if int(camp.escrow_balance_atto) == 0:
                camp.status = CAMPAIGN_STATUS_DEPLETED
        elif decision == DECISION_REJECTED:
            disc.status = DISCLOSURE_STATUS_REJECTED
        else:
            disc.status = DISCLOSURE_STATUS_INSUFFICIENT

        disc.verifiability_score = u256(v_score)
        disc.severity_score = u256(s_score)
        disc.documentation_depth = u256(d_score)
        disc.materiality_index = u256(mis)
        disc.confidence = u256(confidence)
        disc.awarded_bounty_atto = u256(bounty)

        self.disclosures[disclosure_id] = disc
        self.campaigns[disc.campaign_id] = camp

        rec = ForensicAuditRecord(
            disclosure_id=disclosure_id,
            auditor_decision=decision,
            materiality_index=u256(mis),
            confidence=u256(confidence),
            rationale=rationale,
            regulatory_feed_summary=feed_summary,
            timestamp_seq=u256(len(self.records) + 1),
        )
        self.records.append(rec)

    def _evaluate_forensic_consensus(
        self,
        target_entity: str,
        category: str,
        summary: str,
        evidence: str,
        oracle_url: str,
    ) -> dict:
        def leader_fn() -> dict:
            reg_summary = "Regulatory filings clean: no pre-existing enforcement action."
            try:
                web_res = gl.nondet.web.render(oracle_url, mode="text")
                if web_res.status == 200 and web_res.body:
                    reg_summary = f"Regulatory record: {web_res.body[:180]}"
            except Exception:
                reg_summary = "Direct whistleblower documentary review."

            prompt = (
                "You are a Senior Corporate Fraud Investigator and Forensic Auditor. "
                f"Target Entity: {target_entity}. Category: {category}. "
                f"Executive Summary: {summary}. "
                f"Evidence Documentation: {evidence}. "
                f"Regulatory Baseline: {reg_summary}. "
                'Respond with strict JSON: {"decision": "VERIFIED" | "REJECTED" | "INSUFFICIENT", '
                '"confidence": <int 0-100>, "verifiability": <int 0-100>, '
                '"severity": <int 0-100>, "documentation_depth": <int 0-100>, '
                '"rationale": "<summary>"}'
            )

            res = _run_forensic_llm(prompt)
            res["regulatory_feed_summary"] = reg_summary[:256]
            return res

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return _handle_forensic_leader_error(leaders_res, leader_fn)
            try:
                v_res = leader_fn()
                leader = leaders_res.calldata
                if not isinstance(leader, dict):
                    return False
                if leader.get("decision") != v_res.get("decision"):
                    return False
                
                mis_diff = abs(int(v_res.get("materiality_index", 0)) - int(leader.get("materiality_index", 0)))
                return mis_diff <= 15
            except Exception:
                return False

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ------------------------------------------------------------------
    # 4. Bounty Claim Execution
    # ------------------------------------------------------------------
    @gl.public.write
    def claim_bounty(self, disclosure_id: str) -> None:
        if disclosure_id not in self.disclosures:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure {disclosure_id} not found")

        disc = self.disclosures[disclosure_id]
        if disc.status != DISCLOSURE_STATUS_AWARDED:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure is not VERIFIED_AWARDED")
        if disc.is_claimed:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Bounty has already been claimed")

        sender = gl.message.sender_address
        if sender != disc.whistleblower_stealth and sender != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only whistleblower stealth address can claim")

        bounty = int(disc.awarded_bounty_atto)
        disc.is_claimed = True
        self.disclosures[disclosure_id] = disc
        self.total_bounties_paid = u256(int(self.total_bounties_paid) + bounty)

        _Recipient(disc.whistleblower_stealth).emit_transfer(value=u256(bounty), on="finalized")

    # ------------------------------------------------------------------
    # 5. Campaign Closure
    # ------------------------------------------------------------------
    @gl.public.write
    def close_campaign(self, campaign_id: str) -> None:
        if campaign_id not in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} not found")

        camp = self.campaigns[campaign_id]
        sender = gl.message.sender_address
        if sender != camp.sponsor and sender != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only sponsor or owner can close campaign")
        if camp.status == CAMPAIGN_STATUS_CLOSED:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign is already closed")

        rem = int(camp.escrow_balance_atto)
        camp.status = CAMPAIGN_STATUS_CLOSED
        camp.escrow_balance_atto = u256(0)
        self.campaigns[campaign_id] = camp

        if rem > 0:
            _Recipient(camp.sponsor).emit_transfer(value=u256(rem), on="finalized")

    # ------------------------------------------------------------------
    # 6. View Methods & Protocol Overview
    # ------------------------------------------------------------------
    @gl.public.view
    def get_campaign(self, campaign_id: str) -> dict:
        if campaign_id not in self.campaigns:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Campaign {campaign_id} not found")
        camp = self.campaigns[campaign_id]
        return {
            "campaign_id": camp.campaign_id,
            "sponsor": camp.sponsor.as_hex,
            "target_entity": camp.target_entity,
            "category": camp.category,
            "escrow_balance_atto": str(int(camp.escrow_balance_atto)),
            "total_awarded_atto": str(int(camp.total_awarded_atto)),
            "min_materiality_threshold": int(camp.min_materiality_threshold),
            "description": camp.description,
            "status": camp.status,
            "registered_seq": int(camp.registered_seq),
        }

    @gl.public.view
    def get_disclosure(self, disclosure_id: str) -> dict:
        if disclosure_id not in self.disclosures:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Disclosure {disclosure_id} not found")
        disc = self.disclosures[disclosure_id]
        return {
            "disclosure_id": disc.disclosure_id,
            "campaign_id": disc.campaign_id,
            "whistleblower_stealth": disc.whistleblower_stealth.as_hex,
            "evidence_hash": disc.evidence_hash,
            "executive_summary": disc.executive_summary,
            "status": disc.status,
            "verifiability_score": int(disc.verifiability_score),
            "severity_score": int(disc.severity_score),
            "documentation_depth": int(disc.documentation_depth),
            "materiality_index": int(disc.materiality_index),
            "confidence": int(disc.confidence),
            "awarded_bounty_atto": str(int(disc.awarded_bounty_atto)),
            "is_claimed": disc.is_claimed,
            "registered_seq": int(disc.registered_seq),
        }

    @gl.public.view
    def get_records(self, disclosure_id: str) -> list:
        out = []
        for r in self.records:
            if r.disclosure_id == disclosure_id:
                out.append({
                    "auditor_decision": r.auditor_decision,
                    "materiality_index": int(r.materiality_index),
                    "confidence": int(r.confidence),
                    "rationale": r.rationale,
                    "regulatory_feed_summary": r.regulatory_feed_summary,
                    "timestamp_seq": int(r.timestamp_seq),
                })
        return out

    @gl.public.view
    def list_campaigns(self) -> list:
        out = []
        for cid in self.challenge_campaign_ids():
            out.append(self.get_campaign(cid))
        return out

    def challenge_campaign_ids(self) -> list:
        out = []
        for c in self.campaign_ids:
            out.append(c)
        return out

    @gl.public.view
    def list_disclosures(self, campaign_id: str) -> list:
        out = []
        for did in self.disclosure_ids:
            disc = self.disclosures[did]
            if disc.campaign_id == campaign_id:
                out.append(self.get_disclosure(did))
        return out

    @gl.public.view
    def get_protocol_overview(self) -> dict:
        return {
            "owner": self.owner.as_hex,
            "regulatory_oracle_base": self.regulatory_oracle_base,
            "total_campaigns": len(self.campaign_ids),
            "total_disclosures": len(self.disclosure_ids),
            "total_audits": len(self.records),
            "total_bounties_funded": str(int(self.total_bounties_funded)),
            "total_bounties_paid": str(int(self.total_bounties_paid)),
        }


# --- Internal Helpers -----------------------------------------------------
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

    raw_dec = str(parsed.get("decision", DECISION_INSUFFICIENT)).strip().upper()
    if raw_dec in ("VERIFIED", "VALID", "CONFIRMED", "APPROVED"):
        decision = DECISION_VERIFIED
    elif raw_dec in ("REJECTED", "FRAUDULENT", "DISMISSED"):
        decision = DECISION_REJECTED
    else:
        decision = DECISION_INSUFFICIENT

    confidence = max(0, min(100, int(parsed.get("confidence", 75))))
    v_score = max(0, min(100, int(parsed.get("verifiability", 70))))
    s_score = max(0, min(100, int(parsed.get("severity", 70))))
    d_score = max(0, min(100, int(parsed.get("documentation_depth", 70))))
    rationale = str(parsed.get("rationale", "Forensic examination completed."))[:300]

    # Calculate Materiality Index: MIS = V * 0.35 + S * 0.40 + D * 0.25
    mis = int((v_score * 0.35) + (s_score * 0.40) + (d_score * 0.25))
    mis = max(0, min(100, mis))

    return {
        "decision": decision,
        "confidence": confidence,
        "verifiability": v_score,
        "severity": s_score,
        "documentation_depth": d_score,
        "materiality_index": mis,
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
