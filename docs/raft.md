# RAFT Roadmap

This document tracks the Retrieval-Aware Feedback Tuning (RAFT) plan for the LangGraph POC.

## Goals

1. Score agent responses for faithfulness, coverage, and latency.
2. Persist evaluation results for longitudinal tracking.
3. Feed metrics back into router + swarm weights.

## Phase 1 (Current)

- Stub evaluator node that logs pending RAFT evaluation.
- CLI script `scripts/raft/run_eval.py` (planned) that replays saved trajectories.

## Phase 2

- Implement automatic grounding checks by comparing citations with retrieved vectors.
- Introduce coverage rubric that penalizes missing required facts/tools.

## Phase 3

- Backpropagate scores into router heuristics (raise/lower RAG vs GraphRAG weight).
- Train lightweight reward model using trajectory archives and InstructLab datasets.
