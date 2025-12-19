# Prompt Tuning & PEFT Playbook

## Prompt Template Search
Use `scripts/models/prompt_search.py` to explore template variants:
```bash
python scripts/models/prompt_search.py --prompt "Summarize {topic}" --topics "LangGraph" "LangChain"
```
The script scores combinations using heuristic metrics and writes results to `data/metrics/prompt_search.jsonl`.

## PEFT / LoRA Scaffolding
Use `scripts/models/train_peft.py` to generate a PEFT configuration stub:
```bash
python scripts/models/train_peft.py --base-model mistral-7b --dataset data/datasets/kb_v1/chunks.jsonl --output-dir data/peft
```
The script validates inputs, writes a config manifest, and documents the next steps for running actual LoRA training via Hugging Face PEFT libraries.

> Note: This repo ships scaffolding; integrate with PEFT/transformers in your environment for full fine-tuning.
