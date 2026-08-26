# SentinelDAO Constitution — Whistleblower & ESG / Corporate Fraud Bounty Protocol

## Core Invariants & Governance Principles

### I. Stealth Whistleblower Protection & Non-Custodial Escrow
1. Whistleblowers submit evidence linked to disposable stealth addresses.
2. Bounty escrows deposited by sponsors or DAOs are locked in the contract and CANNOT be unilaterally drained by sponsors while active disclosures are under examination.

### II. Autonomous Forensic Consensus & External Regulatory Feeds
1. Evidence evaluation MUST use GenLayer's non-deterministic multi-LLM quorum (`gl.vm.run_nondet_unsafe`).
2. The consensus engine cross-references disclosures with regulatory and corporate filing databases (SEC EDGAR, EPA enforcement, court registries) via `gl.nondet.web.render`.
3. Forensic evaluation extracts Verifiability ($V$), Severity ($S$), and Documentation Depth ($D$) on a 0-100 scale.

### III. Mathematical Materiality Index ($\text{MIS}$)
1. Payout eligibility requires $\text{MIS} \ge 60$ and $\text{Confidence} \ge 80\%$:
   $$\text{MIS} = \frac{V \times 0.35 + S \times 0.40 + D \times 0.25}{100}$$
2. Payouts follow a progressive quadratic materiality curve to reward high-impact revelations while penalizing trivial submissions.

### IV. GenVM Storage & Deterministic Execution
1. All balances use `u256` atto-precision ($10^{18}$).
2. Storage types MUST use `TreeMap` and `DynArray` with `@allow_storage` dataclasses.
3. 100% compliance with `genvm-lint` rules.
