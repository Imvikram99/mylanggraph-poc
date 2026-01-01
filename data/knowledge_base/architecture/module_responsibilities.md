# LangGraph Module Responsibilities

This note condenses the architecture narrative from `README.md` and `docs/flow-diagram.md` so routing + swarm decisions stay grounded in code ownership.

| Module | Responsibilities | Key Files / Docs |
| --- | --- | --- |
| Router Node | Score intents, enforce latency/cost budgets, choose between RAG, GraphRAG, hybrid fan-out, skill packs, or swarm escalations. Annotates `metadata.router_decision` for telemetry. | `src/graph/nodes/router.py`, `configs/graph_config.dev.yaml#defaults.router`, `README.md#Architecture` |
| RAG Retriever | Fetch dense docs from Qdrant/Chroma, apply HEAT filters, emit citations for evaluator + audit logs, and write long-term context back to memory writer. | `src/graph/nodes/rag.py`, `scripts/ingest.py`, `data/knowledge_base/*` |
| GraphRAG Node | Walk lightweight entity graph snapshots, stitch relationship summaries, and back off to basic RAG when traversal fails. | `src/graph/nodes/graph_rag.py`, `data/graph/` |
| SkillHub Node | Dynamically loads registered tool packs (`skills/registry.yaml`) and MCP servers; default filesystem MCP is scoped to `data/knowledge_base`. | `src/graph/nodes/skills.py`, `configs/mcp_tools.yaml`, `skills/` |
| Memory Layer | Combines SQLite checkpoints for short-term history with `TemporalMemoryStore` for timestamped insights, categories, and TTL enforcement. | `src/memory/checkpointer.py`, `src/memory/temporal.py`, `docs/architecture_plan.md` |
| Swarm Coordinator | Plans tasks, dispatches Researcher/Writer worker nodes, reconciles outputs via weighted vote, and hands off to evaluator. | `src/graph/nodes/swarm.py`, `configs/graph_config.dev.yaml#swarm`, `README.md#What-this-POC-demonstrates` |
| Evaluator / RAFT Hook | Scores grounding/coverage, logs metrics to `data/metrics/*`, future RAFT plan ensures reviewer feedback loops into router weights. | `src/graph/nodes/evaluator.py`, `docs/raft.md` |

**State Dependencies**
- `FeatureState.messages` capture Architect/Reviewer chatter for summarization.
- `FeatureState.plan` stores phase slices for downstream planning (Phase 3+).
- `checkpoints` and `attempt_counters` enforce circuit breakers before re-routing.
