"""Prompt tuning helpers."""

from __future__ import annotations


def score_prompt(prompt: str) -> float:
    length_penalty = abs(len(prompt) - 80) / 80
    directives = ["cite", "steps", "analyze"]
    contains_directives = sum(keyword in prompt.lower() for keyword in directives) * 0.1
    return round(max(0.0, 1.0 - length_penalty + contains_directives), 3)
