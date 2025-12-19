# Data Engineering Playbook

1. **Pipeline overview**
   - Use `scripts/data/build_corpus.py` for ingestion/cleaning/chunking.
   - Document schema changes in `data/datasets/manifest.json`.
2. **Handoff checklist**
   - Provide dataset ID, location, schema, and quality metrics (`data/metrics/data_quality.json`).
   - Capture lineage (source repos, commit ids) and attach to manifests.
3. **On-call tips**
   - Rebuild corpora before major releases.
   - Run `python scripts/data/quality_report.py ...` after ingest to confirm deduping.
