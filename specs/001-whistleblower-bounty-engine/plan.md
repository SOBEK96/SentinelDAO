# Implementation Plan: SentinelDAO

## Architecture
1. **Contract**: `contracts/sentinel_dao.py`
   - Inherits `gl.Contract`.
   - Methods: 12 (6 Write, 6 View).
2. **Consensus**:
   - `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`.
   - `leader_fn`: Ingests regulatory SEC/EPA feed, evaluates evidence with Multi-LLM forensic prompt.
   - `validator_fn`: Verifies $\text{MIS}$ score parity within $\pm 15$ points.
3. **Test Suite**:
   - `contracts/test/test_sentinel_dao.py` with 20+ direct-mode tests.
