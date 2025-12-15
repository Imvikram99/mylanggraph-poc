# LangGraph Agent POC
Modern LangGraph-driven multi-agent template with RAG, GraphRAG, and MCP-aware workflows.

## What this POC demonstrates
| Capability | Where it lives | Status |
| --- | --- | --- |
| LangGraph orchestration | `src/graph/graph_builder.py`, `src/graph/nodes/` | **Implemented** |
| RAG retrieval chain | `src/graph/nodes/rag.py`, `data/vectorstore/` | **Implemented** |
| GraphRAG summarization | `src/graph/nodes/graph_rag.py` + `data/graph/` | **Partial** (graph scoring stubbed) |
| RAFT (Retrieval-Aware Feedback Tuning) | `docs/raft.md` (design spec) | **Planned** |
| InstructLab workflow | `scripts/instructlab/` | **Planned** (scaffolding only) |
| Tool routing | `src/graph/nodes/router.py` | **Implemented** |
| Skill packs | `skills/` packages, `skills/registry.yaml` | **Implemented** |
| Agent memory (short/long) | `src/memory/checkpointer.py`, `data/memory/vectorstore/` | **Implemented** |
| Trajectory saving | `data/trajectories/`, LangGraph run logs | **Implemented** |
| Agent handoff logic | `src/graph/nodes/handoff.py` | **Partial** (single-handoff) |
| Swarm coordination | `src/graph/nodes/swarm.py` | **Partial** (planner → workers) |
| MCP tools integration | `configs/mcp_tools.yaml`, `src/integrations/mcp_client.py` | **Partial** (OpenAI + file server tested) |

## Architecture
```mermaid
graph TD
    A([User Prompt]) --> B{Router Node}
    B -->|RAG question| C[RAG Retriever]
    B -->|Graph walk| D[GraphRAG]
    B -->|Tool request| E[Skill Pack Hub]
    E --> F[Tool Exec]
    C --> G[Memory Writer]
    D --> G
    G --> H[Trajectory Store]
    B --> I[Handoff Node]
    I --> J[Swarm Coordinator]
    J --> K[Evaluator / RAFT]
    K --> L((Response))
    H -.-> L
```

**Request flow**
1. Router inspects intent + system signals (latency budget, cost caps) and selects RAG, GraphRAG, skill pack, or direct handoff.
2. Selected node fetches documents via Qdrant vector store (Chroma fallback) or graph projection, executes HEAT-style retrieval filters, and emits tool/memory events.
3. Short-term memory (SQLite checkpointer) captures conversation, while long-term Qdrant memory ingests timestamped artifacts and exposes time-aware retrieval.
4. Trajectory logger stores LangGraph run metadata plus tool results for replay.
5. Handoff node decides whether to delegate to another agent (e.g., `researcher` → `writer`) or escalate to swarm coordinator.
6. Swarm coordinator spins up planner/worker nodes and reconciles their votes; evaluator (future RAFT) scores results before responding.

## Repo structure
```
langgraph-poc/
├── src/
│   ├── graph/
│   │   ├── graph_builder.py          # ties together LangGraph nodes
│   │   └── nodes/
│   │       ├── router.py             # intent routing + tool arbitration
│   │       ├── rag.py                # dense retrieval pipeline
│   │       ├── graph_rag.py          # graph expansion + summarization
│   │       ├── memory.py             # memory read/write helpers
│   │       ├── handoff.py            # agent delegation logic
│   │       └── swarm.py              # planner/worker orchestration
│   ├── memory/
│   │   └── checkpointer.py
│   ├── integrations/
│   │   └── mcp_client.py
│   └── runner.py
├── skills/
│   ├── research_pack/
│   │   └── tools.py
│   ├── report_pack/
│   │   └── tools.py
│   └── registry.yaml
├── data/
│   ├── knowledge_base/               # markdown/pdf corpus for RAG
│   ├── graph/                        # NetworkX graph snapshots
│   ├── memory/vectorstore/           # legacy embeddings / summaries
│   ├── qdrant/                       # Docker volume for Qdrant snapshots
│   └── trajectories/                 # LangGraph run logs
├── configs/
│   ├── graph_config.yaml
│   ├── models.yaml
│   └── mcp_tools.yaml
├── scripts/
│   ├── ingest.py
│   └── instructlab/
│       └── prepare_sft.py
├── .env.example
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Quickstart
**Prereqs**
- Python 3.11+
- `uv` or `pip` for dependency management
- Optional: Docker (for local MCP servers or vector DB)

**Install**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys + MCP endpoints
python scripts/ingest.py --docs data/knowledge_base
```

**Start Qdrant (local Docker)**
```bash
docker run -d --name qdrant \
  -p 6333:6333 \
  -v $(pwd)/data/qdrant:/qdrant/storage \
  qdrant/qdrant:latest
```
Stop with `docker stop qdrant` when done.

**Key environment variables (`.env.example`)**
- `OPENROUTER_API_KEY` + `OPENROUTER_MODEL` + `OPENROUTER_BASE` (default provider)
- `OPENAI_API_KEY` / `AZURE_OPENAI_API_KEY` (optional fallbacks), `ANTHROPIC_API_KEY`
- `LANGCHAIN_TRACING_V2=true` to enable LangSmith dashboards
- `MODEL_PROVIDER` (`openrouter` by default) and `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`
- `VECTOR_DB_PATH=./data/memory/vectorstore` (fallback) and `QDRANT_COLLECTION=langgraph_memories`
- `MCP_SERVER_REGISTRY=./configs/mcp_tools.yaml`
- `QDRANT_URL=http://localhost:6333` and `QDRANT_API_KEY=` (blank for local)
- `MEMORY_TIME_WINDOW_DAYS=30`, `MEMORY_DECAY_HALF_LIFE_HOURS=72`
- `MEMORY_TOP_K=8`, `MEMORY_TTL_TASK_DAYS=7`

**One command to run**
```bash
python -m src.runner --scenario demo/rag_qa.yaml
```
Expected: console logs showing router decision, retrieval hits, skill invocations, and a final synthesized answer stored under `data/trajectories/latest.json`.

## Configuration
- **Model providers**: defined in `configs/models.yaml`. Default is `openrouter` (`OPENROUTER_MODEL`, `OPENROUTER_BASE`), but you can switch via `MODEL_PROVIDER=openai|anthropic|ollama` and associated env vars.
- **Embedding provider**: `EMBEDDING_PROVIDER` toggles between OpenRouter’s OpenAI-compatible embeddings and native OpenAI. Control model via `EMBEDDING_MODEL`.
- **Vector DB**: default Qdrant (Docker). Configure via `QDRANT_URL`, `QDRANT_API_KEY`, and `VECTOR_DB_COLLECTION`. To fall back to embedded Chroma, set `VECTOR_DB_IMPL=chroma`. `scripts/ingest.py` rebuilds embeddings regardless of backend.
- **Memory backend**: short-term uses LangGraph SQLite checkpointer at `data/memory/checkpointer.sqlite`. Long-term uses Qdrant with timestamped metadata + decay-aware reranking. Tune behavior via `MEMORY_TIME_WINDOW_DAYS`, `MEMORY_DECAY_HALF_LIFE_HOURS`, `MEMORY_TOP_K`, `MEMORY_TTL_TASK_DAYS`.
- **MCP config**: `configs/mcp_tools.yaml` lists MCP servers (filesystem, Jira, custom HTTP). Enable/disable by commenting entries or overriding `MCP_ENABLED=false`. `src/integrations/mcp_client.py` handles registration per run.

## How the graph is built
Nodes are defined in `src/graph/nodes/*` and composed via `graph_builder.py`.

```python
# Router pseudocode
with State() as state:
    if state.intent == "graph":
        return GraphRAGNode
    if state.requires_tool:
        return SkillHubNode
    return RAGNode
```

**Node overview**
- **Router**: scoring heuristics + LLM classifier; selects path and enforces safety rails.
- **RAG**: embeds query, fetches top-k documents, reranks with ColBERT-lite, streams answer.
- **GraphRAG**: expands entity graph via NetworkX projection + summarizer; partial weighting stub remains.
- **Memory**: `memory_write_node` stamps episodic events (ts/type/source/tags) into Qdrant; `memory_retrieve_node` blends semantic scores with recency decay.
- **Skills**: loads registry-defined tools and executes via tool router.
- **Handoff**: detects persona mismatch, clones state, hands off to next agent.
- **Swarm**: planner agent decomposes task, workers execute skill packs, aggregator reconciles.
- **Evaluator**: (planned RAFT) scores final output vs retrieved context.

## Tools & Skills
- **Built-in tools**: web search proxy, file reader/writer, structured calculator, MCP relays, `search_memory` / `write_memory`.
- **Skill packs**: `research_pack` (web search + note summarizer), `report_pack` (outline + formatting), `ops_pack` (Planned for ticket updates).

**Add a new skill pack**
1. Create `skills/<name>_pack/tools.py` exporting LangChain tool functions.
2. Register the pack in `skills/registry.yaml` with capabilities + authorization rules.
3. Optional: add custom MCP server entry if skill depends on remote resource.
4. Restart the runner; router auto-discovers the pack via registry.

## Memory
- **Short-term**: per-conversation state persisted with LangGraph checkpointer. Stores user turn history, scratchpad, latest tool outputs. Retention: 24h rolling (configurable).
- **Long-term (temporal)**: approved artifacts embedded into Qdrant with metadata (`ts`, `importance`, `category`, `source`). Retrieval blends cosine similarity with recency decay: `final_score = similarity + α * exp(-(now - ts)/τ) + β * importance`, where τ derives from `MEMORY_DECAY_HALF_LIFE_HOURS`.
- **Time windows & TTL**: queries can restrict to `MEMORY_TIME_WINDOW_DAYS`, and categories respect TTL (`task_state` default 7 days via `MEMORY_TTL_TASK_DAYS`, `user_preferences` never expires). Stale entries are pruned nightly.
- **Hierarchical summaries**: after every 20 turns (or when state > token threshold) a summary tool writes `daily_summary_YYYY-MM-DD` events; weekly aggregation is planned next.
- **Privacy**: `.env` flag `ALLOW_MEMORY_WRITE=false` disables persistence; trajectories omit sensitive tool payloads when `SCRUB_TRAJECTORIES=true`.

## Trajectory / Observability
- Every LangGraph run emits JSONL traces under `data/trajectories/<timestamp>.jsonl`.
- LangSmith tracing (optional) captures spans, model inputs, tool logs.
- Replay by running `python scripts/replay_trajectory.py --path data/trajectories/<file>`.
- Grafana/Loki integration (Planned) for latency dashboards.

## Agent handoff & swarm
- **Handoff trigger**: router or evaluator flags unmet persona or capability needs (e.g., `researcher` finished but writing required). Handoff node clones the working memory minus sensitive slots and invokes target agent config.
- **Swarm coordination**: planner agent decomposes task into subgoals, assigns to worker agents tied to skill packs, and merges outputs via weighted voting. Currently partial, supporting up to 3 workers round-robin; backlog includes dynamic scaling and consensus scoring.

## RAG / GraphRAG / RAFT / InstructLab details
- **RAG (Implemented)**  
  - *Definition*: dense retrieval over docs in `data/knowledge_base`.  
  - *Pipeline*: embed query → vector search (k=6) → rerank (cross-encoder) → answer synth.  
  - *Demo*: `python -m src.runner --scenario demo/rag_qa.yaml`.  
  - *Sample prompt*: “Summarize the LangGraph memory strategy in 3 bullets.”
- **GraphRAG (Partial)**  
  - *Definition*: combine graph traversal + summarization for entity-heavy questions.  
  - *Pipeline*: detect entities → query NetworkX graph → fetch linked docs → produce aggregated summary.  
  - *Demo*: `python -m src.runner --scenario demo/graphrag.yaml`.  
  - *Sample prompt*: “How do the research and report agents collaborate?”
- **RAFT (Planned)**  
  - *Definition*: Retrieval-Aware Feedback Tuning — an evaluation loop scoring responses vs retrieved context and feeding back to skill weights.  
  - *Pipeline (planned)*: evaluator checks hallucination, coverage, latency → adjust router + swarm heuristics.  
  - *Demo*: `python scripts/raft/run_eval.py --scenario demo/rag_qa.yaml` (placeholder).
- **InstructLab (Planned)**  
  - *Definition*: Instruction-tuning workflow using IBM’s InstructLab recipes to fine-tune local models on captured trajectories.  
  - *Workflow (planned)*: export trajectories → generate synthetic pairs via InstructLab → fine-tune `mistral` locally.  
  - *Run*: `scripts/instructlab/prepare_sft.py` (scaffolding) followed by InstructLab CLI commands.

## Demo scenarios
1. **Competitive research brief**: User asks “Compare Neo4j vs ArangoDB for GraphRAG.” Expect router → RAG + GraphRAG combination, skill pack writes structured brief.
2. **Bug triage via MCP**: Prompt “File a Jira ticket if CPU > 90%.” Router sends to ops skill pack, MCP Jira tool planned to execute; currently logs planned action.
3. **Multi-agent writing**: Prompt “Draft a blog outline about multi-agent LangGraph systems.” Research agent gathers data, handoff to writer agent, swarm consolidates sub-sections.

## Evaluation
- **Definition of done**: answers grounded in retrieved docs, handoffs succeed without dropping context, tool errors <5%.
- **Metrics**: latency (p95 < 12s), faithfulness (manual / RAFT planned), retrieval hit rate (>0.7 relevant docs), tool success rate (>0.9), swarm agreement score (planned RAFT).
- **RAFT tie-in**: evaluator will compute faithfulness + coverage and update router weights; tracked in `data/metrics/raft_runs.json`.

## Roadmap
- Implement RAFT evaluator loop + weight updates.
- Finish MCP integrations for Jira & GitHub issues.
- Expand swarm coordination to elastic worker pools.
- Complete InstructLab training script with automated dataset export.
- Add UI harness (Gradio) for interactive demos.

## Troubleshooting
- **Vector store missing**: run `scripts/ingest.py` after populating `data/knowledge_base`.
- **MCP connection errors**: verify server URLs in `configs/mcp_tools.yaml` and ensure `MCP_ENABLED=true`.
- **Memory not persisting**: check write permissions to `data/memory/` and `ALLOW_MEMORY_WRITE`.
- **LangGraph state errors**: delete `data/memory/checkpointer.sqlite` (will rebuild) if schema changes.

## Security & data notes
- Secrets stay in `.env`; do not commit.  
- Set `SCRUB_TRAJECTORIES=true` to redact tool payloads before saving.  
- MCP servers can expose filesystem; keep `configs/mcp_tools.yaml` minimal for production.  
- Vector store contains derived insights—prune before sharing repo.

## License / Contributing
- **License**: MIT (update `LICENSE` if company policy differs).  
- **Contributing**: open a PR with linted code (`ruff`, `mypy`), include scenario recording, and document new skills in `skills/registry.yaml`.
