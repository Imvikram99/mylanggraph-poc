# Capability Gap Plan (QYLIS Senior Data Scientist Role)

This roadmap focuses on the features/tools that align our LangGraph POC with the expectations outlined in the QYLIS Senior Data Scientist job description (model strategy, RLHF/DPO, evaluation governance, and cross-functional tooling).

## 1. Model Strategy & Selection
- _Status: Model registry + benchmarking shipped; strategy catalog documented in `docs/strategies.md`._
- **Model registry + benchmarking harness**
  - Build `scripts/models/benchmark.py` to evaluate OSS/proprietary LLMs/SLMs across latency, cost, accuracy, and privacy flags.
  - Store benchmark metadata (model name, provider, prompt templates) in `data/metrics/model_benchmarks.jsonl` for reproducible comparisons.
- **Dynamic provider selection**
  - Extend `configs/models.yaml` + router to load policy rules (e.g., `MODEL_POLICY=cost_sensitive`) that automatically choose between prompting, RAG, or fine-tuning backends based on scenario metadata.
- **Prompt/RAG strategy catalog**
  - Author `docs/strategies.md` describing when to use prompting vs. RAG vs. fine-tuning, referencing business use cases.

## 2. Data Preparation & Training Readiness
- **Dataset pipeline**
  - Implement `scripts/data/build_corpus.py` that ingests raw documents, handles cleaning/normalization/deduplication, and emits chunked parquet files along with lineage metadata.
- **Dataset catalog + versioning**
  - Introduce `data/datasets/manifest.json` capturing dataset IDs, schema, quality metrics, and storage paths (mirroring MLflow/W&B dataset tracking).
- **Quality dashboards**
  - Add `scripts/data/quality_report.py` to compute coverage, class balance, and dedup stats; surface results in `data/metrics/data_quality.json`.

## 3. RLHF / DPO & Human-in-the-Loop
- **Preference collection service**
  - Build a lightweight annotation UI (FastAPI + SQLite) under `src/ui/annotations.py` to capture pairwise preferences, annotator IDs, and bias metrics.
- **Reward modeling pipeline**
  - Provide `scripts/rlhf/train_reward.py` (PyTorch/HF) that consumes preferences and trains reward models; log experiments via MLflow/W&B.
- **RLHF/DPO orchestration**
  - Add `scripts/rlhf/run_pipeline.py` to run prompt generation, preference sampling, reward training, and policy optimization (supporting both PPO-style RLHF and offline DPO).
- **Bias / agreement metrics**
  - Extend evaluator metrics to log inter-annotator agreement and bias scores per dataset.

## 4. Evaluation & Governance
- _Status: Eval suite + governance + KPI reporter (`src/eval/kpi.py`, `data/metrics/kpi_report.jsonl`)._
- **Comprehensive eval suite**
  - Create `scripts/eval/run_suite.py` covering relevance, hallucination, bias, robustness, and safety; integrate adversarial tests and cost/latency dashboards.
- **Responsible AI controls**
  - Add policy checks (PII detection, toxicity filters) and governance logs stored in `data/metrics/governance.jsonl`.
- **Business impact tracking**
  - Integrate evaluation results with product KPIs (e.g., success rates, conversion metrics) to show measurable impact.

## 5. Technical Leadership & Enablement
- _Status: Playbooks published, PR template (`.github/pull_request_template.md`) enforces mentorship checklist, CI expanded._
- **Cross-functional documentation**
  - Maintain `docs/playbooks/` for data engineering handoffs (schemas, pipelines) and product alignment (evaluation rubrics, release checklists).
- **Mentorship tooling**
  - Set up code review templates (GitHub PR templates) and experiment tracking guidelines to streamline collaboration.
- **CI/CD enhancements**
  - Expand `.github/workflows/ci.yml` to include dataset linting, RLHF pipeline dry runs, and security/governance checks before deployment.

## Immediate Action Items
1. Stand up the model benchmarking harness and dataset build pipeline (Sections 1–2).
2. Prototype the annotation UI + reward modeling script to demonstrate RLHF readiness (Section 3).
3. Expand the evaluator scripts to cover governance criteria and connect to product KPIs (Section 4).
4. Update CI + documentation to reflect cross-functional workflows (Section 5).

## 6. Advanced Agent Orchestration, Evaluation, and Prompt/PEFT Readiness
1. **Agent orchestration (LangChain + cyclic graphs)**
   - Embed a LangChain `AgentExecutor` node within our LangGraph DAG to prove seamless interoperability.
   - Demonstrate cyclic/planning loops (e.g., `planner -> executor -> evaluator -> planner`) with guardrails to prevent infinite cycles.
   - Add a complex scenario (e.g., `demo/autonomous_analyst.yaml`) plus documentation explaining the autonomous workflow.

2. **LLM-as-a-Judge evaluation**
   - Implement a judge module (`src/eval/judge.py`) that calls a stronger model (GPT-4, Claude) to assess outputs for accuracy, safety, and policy adherence using structured prompts.
   - Integrate judge scores into the evaluation pipeline (`scripts/eval/run_suite.py`) and log results alongside heuristic metrics.
   - Provide example prompts + tests that exercise “LLM as judge” patterns.

3. **Prompt tuning / PEFT readiness**
   - Add prompt-optimization tools (e.g., template search via scripts or notebooks) and document workflows under `docs/prompt_tuning.md`.
   - Create a PEFT/LoRA scaffolding script (e.g., `scripts/models/train_peft.py`) that demonstrates how to attach adapters to chosen base models, with configuration knobs for parameter-efficient fine-tuning.
   - Capture best practices (hyperparameters, evaluation hooks) so the repo shows applied knowledge of prompt tuning and PEFT.

4. **Data integrity validation**
   - Define Pydantic schemas for scenario inputs/outputs (`src/schemas/`), enforce validation before/after each graph run, and log schema violations.
   - Add an I/O audit log (`data/metrics/io_audit.jsonl`) documenting whether each request/response satisfied the schema and project requirements.
   - Include CI checks that fail if schema validation or audit logging is missing for new code paths.

## Immediate Next Steps
- [ ] Stand up the model benchmarking harness and dataset build pipeline (Sections 1–2).
- [ ] Prototype the annotation UI + reward modeling script to demonstrate RLHF readiness (Section 3).
- [ ] Expand the evaluator scripts to cover governance criteria and connect to product KPIs (Section 4).
- [ ] Update CI + documentation to reflect cross-functional workflows (Section 5).
- [ ] Implement advanced agent orchestration, LLM-as-a-judge evaluation, prompt/PEFT scaffolding, and data-integrity validation per Section 6.

## 7. Continuous Learning & Stretch Phases
These phases push the POC beyond the job-description baseline and act as structured learning sprints.

### Phase 7A – Synthetic Data & Robustness
- _Status: Implemented via `src/data_pipeline/augment.py`, `scripts/data/augment.py`, and robustness scoring in `scripts/eval/run_suite.py`._
- Build `scripts/data/augment.py` to generate counterfactual/paraphrased samples (LLM + rule-based perturbations).
- Track lineage (`data/datasets/manifest.json`) so augmented samples are clearly labeled.
- Add robustness tests inside `scripts/eval/run_suite.py` to score outputs on noisy/perturbed inputs.

### Phase 7B – Cost & Latency Budgeting
- _Status: Implemented via `CostLatencyTracker`, router telemetry awareness, and `data/metrics/cost_latency.jsonl`._
- Instrument LangGraph callbacks to capture per-node latency, token counts, and estimated cost.
- Emit metrics to `data/metrics/model_benchmarks.jsonl` or a new `data/metrics/cost_latency.jsonl`.
- Teach the router to honor budgets (e.g., drop expensive routes when exceeding thresholds).

### Phase 7C – Safety & Adversarial Red Teaming
- _Status: Implemented via `scripts/eval/adversarial_catalog.py`, `src/eval/adversarial.py`, and governance logging._ 
- Extend the eval suite with jailbreak, toxicity, and PII prompts sourced from `scripts/eval/adversarial_catalog.py`.
- Add policy filters (OpenAI moderation / custom heuristics) and log violations to `data/metrics/governance.jsonl`.
- Automate nightly adversarial sweeps via CI to catch regressions.

### Phase 7D – Regression & Trajectory Snapshots
- _Status: Implemented via `scripts/eval/regression.py` snapshot + compare commands._
- Snapshot representative LangGraph runs (JSON trajectories) and add comparison tests that diff future runs.
- Optional: leverage an “LLM-as-a-judge regression” that compares new outputs with blessed references.
- Wire checks into CI so unexpected deltas block merges.

### Phase 7E – MLOps & Experiment Tracking
- _Status: Implemented via `ExperimentTracker` logging from reward training + RLHF pipeline._
- Push reward-model checkpoints, dataset hashes, and evaluation metrics to MLflow or W&B.
- Provide templates/notebooks showing how to reproduce experiments and visualize KPI lift.

### Phase 7F – Continuous Annotation Feedback
- _Status: Implemented via annotation queue endpoints, dashboards, and active-learning surfacing._
- Upgrade the annotation UI with reviewer queues, inter-annotator dashboards, and bias/coverage charts.
- Implement active-learning sampling (surface low-confidence generations for human review).

### Phase 7G – Deployment Hardening
- _Status: Implemented via tenant-aware FastAPI server, feature flags, and rate limiting._
- Package the graph runner as a FastAPI/Modal service with health checks, rate limiting, and per-tenant secrets.
- Add feature flags / rollout config so risky changes can be toggled without redeploys.

### Phase 7H – Observation-Driven Prompt/Model Tuning
- _Status: Implemented via `scripts/data/audit_report.py` and audit-driven summaries._
- Parse `data/metrics/io_audit.jsonl` + evaluation logs to produce error notebooks that guide improvements.
- Schedule a recurring “audit review” task where failed cases feed back into prompt tuning, data augmentation, or model selection experiments.

Each Phase 7 sprint can be executed independently—pick the stretch area that best supports the next career milestone and iterate just like Phases 1–6.

This plan ensures our repo showcases the skills highlighted in the job post: model selection, data quality, RLHF/HITL systems, evaluation/governance, advanced agent orchestration, LLM-as-a-judge patterns, prompt/PEFT tuning, and technical leadership.
