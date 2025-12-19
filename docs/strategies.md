# Prompt vs. RAG vs. Fine-tuning

This catalog explains when to lean on each strategy so product + data teams can make consistent decisions during scoping.

## Prompt-first
- **Use when**: task is short-lived, knowledge is public, latency/cost requirements are strict.
- **Examples**: summarizing system architecture, reformatting responses, answering “how do we” style FAQs that live in public docs.
- **Signals**: low hallucination risk, minimal grounding demand, context fits in prompt window.

## Retrieval-Augmented Generation (RAG)
- **Use when**: answers must cite internal sources, content changes frequently, or compliance requires traceability.
- **Examples**: referencing LangGraph memory strategy docs, responding to product release questions, quoting KPI dashboards.
- **Signals**: request mentions “based on docs/data”, outputs need citations, user persona is “researcher” or “analyst”.
- **Implementation hooks**: `context.mode = "rag"`, `context.force_route = "rag"`, run `scripts/data/build_corpus.py` + `scripts/ingest.py` to refresh embeddings.

## GraphRAG / Hybrid
- **Use when**: need reasoning over relationships (entities, timelines) or blending structured + unstructured data.
- **Examples**: “Explain how research and writer agents collaborate”, timeline analyses, root-cause investigations.
- **Signals**: mentions “relationships”, “timeline”, “graph”, or tasks exceed 40 tokens with multi-hop reasoning.
- **Implementation hooks**: `context.requires_graph = true`, `context.allow_hybrid = true`.

## Fine-tuning / PEFT
- **Use when**: prompts are insufficient, style/voice must be consistent, or offline inference is needed for scale.
- **Examples**: templated executive briefs, specialized classification, on-prem deployments.
- **Signals**: repeated prompt engineering cycles, high variance in outputs, product KPI gaps persist after RAG tuning.
- **Implementation hooks**: `scripts/models/train_peft.py` to scaffold LoRA configs, `docs/prompt_tuning.md` for workflow, track runs via `data/metrics/experiments.jsonl`.

## Decision checklist
1. Does the task require citing fresh/internal data? → **RAG or Hybrid**
2. Is reasoning over relationships or multiple personas required? → **GraphRAG / Hybrid**
3. Are we chasing stylistic consistency or offline inference? → **Fine-tuning / PEFT**
4. Otherwise start with **Prompt-first**, measure hallucination + KPI deltas, then escalate.

Log the decision in issue/PR templates so reviewers can verify the selected strategy against this catalog.
