# LangGraph Agentic Roadmap

We’ll evolve the POC in clear phases so a single engineer (or Codex automation) can pick up work, know the exit criteria, and keep telemetry/governance intact. Each phase lists goals, deliverables, exit tests, and upstream dependencies.

---

## Expert Review & Guardrails
- **Verdict**: The Architect → Reviewer → Lead design leans into LangGraph’s strengths (stateful cycles + HITL). Keep separation between planning and evaluation so no node grades its own work.
- **State schema first**: Introduce a `FeatureState` `TypedDict` now with `messages`, `plan` (structured dict), `checkpoints`, and counters (e.g., `review_attempts`). This avoids string-diff churn when Reviewer edits individual plan sections.
- **Approval pauses**: Use LangGraph `interrupt_before`/`interrupt_after` hooks so Architect/Tech Lead outputs can pause for human approval (or CLI confirmation) before proceeding.
- **Router-worker vs. swarm**: Treat Swarm execution as an orchestrated map stage—emit a task list, then dispatch specialized workers rather than free-form agent chatter to prevent runaway costs.
- **State summarization**: Before coding begins, summarize the approved plan into a fresh system message and truncate brainstorming context so coding agents operate with a concise brief.
- **Circuit breaker**: Track attempt counts per loop and fail fast (surface a `needs_human` error) after N retries to avoid infinite Architect↔Reviewer cycles.

## Phase 0 – Baseline Readiness
- **Goals**: Run the repo locally, load env vars, ingest minimum docs. Capture current behavior as a control trajectory.
- **Deliverables**:
  - `.env` populated with routing + provider keys.
  - `python scripts/ingest.py --docs data/knowledge_base` refreshed embeddings.
  - `python -m src.runner --scenario demo/rag_qa.yaml --stream` logs saved to `data/trajectories/`.
- **Exit checks**:
  - ✅ `data/memory/vectorstore/` contains fresh files.
  - ✅ `data/metrics/io_audit.jsonl` confirms valid input/output for the smoke scenario.

### Phase 0 Implementation Plan
| Step | Owner | Actions | Success Criteria |
| --- | --- | --- | --- |
| 0.1 Environment bootstrap | Ops | Create/activate `.venv`, install deps via `pip install -r requirements.txt`, copy `.env.example` to `.env` | `which python` points to local venv; `.env` populated with required keys |
| 0.2 Provider + telemetry wiring | Ops | Fill `.env` with `OPENROUTER_API_KEY`, `MODEL_PROVIDER`, `QDRANT_URL`; run `python -m src.runner --help` to confirm config loads; ensure `LANGCHAIN_TRACING_V2` disabled unless LangSmith configured | CLI starts without missing env errors |
| 0.3 Vector store ingestion | Researcher | Run `python scripts/ingest.py --docs data/knowledge_base`; verify logs mention document count; snapshot `${VECTOR_DB_PATH}` timestamp | `ls -lh data/memory/vectorstore` shows updated files (+ telemetry in console) |
| 0.4 Baseline run | Researcher | Execute `python -m src.runner --scenario demo/rag_qa.yaml --stream --graph-config configs/graph_config.dev.yaml`; capture console output + `data/trajectories/run_*.json` | Trajectory + IO audit written; router route recorded |
| 0.5 Verification + checklist | Ops | Confirm `data/metrics/io_audit.jsonl` contains latest scenario_id with `valid_input=true`, `valid_output=true`; document run metadata in this file (phase checklist) | Exit criteria satisfied; share run hash in stand-up |

**Notes**
- If ingestion fails due to Qdrant connectivity, temporarily set `VECTOR_DB_IMPL=chroma` in `.env` to unblock Phase 0 while infrastructure is provisioned.
- Capture screenshots or logs for each step; they become evidence for Phase 1 onboarding.

## Phase 1 – Repository & Knowledge Discovery
- **Goals**: Teach the system about existing capabilities so future prompts stay grounded.
- **Tasks**:
  1. Expand `data/knowledge_base/` with architecture docs, run `scripts/ingest.py`.
  2. Use `SkillHubNode` + MCP filesystem tool to ensure all key docs (README, configs, docs/strategies.md) are retrievable.
  3. Tag memories using `TemporalMemoryStore` categories (`architecture`, `workflow`, `evaluation`).
- **Deliverables**:
  - Curated Markdown notes linking each module to responsibilities.
  - Memory search smoke tests (`python scripts/run_scenarios.py --scenarios demo`) verifying hits for “architecture”, “swarm”, etc.

### Phase 1 Implementation Plan
| Step | Owner | Actions | Success Criteria |
| --- | --- | --- | --- |
| 1.1 Knowledge inventory | Researcher | Identify missing architecture/workflow docs (README, configs, `docs/strategies.md`, runbooks); record source + freshness notes in `docs/plan.md` checklist | Inventory lists every core module with doc path + last updated date |
| 1.2 Knowledge base curation | Researcher | Normalize selected docs (trim secrets, ensure Markdown), copy into `data/knowledge_base/` under descriptive folders | `git status` shows new/updated Markdown under `data/knowledge_base/` and no sensitive data flagged |
| 1.3 Embedding refresh | Ops | Run `python scripts/ingest.py --docs data/knowledge_base` after updating `.env` vector settings; capture doc + chunk counts in logs | `data/memory/vectorstore/` timestamp updated and ingest logs saved to `data/trajectories/phase1_ingest.log` |
| 1.4 SkillHub & MCP verification | Researcher | Configure `SkillHubNode` to surface repo docs, test retrieval via MCP filesystem (e.g., request `README.md`, `configs/graph_config.dev.yaml`) | MCP transcript shows successful fetches for every required doc; SkillHub returns non-empty snippets |
| 1.5 Temporal tagging & smoke tests | Researcher | Tag new memories with `architecture/workflow/evaluation` using `TemporalMemoryStore` helper; run `python scripts/run_scenarios.py --scenarios demo` to confirm retrieval keywords (“architecture”, “swarm”, “checkpoints”) hit | Scenario run stores trajectory referencing tagged memories; CLI output confirms relevant hits |

#### Step 1.1 – Knowledge Inventory
| Module / Focus | Source Doc(s) | Last Updated | Notes |
| --- | --- | --- | --- |
| Architecture overview | `README.md`, `docs/flow-diagram.md` | 2025-12-19 / 2025-12-15 | Covers macro flow + mermaid diagram but lacks per-node responsibilities; needs cross-link to LangGraph state schema. |
| Routing + configuration | `configs/graph_config.dev.yaml`, `src/graph/nodes/router.py` | 2025-12-19 | Router heuristics + forced routes defined, yet “workflow” trigger phrases not documented; add config commentary to KB. |
| Retrieval & knowledge strategy | `docs/strategies.md`, `data/knowledge_base/memory_strategy.md` | 2025-12-19 / 2025-12-19 | Strategy doc summarizes delivery options but is missing concrete owner matrix; curated KB needs RAG + GraphRAG comparison. |
| Evaluation & RAFT | `docs/raft.md`, `src/graph/nodes/evaluator.py` | 2025-12-15 / 2025-12-19 | Describes heuristics but not the planned Reviewer loop; annotate evaluation criteria + metrics sinks. |
| Scenarios & demos | `docs/scenarios.md`, `demo/*.yaml` | 2025-12-19 / 2025-12-15 | Scenario DSL documented, yet we lack tags for architecture/workflow prompts; ingestion must capture sample prompts + expected routes. |
## Phase 2 – Workflow Scaffolding (Architect → Reviewer → Tech Lead)
- **Goals**: Add the new feature-request workflow that routes “I need this feature…” through architecture planning, strict review, and tech-lead planning.
- **Tasks**:
  1. Create `configs/workflows.yaml` with prompt templates for architects, reviewers, and tech leads.
  2. Define `FeatureState` (extends `AgentState`) with `messages`, `plan`, `checkpoints`, `attempt_counters`, and `workflow_phase` metadata; plumb it through `graph_builder`.
  3. Add nodes under `src/graph/nodes/workflow.py` (`WorkflowSelectorNode`, `ArchitecturePlannerNode`, `PlanReviewerNode`, `TechLeadNode`) and register them in `graph_builder`, making reviewer nodes capable of mutating only the relevant plan slice.
  4. Update `RouterNode` thresholds so `context.mode=architect` or trigger phrases force the workflow path; hook `interrupt_before=["plan_reviewer", "tech_lead"]` so CLI users/HITL can approve.
  5. Extend `skills/registry.yaml` with `lead_pack` & `implementation_pack` to expose reusable prompt helpers.
- **Deliverables**:
  - New scenario (`demo/feature_request.yaml`) proving the branch.
  - Telemetry showing router reason `workflow`.
- **Exit checks**:
  - ✅ Workflow nodes wrapped by `CostLatencyTracker`.
  - ✅ Plan reviewer can send corrections (use `RetryNode` contract).

**Implementation notes**
- `configs/workflows.yaml` holds the architect/reviewer/tech-lead prompt templates.
- `FeatureState` extends the base agent state with `plan`, `checkpoints`, and `workflow_phase` metadata that flow through `graph_builder`.
- New workflow nodes live in `src/graph/nodes/workflow.py`, and the scenario `demo/feature_request.yaml` asserts `router_reason=workflow_request`.
- Set `WORKFLOW_REQUIRE_APPROVALS=true` in `.env` to pause before `plan_reviewer`/`tech_lead` for HITL approvals.

## Phase 3 – Implementation Planner & Phase Gates
- **Goals**: Turn reviewer-approved plans into phase-wise execution steps and align with swarm/coding loops.
- **Tasks**:
  1. Create `docs/implementation.md` with templates for Phase plan, dependencies, owners, and review checklist.
  2. Build `ImplementationPlannerNode` that reads the doc via MCP filesystem and emits Markdown sections (`Phase 1`, `Phase 2`, ...) while writing each phase to `FeatureState["plan"]["phases"]`.
  3. Replace the open-ended Swarm loop with a router-worker fan-out: Implementation planner emits a task list, `Send()` dispatches workers per task, and `SwarmNode` simply reconciles outputs.
  4. Add CLI helper (`scripts/workflow/new_feature.py`) to set scenario context (mode, stack, deadlines) and optionally enforce a `recursion_limit`.
- **Deliverables**:
  - Phase-wise plan stored in trajectory metadata.
  - `data/trajectories/` includes `phases` artifact with owners + acceptance tests.
- **Exit checks**:
  - ✅ When Implementation planner fails validation, reviewer feedback loops until corrected.
  - ✅ Swarm outputs cite phase titles in `state["output"]`.

**Implementation notes**
- `docs/implementation.md` + `data/knowledge_base/workflows/implementation_playbook.md` define the templates consumed by `ImplementationPlannerNode`.
- `FeatureState.plan.phases` holds the phase slices, and `SwarmNode` now emits summaries referencing `Phase 1`, `Phase 2`, etc.
- `scripts/workflow/new_feature.py` scaffolds feature-request scenarios with the correct workflow context and assertions.

## Phase 4 – Coding, Review, and Automation
- **Goals**: Drive real edits and reviews based on the phase plan, enabling Codex/agents to implement features end-to-end.
- **Tasks**:
  1. Insert a `PlanSummaryNode` that condenses Architect/Reviewer chatter into a concise system brief before coding; clear stale brainstorm messages but keep the structured plan in state.
  2. Teach `LangChainAgentNode` to read phases and execute coding subtasks or call skill packs (`report_pack` for docs, `lead_pack` for stack choices).
  3. Wrap all code execution and file writes in a sandbox (Docker/E2B) so `CodeExecutionTool` cannot mutate the host; expose sandbox controls via `skills/ops_pack`.
  4. Implement `CodeReviewNode` that enforces `docs/playbooks/product_alignment.md` and `docs/playbooks/data_engineering.md` guardrails.
  5. Capture diffs/tests per phase (persist to `data/trajectories` and optionally `data/metrics/cost_latency.jsonl`), linking them back to `FeatureState["checkpoints"]`.
- **Deliverables**:
  - Automated checklist for each phase: plan approved → implementation done → code reviewed.
  - CLI command `python -m src.runner --scenario demo/feature_request.yaml` produces final response referencing code paths touched.
- **Exit checks**:
  - ✅ CodeReviewNode emits actionable feedback when acceptance tests missing.
  - ✅ IO audit shows new route + metadata (`workflow_phase`).

**Implementation plan**
- **PlanSummaryNode**:
  - Create `PlanSummaryNode` (e.g., `src/graph/nodes/summary.py` extension) that ingests `FeatureState.plan` + recent conversation and outputs a concise system brief stored in `state["messages"]` and `state["plan"]["summary"]`.
  - Hook the node between `implementation_planner` and the execution branch so downstream coding agents operate on the summary, and ensure old brainstorm messages are trimmed.
- **Phase-aware execution**:
  - Extend `LangChainAgentNode` to iterate through `plan["phases"]`, setting context (owner, deliverables, acceptance tests) before executing each subtask.
  - Allow phases to select skill packs dynamically (`context.skill_pack`, `skill_args`) so the agent can call `report_pack`, `lead_pack`, etc.
  - Persist per-phase outputs into `FeatureState["checkpoints"]` and attach them to `artifacts`.
- **Repo automation entrypoint**:
  - Provide a CLI (`python scripts/workflow/new_feature.py run --repo <path>|--repo-url <url> --branch feature/test --prompt "Implement X"`) to capture feature requests, repository locations, and target branches in a single step.
  - Flow repo metadata through `FeatureState.plan.metadata` and execution nodes so the coding phase can automatically call `ops_pack.prepare_repo` / `ops_pack.run_repo_command` to clone/check out branches inside `WORKFLOW_REPO_ROOT` and run git status/tests in a sandbox.
  - Add a Codex bridge skill (`codex_pack.request_codex`) that wraps `scripts/ops/codex_proxy.py`, forwarding coding tasks to the Codex CLI so all code generation remains in the approved environment. Configure `CODEX_CLI_COMMAND` and optionally `WORKFLOW_REPO_ROOT`/`CODEX_TARGET_REPO` to point at the desired workspace.
- **Secure code execution**:
  - Integrate a sandbox tool (Docker/E2B wrapper) exposed via `skills/ops_pack`, ensuring file writes/tests run in isolation.
  - Provide configuration in `.env`/`configs/graph_config.*` for sandbox toggles (local vs. remote).
- **CodeReviewNode**:
  - Implement `CodeReviewNode` that reads `docs/playbooks/product_alignment.md` and `docs/playbooks/data_engineering.md`, validates phase outputs against guardrails, and emits actionable feedback if acceptance tests are missing.
  - Wire the reviewer after phase execution, with retries if critical findings exist, and log results to `data/metrics/io_audit.jsonl`.
- **Telemetry + CLI**:
  - Augment `data/trajectories/run_*.json` with a per-phase checklist artifact (plan summary → implementation outputs → review verdicts).
  - Update `scripts/workflow/new_feature.py` (or add a companion command) to set `context.recursion_limit`, sandbox preferences, and desired reviewers for coding phases.
  - Document how to run `python -m src.runner --scenario demo/feature_request.yaml --stream` to observe the full coding loop.

## Phase 5 – Observability & Governance Expansion
- **Goals**: Ensure every feature run captures budget, evaluation, and governance posture.
- **Tasks**:
  1. Extend `CostLatencyTracker` metrics to include workflow phase IDs.
  2. Update `EvaluatorNode` prompt to reason about plan coverage + risk.
  3. Wire governance outputs to `data/metrics/governance.jsonl` (reuse `scripts/eval/adversarial_scan.py` to sanity-check).
- **Deliverables**:
  - Dashboard-ready JSONL logs storing `phase`, `route`, `cost_usd`, `latency_s`, `review_status`.
  - Documented verification instructions in this file.
- **Exit checks**:
  - ✅ Regression tests fail if workflow path skips evaluator or audit logging.

**Implementation plan**
- **Tracker enhancements**:
  - Update `CostLatencyTracker` to capture `state["workflow_phase"]` for each node invocation, persisting `"workflow_phase"` into `data/metrics/cost_latency.jsonl`.
  - Expose tracker summaries (cost, latency, phase coverage) via a helper API so CLI runners can print aggregates.
- **Evaluator upgrades**:
  - Expand `EvaluatorNode` prompt logic to reference `plan["phases"]`, verifying coverage/risks per phase.
  - Log evaluator verdicts (coverage %, risk notes) into metadata and emit them to the new governance log.
- **Governance logging**:
  - Introduce `data/metrics/governance.jsonl` storing `{scenario_id, phase, route, review_status, cost_usd, latency_s}` for every run.
  - Provide a CLI command (e.g., `python scripts/eval/adversarial_scan.py ...`) that reads the log, checks for missing phases, and raises on gaps.
- **IO audit guardrails**:
  - Enhance `IOAuditLogger` to fail when workflow runs skip evaluator/code review entries, wiring this check into pytest/regression tests.
  - Add unit tests ensuring skipped evaluator paths raise exceptions.
- **Docs & verification**:
  - Document the observability steps in `docs/plan.md` and `README.md` (validation commands, governance log schema).
  - Update `scripts/workflow/new_feature.py` or a companion script to note where governance artifacts are stored so operators can retrieve them quickly.

## Phase 6 – Stretch: RLHF, Prompt/PEFT, Deployment
- **Goals**: Turn the workflow into a showcase of advanced capabilities.
- **Tasks**:
  - Integrate RLHF artifacts (`scripts/rlhf/train_reward.py`) into plan evaluation loop.
  - Reuse `docs/prompt_tuning.md` to optimize architecture prompts; optionally kick off PEFT scaffolding.
  - Harden deployment via `configs/tenants.yaml` + FastAPI server so workflow can run multi-tenant.
- **Deliverables**:
  - Benchmarks comparing pre/post tuning.
  - CI entry ensuring workflow scenario runs nightly.

**Implementation plan**
- **RLHF integration**:
  - Connect `scripts/rlhf/train_reward.py` outputs to the evaluator/code-review loop, feeding reward scores into `EvaluatorNode` metadata and adjusting router weights.
  - Automate reward-model training from trajectory archives, storing checkpoints under `data/rlhf/`.
- **Prompt/PEFT tuning**:
  - Use `docs/prompt_tuning.md` as the template for Architect/Tech Lead prompts; add a tuning command that sweeps key variables and writes results to `data/metrics/prompt_tuning.json`.
  - Scaffold PEFT adapters for the preferred LLM (LoRA or QLoRA), hooking them into `configs/models.yaml` with toggles for sandbox/deployment.
- **Deployment hardening**:
  - Flesh out `configs/tenants.yaml` + FastAPI server settings so the workflow can run multi-tenant; add guardrails for tenant-specific secrets and logging.
  - Create CI checks that run `demo/feature_request.yaml` nightly, capture reward-model deltas, and fail on regressions.
- **Benchmarking/documentation**:
  - Define before/after metrics for RLHF + prompt tuning (accuracy, cost, latency) and publish them in `docs/benchmarks.md`.
  - Document deployment steps (FastAPI service, tenant config, PEFT adapter usage) so ops can promote the workflow to staging/prod.

---

## Milestones & Tracking
| Phase | Target Duration | Primary Owner | Blocking Dependencies | Validation Command |
| --- | --- | --- | --- | --- |
| 0 | 0.5d | Ops | None | `python -m src.runner --scenario demo/rag_qa.yaml --stream` |
| 1 | 1d | Researcher | Phase 0 | `python scripts/run_scenarios.py --scenarios demo` |
| 2 | 2d | Architect | Phase 1 | `python -m src.runner --scenario demo/feature_request.yaml --graph-config configs/graph_config.dev.yaml` |
| 3 | 2d | Tech Lead | Phase 2 | `python -m src.runner --scenario demo/feature_request.yaml --stream` |
| 4 | 2d | SWE | Phase 3 | `pytest` + CLI scenario |
| 5 | 1d | Observability | Phase 4 | `python scripts/eval/adversarial_scan.py data/trajectories --report data/metrics/adversarial_report.json` |
| 6 | ongoing | Principal | Phase 5 | Project-specific |

---

## Working Agreements
- Always land a trajectory + IO audit per phase so Codex can replay context.
- Keep skill packs up to date; if a phase needs bespoke tooling, add it via `skills/registry.yaml` instead of hardcoding.
- Update this `docs/plan.md` whenever a phase completes (checklist style) so future contributors know the current baseline.
- Enforce circuit breakers: track `review_attempts` and fail gracefully (surface `needs_human`) if Architect↔Reviewer or Coding↔Review loops exceed agreed limits.
- Whenever phases transition from planning to execution, run the summarization step so downstream agents operate with a clean state snapshot.
- Write graph-edge unit tests with mocked state (e.g., Reviewer rejection) before connecting live LLM calls.
- Ensure runs use a checkpointing backend (SQLite/Postgres) so failed phases can resume (“time travel” debugging).
