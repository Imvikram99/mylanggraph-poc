# Run entire flow with Gemini CLI as primary coding tool

**Prerequisites:**
1. Ensure `GEMINI_CLI_COMMAND` is set in `.env` or exported if your binary is not `gemini` (e.g. `GEMINI_CLI_COMMAND="gemini-cli"`).

## Full run (shared context enabled)
```bash
python scripts/workflow/new_feature.py run \
  --prompt "Ship the test endpoint in horilla/backend" \
  --repo /Users/apple/Documents/vikram_workspace/spring-boot/brbhr/horilla/backend \
  --branch feature/test \
  --feature "API smoke test" \
  --graph-config configs/graph_config.dev.yaml \
  --stream \
  --coding-tool gemini \
  --workflow-mode full \
  --shared-context-enabled
```

## Resume run (skip completed phases)
```bash
python scripts/workflow/new_feature.py run \
  --prompt "Ship the test endpoint in horilla/backend" \
  --repo /Users/apple/Documents/vikram_workspace/spring-boot/brbhr/horilla/backend \
  --branch feature/test \
  --feature "API smoke test" \
  --graph-config configs/graph_config.dev.yaml \
  --stream \
  --coding-tool gemini \
  --workflow-mode from_planning \
  --shared-context-enabled \
  --workflow-resume
```

## Force rerun (ignore checkpoints)
```bash
python scripts/workflow/new_feature.py run \
  --prompt "Ship the test endpoint in horilla/backend" \
  --repo /Users/apple/Documents/vikram_workspace/spring-boot/brbhr/horilla/backend \
  --branch feature/test \
  --feature "API smoke test" \
  --graph-config configs/graph_config.dev.yaml \
  --stream \
  --coding-tool gemini \
  --workflow-mode full \
  --shared-context-enabled \
  --force-rerun
```

## Full options template (all flags)
Note: remove `--prep-only` and `--plan-only` unless you explicitly want those behaviors.
```bash
python scripts/workflow/new_feature.py run \
  --prompt "Ship the test endpoint in tution-teacher" \
  --persona architect \
  --stack "LangGraph POC" \
  --scenario-id feature_request \
  --deadline "2026-01-31" \
  --repo /Users/apple/Documents/vikram_workspace/spring-boot/brbhr/tution-teacher \
  --repo-url "" \
  --branch feature/test \
  --feature "API smoke test" \
  --graph-config configs/graph_config.dev.yaml \
  --stream \
  --save demo/feature_request_generated.yaml \
  --prep-only \
  --plan-only \
  --workflow-mode full \
  --force-rerun \
  --coding-tool gemini \
  --review-tool gemini \
  --fallback-review-tool codex \
  --shared-context-enabled \
  --workflow-resume
```


 langgraph-poc % python scripts/workflow/new_feature.py run \
  --prompt "Ship the test endpoint in tution-teacher" \
  --persona architect \
  --stack "LangGraph POC" \
  --scenario-id feature_request \
  --deadline "2026-01-31" \
  --repo /Users/apple/Documents/vikram_workspace/spring-boot/brbhr/tution-teacher \
  --repo-url "" \
  --branch feature/test2 \
  --feature "API smoke test" \
  --graph-config configs/graph_config.dev.yaml \
  --stream \
  --save demo/feature_request_generated.yaml \
  --prep-only \
  --plan-only \
  --workflow-mode planning \
  --force-rerun \
  --coding-tool gemini \
  --review-tool gemini \
  --fallback-review-tool codex \
  --shared-context-enabled \
  --workflow-resume


python scripts/workflow/new_feature.py run \
  --prompt "Ship the test endpoint in tution-teacher" \
  --persona architect \
  --stack "LangGraph POC" \
  --scenario-id feature_request \
  --deadline "2026-01-31" \
  --repo /Users/apple/Documents/vikram_workspace/spring-boot/brbhr/tution-teacher \
  --branch feature/test2 \
  --feature "API smoke test" \
  --graph-config configs/graph_config.dev.yaml \
  --stream \
  --save demo/feature_request_generated.yaml \
  --workflow-mode planning \
  --plan-only \
  --force-rerun \
  --coding-tool gemini \
  --review-tool gemini \
  --fallback-review-tool codex \
  --shared-context-enabled \
  --no-workflow-resume
