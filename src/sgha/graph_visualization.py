from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx

from .utils import ensure_dir, write_text


COLOR_BY_TYPE = {
    "Paper": "#34495e",
    "Method": "#2980b9",
    "Task": "#16a085",
    "Dataset": "#27ae60",
    "Metric": "#8e44ad",
    "Assumption": "#d35400",
    "Result": "#2c3e50",
    "Limitation": "#c0392b",
    "FailureCondition": "#e67e22",
    "Claim": "#7f8c8d",
    "Gap": "#b03a2e",
    "Hypothesis": "#1f618d",
}


def write_pyvis_html(graph: nx.MultiDiGraph, output_path: str | Path, *, max_nodes: int = 500) -> Path:
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    try:
        from pyvis.network import Network

        sub = _bounded_graph(graph, max_nodes)
        net = Network(height="850px", width="100%", directed=True, notebook=False, cdn_resources="in_line")
        for node_id, data in sub.nodes(data=True):
            label = data.get("label", node_id)
            ntype = data.get("type", "")
            net.add_node(node_id, label=label[:80], title=str(data), color=COLOR_BY_TYPE.get(ntype, "#95a5a6"))
        for source, target, key, data in sub.edges(keys=True, data=True):
            net.add_edge(source, target, label=data.get("relation", ""), title=str(data))
        net.force_atlas_2based()
        net.write_html(str(output_path), notebook=False)
    except Exception as exc:
        write_text(output_path, f"<html><body><h1>Graph visualization unavailable</h1><pre>{exc}</pre></body></html>")
    return output_path


def _bounded_graph(graph: nx.MultiDiGraph, max_nodes: int) -> nx.MultiDiGraph:
    if graph.number_of_nodes() <= max_nodes:
        return graph
    nodes = sorted(graph.nodes(), key=lambda n: graph.degree(n), reverse=True)[:max_nodes]
    return graph.subgraph(nodes).copy()
