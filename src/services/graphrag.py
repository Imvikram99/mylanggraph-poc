"""Utilities for working with lightweight knowledge graphs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

import networkx as nx
from rich.console import Console

console = Console()


class GraphKnowledgeBase:
    """Loads a simple entity graph and exposes helper queries for GraphRAG."""

    def __init__(self, graph_path: str = "data/graph/entities.json") -> None:
        self.graph_path = Path(graph_path)
        self.graph = self._load_graph()

    def neighbors_descriptions(self, entities: Iterable[str], max_hops: int = 2) -> List[str]:
        """Return textual descriptions for relationships around the entities."""
        if self.graph is None or self.graph.number_of_nodes() == 0:
            return []
        descriptions: List[str] = []
        undirected = self.graph.to_undirected()
        for entity in entities:
            if entity not in undirected:
                continue
            paths = nx.single_source_shortest_path(undirected, entity, cutoff=max_hops)
            for target, path in paths.items():
                if len(path) < 2 or target == entity:
                    continue
                src = path[-2]
                edge_data = self.graph.get_edge_data(src, target) or {}
                if not edge_data:
                    edge_data = self.graph.get_edge_data(target, src) or {}
                for rel in edge_data.values():
                    relation = rel.get("relation", "related_to")
                    descriptions.append(f"{src} --{relation}--> {target}")
        return descriptions

    def _load_graph(self) -> nx.MultiDiGraph | None:
        if not self.graph_path.exists():
            console.log(f"[yellow]Graph file not found at {self.graph_path}; GraphRAG will fallback.[/]")
            return None
        try:
            payload = json.loads(self.graph_path.read_text(encoding="utf-8"))
        except Exception as exc:
            console.log(f"[red]Failed to load graph data[/] {exc}")
            return None
        graph = nx.MultiDiGraph()
        if isinstance(payload, list):
            for edge in payload:
                source = edge.get("source")
                target = edge.get("target")
                relation = edge.get("relation", "related_to")
                if not source or not target:
                    continue
                graph.add_edge(source, target, relation=relation)
        else:
            console.log(f"[yellow]Graph data at {self.graph_path} is not a list; skipping load.[/]")
        return graph
