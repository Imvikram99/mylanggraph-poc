# RAFT & Evaluation Notes

Summarizes `docs/raft.md` and evaluator implementation details for anyone instrumenting Phase 1 discovery runs.

## Current Evaluator State
- `src/graph/nodes/evaluator.py` implements a heuristic RAFT stub: it inspects router metadata, compares it against retrieved docs, and emits coverage/grounding remarks into trajectory metadata.
- Metrics land in `data/metrics/io_audit.jsonl` (schema validation), `data/metrics/cost_latency.jsonl` (per-node budgets), and `data/metrics/raft_runs.jsonl` (phase-specific experiments).
- Evaluator output informs MemoryWriteNode importance so high-risk answers persist longer.

## RAFT Roadmap (from docs/raft.md)
1. **Phase 1** – Log pending evaluation and wire CLI replay script (`scripts/raft/run_eval.py`, planned).
2. **Phase 2** – Compare citations to retrieved chunks, add coverage rubric penalizing missing facts.
3. **Phase 3** – Feed RAFT scores back into router weights and train a reward model using trajectory archives + InstructLab datasets.

## Operational Reminders
- Every curated knowledge doc ingested via `scripts/ingest.py` must include cite-able source hints so evaluator prompts reference them (“Source: `architecture/module_responsibilities.md`”).
- Capture ingest logs at `data/trajectories/phase1_ingest.log` and attach to stand-ups; evaluator fine-tuning depends on chunk counts staying stable.
- Temporal memories tagged `architecture`, `workflow`, or `evaluation` create easy filters for reviewer prompts (Phase 2+) and make RAFT audits traceable.
