# Routing & Workflow Playbook

Ground truth pulled from `configs/graph_config.dev.yaml`, `docs/scenarios.md`, and `demo/*.yaml` so new contributors can reason about how prompts traverse the LangGraph workflow.

## Decision Inputs
- **Persona / context**: `scenario.context.persona` hints at skill packs (e.g., `researcher` prefers `research_pack`).
- **Mode flags**: `context.mode=rag` or `context.requires_graph=true` force retrieval flavors.
- **Router thresholds**: `graph_rag=0.4`, `swarm=0.45` (dev config) map to scoring heuristics in `RouterNode`.
- **Cost/latency budgets**: Router stores spent tokens + elapsed seconds and avoids branches that would breach budgets recorded in context.
- **Forced routes**: `context.force_route` short-circuits into a node when QA/test harness wants determinism.

## Personas & Scenarios
| Scenario | Route Expectation | Notes |
| --- | --- | --- |
| `demo/rag_qa.yaml` | Pure RAG | Validates retrieval for memory docs, runs with persona `researcher` and `mode=rag`. |
| `demo/graphrag.yaml` | GraphRAG or hybrid | Contains timeline language (“relationship”, “graph”). |
| `demo/autonomous_analyst.yaml` | Swarm planner + workers | Exercises multi-turn plan/execution loop. |

Each scenario YAML uses the DSL documented in `docs/scenarios.md` → prompts, optional context overrides, and assertions that validate outputs (contains strings, metadata checks).

## MCP / Knowledge Access
- `configs/mcp_tools.yaml` enables the builtin **filesystem** MCP rooted at `data/knowledge_base`.
- SkillHub auto-registers `filesystem_read`, so agents can fetch curated docs (README summary, strategies, RAFT notes) without exposing the whole repo.

## Workflow Guardrails
1. Router writes `metadata.router_decision` to every trajectory so evaluators know which branch executed.
2. Memory retrieval precedes heavy computation; `TemporalMemoryStore` filters to the last 30 days (dev config) and merges into `state["working_memory"]["long_term"]`.
3. Swarm planner defaults to `researcher` planner with `researcher` + `writer` workers (max 2); review future phases to add Tech Lead + Reviewer gates.
4. When `context.mode="architect"` (future Phase 2), router will bypass generic RAG route and invoke workflow nodes noted in `docs/plan.md#Phase-2`.

## Strategy Selection Cheatsheet
Adapted from `docs/strategies.md` so playbooks live alongside routing decisions.

| Strategy | When to choose | Signals | Hooks |
| --- | --- | --- | --- |
| Prompt-first | Lightweight, public knowledge, strict latency/cost | Low hallucination risk, short responses | rely on system prompts + `context.model_policy` |
| RAG | Requires citing internal docs, content changes often | Prompts mention “from docs/data”, persona `researcher` | `context.mode="rag"`, refresh `data/knowledge_base` then run `scripts/ingest.py` |
| GraphRAG / Hybrid | Need relationship reasoning / multi-hop analysis | Keywords: “relationship”, “timeline”, “graph” | `context.requires_graph=true`, router threshold `graph_rag` |
| Swarm / Tooling | Multi-step execution or tool coordination | Prompts ask for plans, delegated work | Router raises `swarm` route → `src/graph/nodes/swarm.py` |
| Fine-tuning / PEFT | Styling consistency or offline inference | Frequent prompt tweaks, KPI gaps persist | `scripts/models/train_peft.py`, `docs/prompt_tuning.md` |
