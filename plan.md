# Shared Context Across Sessions Plan

## Goals
- Persist planning + implementation context in-repo so multiple sessions can resume with shared state.
- Keep planning and implementation context separate (hard boundary + separate budgets).
- Treat tool session IDs as optional acceleration, not a source of truth.
- Keep prompts small by sending summaries + file pointers instead of full documents.
- Apply all shared-context behavior only when an explicit feature flag is enabled.

## Current Observations (from this repo)
- Workflow sessions (`_dispatch_codex`, `_dispatch_gemini`) store session IDs in `plan.metadata` only; they are lost between runs.
- `LangChainAgentNode` uses `phase_execution.sessions` for per-phase tool calls, but it is also in-memory only.
- `ConversationSummaryNode` and `PlanSummaryNode` create concise summaries but do not persist them.
- `TemporalMemoryStore` already persists data to `data/memory/vectorstore/memories.jsonl`, yet workflow/tool dispatch does not read from it.
- `scripts/ops/codex_proxy.py` logs prompts to `docs/codex_prompts.md` and `data/ops/codex_requests.jsonl`, but nothing reuses those logs as context.

## Proposed Approach
1. **Repo context store**
   - Add lightweight context files in-repo:
     - Planning: `data/context/planning_context.json`
     - Implementation: `data/context/implementation_context.json`
     - Planning sessions (local only): `data/context/planning_sessions.local.json`
     - Implementation sessions (local only): `data/context/implementation_sessions.local.json`
     - Optional human-readable: `docs/context_summary.md`
   - Key by `{repo_path, branch, workstream_id}` to support multiple workstreams.
   - Commit machine JSON + markdown; gitignore `*.local.json` session files.
   - Gated behind a shared-context flag (default off).
2. **Repo state beats memory (hard rule)**
   - Track `repo_commit`, `tracked_files_hash`, and `summary_hash`.
   - On mismatch: mark cached summary as `STALE` and force a file re-scan step.
3. **Evidence ledger**
   - Store claims with evidence (file paths + line refs or symbols).
   - Reject any "done/implemented/fixed" claim that lacks evidence.
4. **Pinned vs Working vs Retrieved**
   - **Pinned**: immutable rules (repo state is truth, security constraints).
   - **Working**: short task summary, open decisions, current checklist.
   - **Retrieved**: on-demand memory snippets, gated by relevance threshold.
5. **Context load at start**
   - New `ContextLoadNode` reads the appropriate store and merges context into `state.context` and `plan.metadata`.
   - Always compute hashes + staleness flags before use.
   - Node is a no-op unless shared-context mode is enabled.
6. **Context write at end**
   - New `ContextWriteNode` persists updated summaries, evidence ledger, and decisions.
   - Only update summaries after verified checkpoints (tests pass, diff applied).
   - If a run fails, store `failed_step`, `error`, `next_action` only.
   - Node is a no-op unless shared-context mode is enabled.
7. **Context bundle injection**
   - Add a short "Context Bundle" to `_dispatch_codex`, `_dispatch_gemini`, and `LangChainAgentNode._format_phase_instruction`.
   - Bundle includes:
     - Pinned rules (short).
     - Working summary + open decisions.
     - Evidence ledger references (not raw content).
     - File pointers (product/UX/architecture/implementation docs).
     - Optional memory snippets from `TemporalMemoryStore.search(feature_request)`.
     - Session IDs (optional, best-effort).
   - Support **role rounds** in a single chat:
     - Roles: Product Owner → Architect → Developer → Validator.
     - Each role sees the same context bundle; no new facts unless backed by repo/tool/user.
     - The "chair" adds a short decision log + open questions after each round.
   - Bundle injection is disabled unless shared-context mode is enabled.
8. **Cost controls**
   - Hard limit bundle length (ex: 1–2k chars per phase).
   - Deterministic budgeter keeps pinned rules, last N decisions, last N errors.
   - Use file references instead of embedding long content.
   - Prefer "diff-first" resume: show git diff vs last checkpoint before summary.
   - If `STALE=true`, force diff-first and mark summaries as stale (do not trust).
   - Budgeter only runs in shared-context mode.

## Implementation Steps
1. Create `src/context/store.py` (load/save/merge helpers, file locking, schema versioning, hash computation).
2. Add `ContextLoadNode`, `ContextWriteNode`, and `ValidationNode` in `src/graph/nodes/`.
3. Wire nodes into `src/graph/graph_builder.py`:
   - Before `workflow_selector` (load context).
   - Before `langchain_agent` (validate + inject diff-first bundle).
   - Before `memory_write` (persist context).
   - Wrap nodes with a shared-context flag check (context/env/config).
4. Update prompt builders:
   - `src/graph/nodes/workflow.py` (`_dispatch_codex`, `_dispatch_gemini`).
   - `src/graph/nodes/langchain_agent.py` (`_format_phase_instruction`).
5. Extend `TemporalMemoryStore` usage for retrieval-only context snippets with relevance gating.
6. Add a small test to validate load/merge/persist, staleness checks, and prompt injection.

## Flag Design (draft)
- **Context flag**: `state.context.share_session` (boolean).
- **Env fallback**: `SHARED_CONTEXT_ENABLED=true|false`.
- **Config fallback**: `configs/graph_config.yaml` toggle for defaults.
- **Rule**: if the flag is false, skip context store, bundle injection, validation, and evidence gating.

## Expected Cost Savings
- Short summaries + file pointers reduce token usage in repeated planning/implementation calls.
- Hard-limited bundles prevent prompt growth as sessions accumulate.
- Optional session resume reduces re-priming when available, without being required.

## Context Schema (draft)
```json
{
  "schema_version": 1,
  "key": {"repo": "...", "branch": "...", "workstream_id": "..."},
  "feature_request": "...",
  "checkpoint": {"git_head": "...", "tracked_files_hash": "...", "summary_hash": "..."},
  "pinned_rules": ["..."],
  "working_summary": {"text": "...", "updated_at": "...", "stale": false},
  "open_decisions": [{"id": "D1", "text": "...", "status": "open"}],
  "evidence_ledger": [{"claim": "...", "files": [{"path": "...", "lines": "L10-L40"}]}],
  "cli_sessions": {"codex": {"id": "...", "local_path": "..."}, "gemini": {"id": "..."}},
  "last_run": {"status": "failed", "error": "...", "next_action": "..."}
}
```

## Context Budget Defaults
**Planning bundle (target 1800–2200 chars)**
- Pinned rules: 250–350
- Repo checkpoint + staleness: 150
- Open decisions (last 3–5): 400–600
- Working summary: 500–800
- File pointers: 200–300
- Retrieved snippets: 0–300 (only if relevant)

**Implementation bundle (target 1200–1700 chars)**
- Pinned rules: 250–350
- Diff-first summary: 300–600
- Task checklist (next 3 steps): 250–400
- Evidence reminder: 100–150
- Retrieved snippets: 0–200

**Role round budgets (planning mode; per role output target)**
- Product Owner: 400–700 chars
- Architect: 600–900 chars
- Developer: 700–1000 chars
- Validator: 300–500 chars

## Decisions
- JSON + markdown: JSON is source of truth; markdown is human dashboard only.
- Commit JSON + markdown; session files live in `*.local.json` and are gitignored.
- Workstream key uses `workstream_id` for stability; `feature_request` is a label.
