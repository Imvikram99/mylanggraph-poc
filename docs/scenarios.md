# Scenario DSL

Scenarios are YAML files that describe the user prompt, optional context, and basic assertions to validate the agent’s output. They power `python scripts/run_scenarios.py` and CI smoke tests.

```yaml
prompt: "Summarize the LangGraph memory strategy."
context:
  persona: researcher
  mode: rag
assertions:
  - type: contains
    value: "Memory Strategy"
  - type: not_contains
    value: "error"
  - type: metadata
    path: ["metadata", "route_history", -1]
    equals: "rag"
```

## Fields

- `prompt` *(required)* – User utterance fed into the graph.
- `context` *(optional)* – Extra state injected into the LangGraph run (persona, constraints, scenario id, etc.).
- `assertions` *(optional)* – List of checks run after the graph completes.
  - `contains` / `not_contains`: ensure the final `output` string includes or excludes a substring.
  - `metadata`: navigate into the result via `path` (list of keys or indexes) and compare with `equals`.

## Running scenarios

```bash
python scripts/run_scenarios.py --scenarios demo
```

The CLI accepts files or directories; directories are scanned for `*.yaml`. A non-zero exit code indicates a failing assertion (surfaced in CI via `.github/workflows/ci.yml`).
