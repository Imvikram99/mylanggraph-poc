"""Governance logging for responsible AI checks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict

from .adversarial import AdversarialTester


PII_REGEX = re.compile(r"\b(\d{3}-\d{2}-\d{4}|\d{16})\b")
TOXIC_KEYWORDS = {"hate", "kill", "suicide"}


class GovernanceLogger:
    def __init__(self, path: Path = Path("data/metrics/governance.jsonl")) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tester = AdversarialTester()

    def log(self, state: Dict[str, any]) -> Dict[str, bool]:
        output = str(state.get("output") or "")
        pii = bool(PII_REGEX.search(output))
        toxic = any(word in output.lower() for word in TOXIC_KEYWORDS)
        adversarial_hits = self.tester.scan_output(output)
        telemetry = ((state.get("metadata") or {}).get("telemetry") or {})
        plan = state.get("plan") or {}
        phases = plan.get("phases") or []
        review_status = ((state.get("metadata") or {}).get("code_review") or {}).get("status")
        base_record = {
            "scenario": state.get("context", {}).get("scenario_id"),
            "route": state.get("route"),
            "pii_detected": pii,
            "toxicity_detected": toxic,
            "jailbreak_detected": bool(adversarial_hits),
            "adversarial_hits": [hit["name"] for hit in adversarial_hits],
            "cost_usd": telemetry.get("cost_estimate_usd"),
            "latency_s": telemetry.get("latency_s"),
            "review_status": review_status,
        }
        records = []
        if phases:
            for phase in phases:
                record = {**base_record, "phase": phase.get("name"), "owner": phase.get("owner")}
                records.append(record)
        else:
            records.append({**base_record, "phase": state.get("workflow_phase")})
        with self.path.open("a", encoding="utf-8") as fout:
            for record in records:
                fout.write(json.dumps(record) + "\n")
        return {
            "pii_detected": pii,
            "toxicity_detected": toxic,
            "jailbreak_detected": bool(adversarial_hits),
        }
