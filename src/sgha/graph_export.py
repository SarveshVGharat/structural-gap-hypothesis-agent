from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph

from .utils import ensure_dir, write_csv, write_json


def export_graph(graph: nx.MultiDiGraph, graph_dir: str | Path) -> None:
    graph_dir = Path(graph_dir)
    ensure_dir(graph_dir)
    try:
        data = json_graph.node_link_data(graph, edges="edges")
    except TypeError:  # networkx < 3.4
        data = json_graph.node_link_data(graph)
        data["edges"] = data.pop("links", [])
    write_json(graph_dir / "graph.json", data)
    nx.write_graphml(_graphml_safe_copy(graph), graph_dir / "graph.graphml")
    write_csv(graph_dir / "nodes.csv", node_rows(graph))
    write_csv(graph_dir / "edges.csv", edge_rows(graph))
    write_csv(graph_dir / "node_types_summary.csv", _summary_rows([d.get("type", "") for _, d in graph.nodes(data=True)], "node_type"))
    write_csv(graph_dir / "edge_types_summary.csv", _summary_rows([d.get("relation", "") for _, _, _, d in graph.edges(keys=True, data=True)], "edge_type"))


def load_graph(path: str | Path) -> nx.MultiDiGraph:
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    try:
        return json_graph.node_link_graph(data, edges="edges", directed=True, multigraph=True)
    except TypeError:  # networkx < 3.4
        legacy = dict(data)
        legacy["links"] = legacy.get("edges", [])
        return json_graph.node_link_graph(legacy, directed=True, multigraph=True)


def node_rows(graph: nx.MultiDiGraph) -> list[dict[str, Any]]:
    rows = []
    for node_id, data in graph.nodes(data=True):
        rows.append({"id": node_id, **data})
    return rows


def edge_rows(graph: nx.MultiDiGraph) -> list[dict[str, Any]]:
    rows = []
    for source, target, key, data in graph.edges(keys=True, data=True):
        rows.append({"id": key, "source": source, "target": target, **data})
    return rows


def _summary_rows(values: list[str], field: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return [{field: k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def _graphml_safe_copy(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    safe = nx.MultiDiGraph()
    for node_id, data in graph.nodes(data=True):
        safe.add_node(node_id, **{k: _safe_attr(v) for k, v in data.items()})
    for source, target, key, data in graph.edges(keys=True, data=True):
        safe.add_edge(source, target, key=key, **{k: _safe_attr(v) for k, v in data.items()})
    return safe


def _safe_attr(value: Any) -> str | int | float | bool:
    if isinstance(value, (str, int, float, bool)):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)
