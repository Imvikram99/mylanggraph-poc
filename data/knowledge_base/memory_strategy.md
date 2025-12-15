# Memory Strategy

- Short-term context is cached in LangGraph's SQLite checkpointer.
- Long-term insights are embedded into Qdrant with timestamps, categories, and importance scores.
- Summaries roll up every ~20 turns into daily digests for cheaper recalls.
