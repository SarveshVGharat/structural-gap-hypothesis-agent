from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from .corpus_manifest import read_manifest
from .graph_export import load_graph
from .graph_schema import GRAPH_SCHEMA
from .utils import read_json, read_jsonl, read_text, write_text, write_json, write_csv

_FORBIDDEN_ABSTRACT_PHRASES = (
    "we prove", "we show", "our experiments demonstrate", "this paper establishes",
    "we demonstrate", "we establish", "results show that",
)


def _deterministic_abstract(hyp: dict, *, author_context: str = "", min_words: int = 100) -> dict:
    """Proposal-style fallback abstract built without an LLM. Never uses result language."""
    ps = (hyp.get("problem_statement") or hyp.get("gap") or "this structural research gap").strip().rstrip(".")
    motif = ", ".join(hyp.get("origin_motif_types", []) or ([hyp.get("motif_type")] if hyp.get("motif_type") else [])) or "an identified structural gap"
    sup = hyp.get("supporting_papers", []) or []
    mech = (hyp.get("mechanism") or "").strip()
    scope = (hyp.get("remaining_gap_scope") or "").strip()
    parts = [
        f"This project studies {ps}.",
        f"The central question arises from {motif} observed across the corpus"
        + (f" ({len(sup)} supporting papers)." if sup else "."),
    ]
    if mech:
        parts.append(f"A possible approach is suggested by the mechanism: {mech}.")
    else:
        parts.append("A possible approach would formalize the gap and test it against the supporting evidence.")
    if scope:
        parts.append(f"The remaining open scope is: {scope}.")
    parts.append("A successful outcome would clarify when the underlying assumptions hold and provide a concrete, testable account of the gap.")
    if author_context:
        parts.append(f"This question also connects to the author profile: {author_context}.")
    text = " ".join(parts)
    # pad cautiously toward min_words without adding claims
    if len(text.split()) < min_words:
        text += (" This project would investigate the conditions, evidence, and falsifiable "
                 "predictions needed to turn the observed gap into a well-posed research problem.")
    return {
        "proposal_style_abstract": text,
        "abstract_generation_rationale": "fallback",
        "abstract_evidence_papers": sup[:8],
        "abstract_counterevidence_papers": (hyp.get("counterevidence_papers", []) or [])[:8],
    }


def generate_final_abstracts(ctx: Any, finals: list[dict], *, llm: Any = None,
                             author_context_by_id: dict | None = None) -> dict:
    """Attach proposal_style_abstract to each final hypothesis (LLM if available, else
    deterministic fallback). Returns summary counts. Idempotent: skips hyps already having one."""
    rcfg = (ctx.config.get("reporting", {}) or {})
    if not rcfg.get("include_problem_abstracts", True):
        return {"generated": 0, "fallback": 0, "failures": 0, "skipped": len(finals), "enabled": False}
    from .prompt_templates import generate_problem_abstract_prompt
    min_w = int(rcfg.get("abstract_min_words", 100)); max_w = int(rcfg.get("abstract_max_words", 220))
    acbi = author_context_by_id or {}
    gen = fb = fail = skip = 0
    # llm semantics: False -> never use an LLM (pure deterministic fallback); None -> lazily
    # construct the default client; an object -> use it as-is (tests inject mocks).
    if llm is False:
        _llm = None
    elif llm is None:
        try:
            from .llm_client import LLMClient
            _llm = LLMClient(ctx)
        except Exception:
            _llm = None
    else:
        _llm = llm
    for hyp in finals:
        if hyp.get("proposal_style_abstract"):
            skip += 1
            continue
        payload = {
            "problem_statement": hyp.get("problem_statement", ""),
            "short_title": hyp.get("hypothesis_id", ""),
            "origin_motif_type": hyp.get("origin_motif_types", []) or hyp.get("motif_type", ""),
            "gap_description": hyp.get("gap", "") or hyp.get("original_gap_description", ""),
            "supporting_paper_snippets": [ (e.get("evidence_text","") if isinstance(e,dict) else str(e))
                                           for e in (hyp.get("supporting_evidence", []) or [])[:6]],
            "supporting_papers": hyp.get("supporting_papers", []),
            "counterevidence_snippets": [ (e.get("rationale") or e.get("evidence_text","")) if isinstance(e,dict) else str(e)
                                          for e in (hyp.get("counterevidence", []) or [])[:6]],
            "remaining_gap_scope": hyp.get("remaining_gap_scope", ""),
            "mechanism": hyp.get("mechanism", ""),
            "feasibility": hyp.get("feasibility_score", ""),
            "proposed_contribution_type": hyp.get("target", ""),
        }
        author_context = acbi.get(hyp.get("hypothesis_id"), "")
        result = None
        if _llm is not None:
            try:
                raw, *_ = _llm.complete_json(
                    stage="evolution", agent_name="problem_abstract",
                    prompt=generate_problem_abstract_prompt(payload, min_words=min_w, max_words=max_w,
                                                            author_context=author_context),
                    schema_name="ProblemAbstract")
                abs_text = str(raw.get("proposal_style_abstract", "")).strip()
                low = abs_text.lower()
                if abs_text and not any(p in low for p in _FORBIDDEN_ABSTRACT_PHRASES):
                    result = {
                        "proposal_style_abstract": abs_text,
                        "abstract_generation_rationale": str(raw.get("abstract_generation_rationale", "llm")) or "llm",
                        "abstract_evidence_papers": list(raw.get("abstract_evidence_papers", []) or [])[:8],
                        "abstract_counterevidence_papers": list(raw.get("abstract_counterevidence_papers", []) or [])[:8],
                    }
                    gen += 1
            except Exception:
                result = None
        if result is None:
            result = _deterministic_abstract(hyp, author_context=author_context, min_words=min_w)
            if _llm is None:
                fb += 1
            else:
                fail += 1  # LLM was available but failed/unusable -> fell back
        hyp.update(result)
    return {"generated": gen, "fallback": fb, "failures": fail, "skipped": skip, "enabled": True}


def personalize_finals(ctx: Any, finals: list[dict]) -> dict:
    """If personalization is enabled, attach author-alignment fields, original/personalized
    scores, and (optionally) rerank by personalized_score. Returns context for the report.
    No-op (returns enabled=False) otherwise — non-personalized runs are unchanged."""
    pers = (ctx.config.get("personalization", {}) or {})
    if not pers.get("enabled", False):
        return {"enabled": False}
    from .personalization import (personalized_score, compute_seed_alignment_score,
                                  deterministic_seed_alignment)
    # Recommended mode: manual seed papers (profile/seed_papers.jsonl). Falls back to the
    # legacy author-profile file only if no seed papers are present.
    seed_papers = read_jsonl(ctx.path("profile", "seed_papers.jsonl"))
    if not seed_papers:
        seed_papers = read_jsonl(ctx.path("corpus", "selected_seed_papers.jsonl")) or []
        seed_papers = [p for p in seed_papers if p.get("is_manual_seed_paper")]
    rels = read_jsonl(ctx.path("corpus", "paper_relationships.jsonl"))
    for hyp in finals:
        orig = float(hyp.get("fitness", 0.0) or 0.0)
        hyp["original_score"] = orig
        align = compute_seed_alignment_score(hyp.get("supporting_papers", []), seed_papers, rels)
        hyp["seed_alignment_score"] = align
        hyp["author_alignment_score"] = align  # backward-compat mirror
        expl = deterministic_seed_alignment(hyp, seed_papers, rels)
        hyp.update(expl)
        hyp["related_author_papers"] = expl.get("related_seed_papers", [])  # back-compat mirror
        hyp["personalized_score"] = personalized_score(
            structural_gap_score=orig, seed_alignment_score=align,
            novelty_score=float(hyp.get("novelty_score", 0.0) or 0.0),
            feasibility_score=float(hyp.get("feasibility_score", 0.0) or 0.0), config=ctx.config)
    rerank = (pers.get("ranking", {}) or {}).get("use_personalized_reranking", True)
    if rerank:
        for h in finals: h["original_rank"] = h.get("rank")
        finals.sort(key=lambda h: -float(h.get("personalized_score", 0.0)))
        for i, h in enumerate(finals, 1): h["personalized_rank"] = i
    seed_ctx = {}
    for hyp in finals:
        rp = hyp.get("related_seed_papers") or []
        if rp:
            seed_ctx[hyp.get("hypothesis_id")] = f"relates to seed papers {rp[:3]}"
    return {"enabled": True, "seed_papers": seed_papers, "relationships": rels,
            "reranked": bool(rerank), "author_context_by_id": seed_ctx}


def build_report(ctx: Any) -> tuple[Path, Path]:
    ctx.stage_start("report")
    lines: list[str] = []
    lines.append(f"# Structural Gap Hypothesis Agent Report")
    lines.append("")
    lines.append("## 1. Run Metadata")
    lines.append(f"- Run ID: `{ctx.run_id}`")
    lines.append(f"- Run directory: `{ctx.run_dir}`")
    lines.append(f"- Output root: `{ctx.output_root}`")
    lines.append(f"- Dataset root: `{ctx.dataset_root}`")
    lines.append("")
    lines.append("## 2. arXiv Query")
    query = read_json(ctx.path("arxiv", "query.json"), default={})
    lines.append(f"- Query: `{query.get('query', ctx.config.get('query', ''))}`")
    lines.append(f"- Max results: `{query.get('max_results', ctx.config.get('max_results', ''))}`")
    lines.append("")
    lines.append("## 3. Downloaded Papers")
    papers = read_manifest(ctx.run_dir)
    for p in papers:
        lines.append(f"- `{p.arxiv_id}` {p.title} | status={p.download_status} | pdf=`{p.local_pdf_path}`")
    lines.append("")
    lines.append("## 4. Parsing Summary")
    parse_quality = read_json(ctx.path("parsed", "parse_quality.json"), default={})
    lines.append(f"- Parsed paper records: `{len(parse_quality)}`")
    for pid, q in parse_quality.items():
        lines.append(f"- `{pid}`: {q}")
    lines.append("")
    lines.append("## 5. Extraction Schema")
    lines.append("```json")
    lines.append(_json_block(read_json(ctx.path("extracted", "all_extractions.json"), default=[])[0] if read_json(ctx.path("extracted", "all_extractions.json"), default=[]) else {"schema": "PaperExtraction"}))
    lines.append("```")
    lines.append("")
    lines.append("## 6. Prompt Templates Used")
    for prompt in sorted(ctx.path("prompts").glob("**/*")):
        if prompt.is_file():
            rel = prompt.relative_to(ctx.run_dir)
            lines.append(f"- `{rel}`")
    lines.append("")
    lines.append("## 7. LLM Calls")
    calls = read_jsonl(ctx.path("logs", "llm_calls.jsonl"))
    successes = sum(1 for c in calls if c.get("success"))
    lines.append(f"- Total calls: `{len(calls)}`")
    lines.append(f"- Successful calls: `{successes}`")
    lines.append(f"- Failed calls: `{len(calls) - successes}`")
    lines.append("")
    lines.append("## 8. Graph Schema")
    lines.append("```json")
    lines.append(_json_block(GRAPH_SCHEMA))
    lines.append("```")
    lines.append("")
    lines.append("## 9. Graph Statistics")
    graph_path = ctx.path("graph", "graph.json")
    if graph_path.exists():
        graph = load_graph(graph_path)
        lines.append(f"- Nodes: `{graph.number_of_nodes()}`")
        lines.append(f"- Edges: `{graph.number_of_edges()}`")
    lines.append(f"- Visualization: `{ctx.path('graph', 'visualizations', 'full_graph_overview.html')}`")
    lines.append("")
    lines.append("## 10. Motif Queries And Hits")
    motifs = read_json(ctx.path("motifs", "motif_hits.json"), default=[])
    lines.append(f"- Motif hits: `{len(motifs)}`")
    activation_data = read_json(ctx.path("motifs", "motif_activation.json"), default={})
    if activation_data:
        lines.append("")
        lines.append("### Motif Activation")
        lines.append(f"- Profile: `{activation_data.get('profile') or 'none'}`")
        lines.append(f"- Default enabled: `{activation_data.get('default_enabled', False)}`")
        lines.append(f"- Normal motifs: {activation_data.get('normal', [])}")
        lines.append(f"- Strict motifs: {activation_data.get('strict', [])}")
        lines.append(f"- Disabled motifs: {activation_data.get('disabled', [])}")
        lines.append(f"- Hits by type: {activation_data.get('hits_by_type', {})}")
    for hit in motifs[:50]:
        lines.append(f"- `{hit.get('motif_id')}` {hit.get('motif_type')}: {hit.get('description')}")
    lines.append("")
    lines.append("## 11. Candidate Gaps")
    gaps = read_json(ctx.path("gaps", "candidate_gaps.json"), default=[])
    for gap in gaps[:50]:
        lines.append(f"- `{gap.get('gap_id')}` score={gap.get('overall_score')}: {gap.get('gap')}")
    lines.append("")
    lines.append("## 12. Verification / Stress Test")
    scores = read_text(ctx.path("verification", "gap_survival_scores.csv"), default="")
    lines.append("```csv")
    lines.append(scores.strip())
    lines.append("```")
    lines.append("")
    lines.append("## 13. Evolutionary Algorithm Settings")
    lines.append("```json")
    lines.append(_json_block(ctx.config.get("evolution", {})))
    lines.append("```")
    lines.append("")
    lines.append("## 14. Generation-by-Generation Summary")
    for gen in sorted(ctx.path("evolution").glob("generation_*.json")):
        data = read_json(gen, default={})
        pop = data.get("population", [])
        best = max((c.get("fitness", 0.0) for c in pop), default=0.0)
        lines.append(f"- `{gen.name}` population={len(pop)} best_fitness={best:.3f}")
    lines.append("")
    lines.append("## 15. Final Ranked Hypotheses")
    finals = read_json(ctx.path("final", "ranked_hypotheses.json"), default=[])
    # --- Personalization enrichment (no-op if disabled) ---
    pctx = personalize_finals(ctx, finals)
    # --- Proposal-style abstracts for every final hypothesis (Feature A) ---
    abs_summary = generate_final_abstracts(
        ctx, finals, author_context_by_id=pctx.get("author_context_by_id") if pctx.get("enabled") else None)
    # persist enriched hypotheses back to json + csv so all final outputs are consistent
    if finals:
        write_json(ctx.path("final", "ranked_hypotheses.json"), finals)
        write_csv(ctx.path("final", "ranked_hypotheses.csv"), [_csv_row(h, pctx.get("enabled", False)) for h in finals])
    # report-level abstract summary
    if abs_summary.get("enabled", True):
        missing = sum(1 for h in finals if not h.get("proposal_style_abstract"))
        lines.append(f"- Proposal-style abstracts generated (LLM): {abs_summary['generated']} | "
                     f"fallback: {abs_summary['fallback']} | LLM failures→fallback: {abs_summary['failures']} | "
                     f"already-present: {abs_summary['skipped']} | missing: {missing}")
        lines.append("")
    for hyp in finals:
        rank_str = f"Rank {hyp.get('rank')}"
        if pctx.get("enabled") and pctx.get("reranked"):
            rank_str = f"Personalized Rank {hyp.get('personalized_rank')} (original {hyp.get('original_rank')})"
        lines.append(f"### {rank_str}: {hyp.get('hypothesis_id')}")
        lines.append(f"- Problem statement: {hyp.get('problem_statement')}")
        lines.append(f"- Gap: {hyp.get('gap')}")
        lines.append(f"- Target: {hyp.get('target')}")
        lines.append(f"- Scope: {hyp.get('scope')}")
        lines.append(f"- Mechanism: {hyp.get('mechanism')}")
        lines.append(f"- Supporting papers: {hyp.get('supporting_papers')}")
        lines.append(f"- Counterevidence: {hyp.get('counterevidence')}")
        lines.append(f"- Traceability path: {hyp.get('traceability_path')}")
        lines.append(f"- Novelty: {hyp.get('novelty_score')} | Feasibility: {hyp.get('feasibility_score')} | Impact: {hyp.get('impact_score')} | Survival: {hyp.get('survival_score')} | Fitness: {hyp.get('fitness')}")
        lines.append(f"- Evolutionary lineage: {hyp.get('evolutionary_lineage')}")
        if pctx.get("enabled"):
            lines.append(f"- Original score: {hyp.get('original_score')} | Personalized score: {hyp.get('personalized_score')} | Seed-paper alignment: {hyp.get('seed_alignment_score')}")
            lines.append(f"- Seed-paper alignment: {hyp.get('seed_alignment_reason')}")
            lines.append(f"- Relationship to seed profile: {hyp.get('relationship_to_seed_profile')}")
            lines.append(f"- Related seed papers: {hyp.get('related_seed_papers')}")
        lines.append("")
        lines.append("#### Abstract")
        lines.append("")
        lines.append(hyp.get("proposal_style_abstract") or "(none)")
        lines.append("")
    if pctx.get("enabled"):
        _append_personalization_section(ctx, lines, pctx, finals)
    lines.append("## 16. Limitations And Known Failure Modes")
    lines.append("- Extraction quality depends on PDF text quality and LLM JSON adherence.")
    lines.append("- Motif detection is deterministic and transparent, but label normalization is intentionally simple in v1.")
    lines.append("- Mock LLM mode is only for smoke testing and does not produce scientific evidence.")
    lines.append("- Optional external skeptic arXiv search is disabled by default to keep runs reproducible.")

    md = "\n".join(lines).rstrip() + "\n"
    md_path = ctx.path("final", "final_report.md")
    html_path = ctx.path("final", "final_report.html")
    write_text(md_path, md)
    write_text(html_path, _markdown_to_html(md))
    ctx.stage_end("report", markdown=str(md_path), html=str(html_path))
    return md_path, html_path


def _csv_row(hyp: dict, personalized: bool) -> dict:
    """Flat CSV row for ranked_hypotheses.csv including the abstract (+ personalized cols)."""
    row = {
        "rank": hyp.get("rank"), "hypothesis_id": hyp.get("hypothesis_id"),
        "problem_statement": hyp.get("problem_statement", ""),
        "novelty_score": hyp.get("novelty_score"), "feasibility_score": hyp.get("feasibility_score"),
        "impact_score": hyp.get("impact_score"), "survival_score": hyp.get("survival_score"),
        "fitness": hyp.get("fitness"),
        "supporting_papers": "; ".join(hyp.get("supporting_papers", []) or []),
        "proposal_style_abstract": hyp.get("proposal_style_abstract", ""),
    }
    if personalized:
        row.update({
            "original_rank": hyp.get("original_rank"), "personalized_rank": hyp.get("personalized_rank"),
            "original_score": hyp.get("original_score"), "personalized_score": hyp.get("personalized_score"),
            "seed_alignment_score": hyp.get("seed_alignment_score"),
            "seed_alignment_reason": hyp.get("seed_alignment_reason", ""),
            "related_seed_papers": "; ".join(hyp.get("related_seed_papers", []) or []),
        })
    return row


def _append_personalization_section(ctx: Any, lines: list, pctx: dict, finals: list) -> None:
    pers = (ctx.config.get("personalization", {}) or {})
    g = lambda *p: read_jsonl(ctx.path(*p))
    seed_papers = pctx.get("seed_papers") or g("profile", "seed_papers.jsonl")
    topic_profile = read_json(ctx.path("profile", "seed_topic_profile.json"), default={})
    selected = g("corpus", "selected_seed_papers.jsonl")
    or_papers = [p for p in selected if not p.get("is_manual_seed_paper")]
    queries = topic_profile.get("generated_openreview_queries", [])
    lines.append("")
    lines.append("# Personalized Seed-Paper Context")
    lines.append("")
    lines.append(f"- Seed label: {topic_profile.get('seed_label') or pers.get('seed_label') or '(derived)'}")
    lines.append(f"- Topic: {topic_profile.get('topic') or pers.get('topic')}")
    lines.append(f"- Seed papers: {len(seed_papers)}")
    lines.append(f"- OpenReview topic papers: {len(or_papers)}")
    lines.append(f"- Selected corpus size: {len(selected)}")
    lines.append(f"- Seed-derived OpenReview queries ({len(queries)}): {queries[:12]}")
    reranked = pctx.get("reranked")
    lines.append(f"- Seed alignment affected ranking: {'yes — reranked by personalized_score' if reranked else 'no (reranking disabled)'}")
    lines.append("")


def _json_block(data: Any) -> str:
    import json

    return json.dumps(data, indent=2, ensure_ascii=False)


def _markdown_to_html(md: str) -> str:
    body = []
    in_code = False
    for line in md.splitlines():
        if line.startswith("```"):
            body.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
        elif in_code:
            body.append(html.escape(line))
        elif line.startswith("# "):
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            body.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            body.append(f"<p>{html.escape(line)}</p>")
        elif not line.strip():
            body.append("")
        else:
            body.append(f"<p>{html.escape(line)}</p>")
    return """<!doctype html>
<html><head><meta charset="utf-8"><title>SGHA Report</title>
<style>body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;line-height:1.5}pre{background:#f6f8fa;padding:1rem;overflow:auto}code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}</style>
</head><body>
""" + "\n".join(body) + "\n</body></html>\n"
