from __future__ import annotations

import re
from collections import Counter
from typing import Any

import networkx as nx

from .corpus_manifest import read_manifest
from .extraction import load_extractions
from .extraction_schemas import PaperExtraction, ScientificTuple
from .graph_export import export_graph
from .graph_schema import GRAPH_SCHEMA, LIST_FIELD_TYPES, RELATION_OBJECT_TYPE
from .graph_visualization import write_pyvis_html
from .utils import append_jsonl, model_dump, normalize_label, stable_id, utc_now_iso, write_json


# ---------------------------------------------------------------------------
# Fix 2: Entity alias normalization helpers
# ---------------------------------------------------------------------------

_ALIAS_STOP = {
    "the", "a", "an", "of", "for", "in", "on", "with", "and", "or", "by", "to",
    "algorithm", "method", "approach", "model", "technique", "framework", "system",
    "our", "their", "its", "this", "that", "we", "they",
}


def _token_key(label: str) -> frozenset[str]:
    tokens = re.findall(r"[a-z0-9]+", label.lower())
    return frozenset(t for t in tokens if len(t) >= 2 and t not in _ALIAS_STOP)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# Fix 5: Junk label filtering — prevent generic names from merging across papers
# ---------------------------------------------------------------------------

# Regex: matches "Algorithm 1", "Theorem 3.4", "Lemma 2", "Proposition A.1", etc.
_JUNK_LABEL_RE = re.compile(
    r"^(algorithm|theorem|lemma|corollary|proposition|remark|claim|definition)\s*[\d\.]+$",
    re.IGNORECASE,
)

_JUNK_LABEL_EXACT = {
    "our algorithm", "our method", "our approach", "our model",
    "the algorithm", "the method", "the proposed method",
    "baseline", "algorithm 1", "algorithm 2", "algorithm 3",
    "algorithm 4", "algorithm 5", "algorithm 6",
}


def _is_junk_label(label: str) -> bool:
    """Return True for generic labels that should not become graph nodes."""
    l = label.strip().lower()
    return l in _JUNK_LABEL_EXACT or bool(_JUNK_LABEL_RE.match(l))


# ---------------------------------------------------------------------------
# Fix 6: Acronym alias — merge "FullName (ACRONYM)" with "ACRONYM"
# ---------------------------------------------------------------------------

def _extract_trailing_acronym(label: str) -> str | None:
    """Return the acronym if label ends with (ACRONYM), else None."""
    m = re.search(r"\(([A-Z][A-Z0-9\-]{1,})\)\s*$", label)
    return m.group(1) if m else None


def _build_acronym_alias_map(labels: list[str]) -> dict[str, str]:
    """Map short acronym labels to their full-name equivalents."""
    full_names: dict[str, str] = {}  # acronym -> full_name
    for label in labels:
        acr = _extract_trailing_acronym(label)
        if acr and acr in labels:
            # prefer the longer, more descriptive label as canonical
            existing = full_names.get(acr)
            if existing is None or len(label) > len(existing):
                full_names[acr] = label
    return full_names  # e.g. {"RCDB": "Robust Contextual Dueling Bandits (RCDB)"}


# Only alias-map these types — Claim/Result/Task have too many distinguishing tokens
# that look similar but are semantically different (e.g., "Realizable" vs "Non-realizable").
_ALIAS_ELIGIBLE_TYPES = {"Method", "Dataset", "Metric", "Assumption"}

# Max label length for alias matching — long strings (>60 chars) share many common words
# and produce false positives even at high threshold.
_ALIAS_MAX_LABEL_LEN = 60


def _build_alias_map(labels: list[str], threshold: float = 0.85) -> dict[str, str]:
    """Map near-duplicate labels to a canonical form (union-find over token Jaccard).

    Only considers short labels (≤ _ALIAS_MAX_LABEL_LEN chars) to avoid
    sentence-level false positives.
    """
    counts: Counter[str] = Counter(labels)
    # Only consider short labels; long ones are likely distinct sentences
    unique = [l for l in counts if len(l) <= _ALIAS_MAX_LABEL_LEN]
    if len(unique) <= 1:
        return {}

    parent = {l: l for l in unique}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        # Canonical = more frequent; tie-break by longer (more descriptive) label
        if counts[rb] > counts[ra] or (counts[rb] == counts[ra] and len(rb) > len(ra)):
            ra, rb = rb, ra
        parent[rb] = ra

    token_sets = {l: _token_key(l) for l in unique}
    for i, la in enumerate(unique):
        tsa = token_sets[la]
        if not tsa:
            continue
        for lb in unique[i + 1:]:
            tsb = token_sets[lb]
            if not tsb:
                continue
            if _jaccard(tsa, tsb) >= threshold:
                union(la, lb)

    return {l: find(l) for l in unique if find(l) != l}


def _collect_labels_by_type(extractions: list[PaperExtraction]) -> dict[str, list[str]]:
    by_type: dict[str, list[str]] = {}
    for extraction in extractions:
        for field, ntype in LIST_FIELD_TYPES.items():
            if ntype not in _ALIAS_ELIGIBLE_TYPES:
                continue
            for value in getattr(extraction, field, []) or []:
                if value and value != "insufficient evidence":
                    by_type.setdefault(ntype, []).append(value)
        for tup in extraction.tuples:
            subject_type = infer_subject_type(tup.relation, tup)
            object_type = _refine_object_type(RELATION_OBJECT_TYPE.get(tup.relation, "Claim"), tup)
            if subject_type in _ALIAS_ELIGIBLE_TYPES:
                by_type.setdefault(subject_type, []).append(tup.subject)
            if object_type in _ALIAS_ELIGIBLE_TYPES:
                by_type.setdefault(object_type, []).append(tup.object)
    return by_type


def _compute_alias_maps(extractions: list[PaperExtraction]) -> dict[str, dict[str, str]]:
    by_type = _collect_labels_by_type(extractions)
    result: dict[str, dict[str, str]] = {}
    for ntype, labels in by_type.items():
        jaccard_map = _build_alias_map(labels)
        acronym_map = _build_acronym_alias_map(labels) if ntype == "Method" else {}
        # Merge both maps; Jaccard map takes precedence on conflict
        merged = {**acronym_map, **jaccard_map}
        if merged:
            result[ntype] = merged
    return result


def _resolve_label(ntype: str, label: str, alias_maps: dict[str, dict[str, str]]) -> str:
    return alias_maps.get(ntype, {}).get(label, label)


# ---------------------------------------------------------------------------
# Fix 3: Edge deduplication
# ---------------------------------------------------------------------------

def _dedup_parallel_edges(graph: nx.MultiDiGraph) -> int:
    """Merge parallel edges with the same (u, v, relation) into one.

    Combines paper_ids and evidence; keeps the highest-confidence copy.
    Returns the number of edges removed.
    """
    to_remove: list[tuple[str, str, str]] = []
    for u, v in list(set((u, v) for u, v, _ in graph.edges(keys=True))):
        if not graph.has_node(u) or not graph.has_node(v):
            continue
        edges_by_rel: dict[str, list[tuple[str, dict]]] = {}
        for key, data in list(graph[u][v].items()):
            rel = data.get("relation", "")
            edges_by_rel.setdefault(rel, []).append((key, data))
        for rel, edge_list in edges_by_rel.items():
            if len(edge_list) <= 1:
                continue
            edge_list.sort(key=lambda x: x[1].get("confidence", 0), reverse=True)
            keep_key, keep_data = edge_list[0]
            merged_pids = list(keep_data.get("paper_ids", []))
            merged_ev = list(keep_data.get("evidence", []))
            for rm_key, rm_data in edge_list[1:]:
                for pid in rm_data.get("paper_ids", []):
                    if pid not in merged_pids:
                        merged_pids.append(pid)
                merged_ev.extend(rm_data.get("evidence", []))
                to_remove.append((u, v, rm_key))
            keep_data["paper_ids"] = merged_pids
            keep_data["evidence"] = merged_ev
            keep_data["support_count"] = len(merged_pids)
    removed = 0
    for u, v, key in to_remove:
        if graph.has_edge(u, v, key=key):
            graph.remove_edge(u, v, key=key)
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# Fix 4: Field-norm assumption flagging
# ---------------------------------------------------------------------------

def _flag_field_norm_assumptions(graph: nx.MultiDiGraph, total_papers: int, threshold: float = 0.5) -> int:
    """Flag Assumption nodes present in >= threshold fraction of papers as field_norm=True."""
    if total_papers == 0:
        return 0
    flagged = 0
    for _, data in graph.nodes(data=True):
        if data.get("type") == "Assumption":
            n_papers = len(set(data.get("paper_ids", [])))
            fraction = n_papers / total_papers
            data["field_norm"] = fraction >= threshold
            data["field_norm_fraction"] = round(fraction, 3)
            if data["field_norm"]:
                flagged += 1
    return flagged


# ---------------------------------------------------------------------------
# Main graph builder
# ---------------------------------------------------------------------------

def build_knowledge_graph(ctx: Any) -> nx.MultiDiGraph:
    ctx.stage_start("build_graph")
    papers = {p.arxiv_id: p for p in read_manifest(ctx.run_dir)}
    extractions = load_extractions(ctx)
    total_papers = len(extractions)

    # Fix 2: compute alias maps from all entity labels before building
    alias_maps = _compute_alias_maps(extractions)
    total_aliases = sum(len(v) for v in alias_maps.values())

    graph = nx.MultiDiGraph()
    for extraction in extractions:
        paper = papers.get(extraction.paper_id)
        paper_node = f"paper:{extraction.paper_id}"
        graph.add_node(
            paper_node,
            type="Paper",
            label=paper.title if paper else extraction.paper_id,
            paper_ids=[extraction.paper_id],
            arxiv_id=extraction.paper_id,
            evidence=[],
        )
        for field, ntype in LIST_FIELD_TYPES.items():
            for value in getattr(extraction, field, []) or []:
                if not value or value == "insufficient evidence":
                    continue
                canonical = _resolve_label(ntype, value, alias_maps)
                # Fix 5: skip generic labels that merge unrelated entities across papers
                if ntype == "Method" and _is_junk_label(canonical):
                    continue
                node_id = entity_node_id(ntype, canonical)
                add_entity_node(graph, node_id, ntype, canonical, extraction.paper_id, field)
                add_edge(graph, paper_node, node_id, "mentions", extraction.paper_id, evidence_text=canonical, section=field)
        for tup in extraction.tuples:
            add_tuple(graph, extraction.paper_id, tup, alias_maps=alias_maps)

    # Fix 3: merge duplicate edges across papers
    removed_edges = _dedup_parallel_edges(graph)

    # Fix 4: flag field-norm assumptions
    flagged_assumptions = _flag_field_norm_assumptions(graph, total_papers)

    append_jsonl(
        ctx.path("graph", "build_graph_postprocess.jsonl"),
        {
            "timestamp": utc_now_iso(),
            "total_papers": total_papers,
            "alias_merges": total_aliases,
            "edges_deduped": removed_edges,
            "field_norm_assumptions": flagged_assumptions,
        },
    )

    export_graph(graph, ctx.path("graph"))
    write_json(ctx.path("graph", "graph_schema.json"), GRAPH_SCHEMA)
    write_pyvis_html(
        graph,
        ctx.path("graph", "visualizations", "full_graph_overview.html"),
        max_nodes=int(ctx.config.get("graph", {}).get("max_visualization_nodes", 500)),
    )
    ctx.stage_end("build_graph", nodes=graph.number_of_nodes(), edges=graph.number_of_edges())
    return graph


def add_tuple(
    graph: nx.MultiDiGraph,
    paper_id: str,
    tup: ScientificTuple,
    alias_maps: dict[str, dict[str, str]] | None = None,
) -> None:
    relation = tup.relation
    object_type = RELATION_OBJECT_TYPE.get(relation, "Claim")
    subject_type = infer_subject_type(relation, tup)
    object_type = _refine_object_type(object_type, tup)

    # Fix 2: resolve aliases before computing node IDs
    am = alias_maps or {}
    subject_label = _resolve_label(subject_type, tup.subject, am)
    object_label = _resolve_label(object_type, tup.object, am)

    # Fix 5: drop tuples whose subject resolves to a junk label
    if subject_type == "Method" and _is_junk_label(subject_label):
        return

    source = entity_node_id(subject_type, subject_label)
    target = entity_node_id(object_type, object_label)
    add_entity_node(graph, source, subject_type, subject_label, paper_id, "tuple_subject", tup)
    add_entity_node(graph, target, object_type, object_label, paper_id, "tuple_object", tup)
    add_edge(
        graph, source, target, relation, paper_id,
        evidence_text=tup.evidence_text,
        section=tup.section,
        confidence=tup.confidence,
        claim_type=getattr(tup, "claim_type", "unknown"),
        polarity=getattr(tup, "polarity", "unknown"),
        condition=getattr(tup, "condition", ""),
        direction=getattr(tup, "direction", "unknown"),
        evidence_type=getattr(tup, "evidence_type", "unknown"),
        strength=getattr(tup, "strength", "unknown"),
        subject_scope=getattr(tup, "subject_scope", "own_method"),
        resolved_by_paper=getattr(tup, "resolved_by_paper", False),
    )


def infer_subject_type(relation: str, tup: ScientificTuple | None = None) -> str:
    if relation in {"contradicts"}:
        return "Claim"
    if tup is not None:
        ct = getattr(tup, "claim_type", "unknown")
        if ct in {"failure", "limitation"}:
            return "Method"
        if ct == "assumption":
            return "Method"
        if ct == "evaluation":
            return "Method"
    return "Method"


def _refine_object_type(default_type: str, tup: ScientificTuple) -> str:
    """Use claim_type to refine the object node type when RELATION_OBJECT_TYPE gives a generic fallback."""
    ct = getattr(tup, "claim_type", "unknown")
    if default_type == "Claim":
        if ct == "failure":
            return "FailureCondition"
        if ct == "limitation":
            return "Limitation"
        if ct == "assumption":
            return "Assumption"
        if ct == "result":
            return "Result"
    return default_type


def entity_node_id(ntype: str, label: str) -> str:
    return stable_id(ntype.lower(), normalize_label(label))


def add_entity_node(graph: nx.MultiDiGraph, node_id: str, ntype: str, label: str, paper_id: str, source_field: str, source_obj: Any | None = None) -> None:
    evidence = {"paper_id": paper_id, "source_field": source_field}
    if source_obj is not None:
        evidence["source"] = model_dump(source_obj)
    if graph.has_node(node_id):
        data = graph.nodes[node_id]
        if paper_id not in data.setdefault("paper_ids", []):
            data["paper_ids"].append(paper_id)
        data.setdefault("evidence", []).append(evidence)
    else:
        graph.add_node(node_id, type=ntype, label=label, paper_ids=[paper_id], evidence=[evidence])


def add_edge(graph: nx.MultiDiGraph, source: str, target: str, relation: str, paper_id: str, **attrs: Any) -> str:
    edge_id = stable_id("edge", source, relation, target, paper_id, attrs.get("evidence_text", ""))
    evidence = {
        "paper_id": paper_id,
        "evidence_text": attrs.get("evidence_text", ""),
        "section": attrs.get("section", ""),
        "confidence": attrs.get("confidence", None),
    }
    graph.add_edge(source, target, key=edge_id, id=edge_id, relation=relation, paper_ids=[paper_id], evidence=[evidence], **attrs)
    return edge_id
