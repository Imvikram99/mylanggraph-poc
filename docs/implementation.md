# Implementation Planning Playbook

Codify Phase 3 expectations so the workflow can turn reviewer-approved plans into actionable execution milestones.

## Phase Template

Each feature plan should include the following sections per phase:

| Field | Description |
| --- | --- |
| Phase Name | e.g., "Design Hardening", "Implementation", "Validation". |
| Owner(s) | Primary agent/role responsible. |
| Deliverables | Specific artifacts or code paths expected. |
| Acceptance Tests | How we prove the phase is complete (CLI command, pytest, etc.). |

## Dependencies & Guardrails

- **FeatureState schema** must store `plan.phases[*]` with name, owners, deliverables, and acceptance tests.
- **Telemetry**: `data/trajectories/run_*.json` should persist a `phases` artifact, and `data/metrics/io_audit.jsonl` must show `workflow_phase=implementation`.
- **Fallback**: If planner validation fails (missing owners/tests), loop back through reviewer corrections before Swarm executes.

## Sandwich Execution Model

- **Implementation phases are lean**: code changes only, skip full builds/tests, run only quick sanity checks.
- **Fullstack Debugger phases** run heavy build/test steps in order (backend build, frontend build, e2e) and update backend/frontend test reports.
- **Checkpointing**: if the debugger hits time limits, it writes progress to `docs/debug_state.md` so retries can resume.

## Review Checklist

1. Every phase lists at least one owner and acceptance signal.
2. Dependencies on configs/models/docs are documented.
3. If tests are deferred, the plan calls out the Fullstack Debugger phase as the execution gate.
4. Plan references `demo/feature_request.yaml` (or scenario-specific file) for end-to-end validation.
