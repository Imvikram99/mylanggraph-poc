"""Aggregate IO audit logs for observation-driven tuning."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Summarize io_audit logs to guide prompt/model tuning.")
console = Console()


@app.command()
def summarize(
    audit_log: Path = typer.Argument(Path("data/metrics/io_audit.jsonl"), exists=True),
    output: Path = typer.Option(Path("data/metrics/audit_summary.json"), "--output"),
) -> None:
    errors = []
    routes = Counter()
    with audit_log.open("r", encoding="utf-8") as fin:
        for line in fin:
            record = json.loads(line)
            if record.get("route"):
                routes[record["route"]] += 1
            if record.get("errors"):
                errors.extend(record["errors"])
    summary = {
        "routes": dict(routes),
        "top_errors": Counter(errors).most_common(10),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    console.log(f"[green]Audit summary written[/] {output}")


if __name__ == "__main__":
    app()
