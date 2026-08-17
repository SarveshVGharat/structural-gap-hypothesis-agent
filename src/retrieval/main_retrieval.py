"""CLI: python -m retrieval.main_retrieval --config configs/retrieval_icl_theory.yaml [overrides]

All topic-specific behaviour is driven by the config file.
No hardcoded ICL or domain-specific logic lives here.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _write_jsonl(path: Path, records: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            obj = r.model_dump() if hasattr(r, "model_dump") else (r.__dict__ if hasattr(r, "__dict__") else r)
            f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _log(msg: str) -> None:
    print(msg, flush=True)


# ── Config loading ────────────────────────────────────────────────────────────

def _load_config(config_path: str | None, query: str | None, cli_overrides: dict[str, Any]) -> "Any":
    from .config import RetrievalConfig

    defaults_path = Path(__file__).parent.parent / "configs" / "retrieval_default.yaml"

    if config_path:
        cfg = RetrievalConfig.from_yaml_with_defaults(config_path, defaults_path if defaults_path.exists() else None)
    else:
        cfg = RetrievalConfig.from_yaml(defaults_path) if defaults_path.exists() else RetrievalConfig()

    # CLI --query overrides config.query.text
    if query:
        data = cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.__dict__
        data.setdefault("query", {})["text"] = query
        cfg = RetrievalConfig.model_validate(data) if hasattr(RetrievalConfig, "model_validate") else RetrievalConfig(**data)

    if cli_overrides:
        cfg = cfg.apply_cli_overrides(cli_overrides)

    return cfg


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_with_config(config: "Any") -> Path:
    """Run the full retrieval pipeline using a RetrievalConfig."""
    from .candidate_collector import collect_candidates_with_config
    from .dedup import deduplicate
    from .embedding_reranker import rerank, rerank_cross_encoder
    from .mmr import mmr_select
    from .query_expander import attach_profile_expansions, expand_from_intent, expand_query_with_llm
    from .query_intent import build_intent
    from .relevance_filter import score_and_filter_with_intent

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = config.logging.output_dir
    run_dir = (Path(out_dir) if out_dir else Path("runs")) / f"retrieval_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    verbose = config.logging.verbose
    log = _log if verbose else (lambda m: None)
    log(f"[retrieval] Output dir: {run_dir}")
    log(f"[retrieval] Profile: {config.query.topic_profile or 'none (generic)'}")

    # Save effective config for reproducibility
    if config.logging.save_audit_trail:
        try:
            config.dump_yaml(run_dir / "effective_retrieval_config.yaml")
        except Exception:
            _write_json(run_dir / "effective_retrieval_config.json",
                        config.model_dump() if hasattr(config, "model_dump") else {})

    # ── 1. Build intent ───────────────────────────────────────────────────────
    log("[retrieval] Step 1/8: Building retrieval intent...")
    intent = build_intent(config)

    # ── 2. Query expansion ────────────────────────────────────────────────────
    log("[retrieval] Step 2/8: Expanding query...")
    intent = attach_profile_expansions(intent, config)
    query = config.query.text

    beh = config.behavior
    if beh.llm_base_url:
        expanded = expand_query_with_llm(query, base_url=beh.llm_base_url, model=beh.llm_model or "Qwen/Qwen3.5-9B", intent=intent)
        expansion_method = "llm"
    else:
        expanded = expand_from_intent(intent)
        expansion_method = "profile_rule_based"

    intent.expanded_queries = expanded
    log(f"  Original: {query}")
    for i, q in enumerate(expanded[1:], 1):
        log(f"  Variant {i}: {q}")

    _write_json(run_dir / "query_expansion.json", {
        "original_query": query,
        "expanded_queries": expanded,
        "expansion_method": expansion_method,
        "intent_mode": intent.intent_mode,
        "profile": intent.profile_name,
        "must_have_phrases": intent.must_have_phrases[:10],
        "exclude_phrases": intent.exclude_phrases[:10],
    })

    # ── 3. Multi-source candidate collection ──────────────────────────────────
    log(f"[retrieval] Step 3/8: Collecting candidates (sources: {config.sources.enabled})...")
    raw_candidates, backend_status = collect_candidates_with_config(
        expanded, config, intent, logger=log,
    )
    _write_json(run_dir / "backend_status.json", backend_status)
    _write_jsonl(run_dir / "raw_candidates.jsonl", [c.model_dump() for c in raw_candidates])
    log(f"  Raw candidates: {len(raw_candidates)}")

    # ── 4. Deduplication ──────────────────────────────────────────────────────
    log("[retrieval] Step 4/8: Deduplicating...")
    deduped = deduplicate(raw_candidates)
    _write_jsonl(run_dir / "deduped_candidates.jsonl", [c.model_dump() for c in deduped])
    log(f"  After dedup: {len(deduped)} (removed {len(raw_candidates) - len(deduped)})")

    # ── 5. Relevance scoring + filtering ─────────────────────────────────────
    log("[retrieval] Step 5/8: Relevance scoring and filtering...")
    kept, rejected = score_and_filter_with_intent(deduped, intent, config.scoring)
    log(f"  Kept: {len(kept)}, Rejected: {len(rejected)}")

    all_scored_records = []
    for sc in kept + rejected:
        d = sc.candidate.model_dump()
        d.update({
            "metadata_score": sc.metadata_score,
            "matched_positive_phrases": sc.matched_positive_phrases,
            "matched_anchor_phrases": sc.matched_anchor_phrases,
            "matched_negative_phrases": sc.matched_negative_phrases,
            "keep": sc.keep,
            "rejection_reason": sc.rejection_reason,
            "score_breakdown": sc.score_breakdown,
        })
        all_scored_records.append(d)
    _write_jsonl(run_dir / "candidates_scored.jsonl", all_scored_records)
    _write_jsonl(run_dir / "rejected_candidates.jsonl", [
        {
            "paper_id": sc.candidate.paper_id,
            "title": sc.candidate.title,
            "score": sc.metadata_score,
            "matched_positive_phrases": sc.matched_positive_phrases,
            "matched_negative_phrases": sc.matched_negative_phrases,
            "rejection_reason": sc.rejection_reason,
        }
        for sc in rejected
    ])

    if not kept:
        log("  WARNING: All candidates rejected. Lowering threshold and retrying...")
        kept, rejected = score_and_filter_with_intent(deduped, intent, config.scoring, keep_threshold=0.0)
        log(f"  After threshold=0: kept {len(kept)}")

    # ── 6. Embedding reranking ────────────────────────────────────────────────
    if beh.use_embeddings and kept:
        log("[retrieval] Step 6/8: Embedding reranking...")
        kept = rerank(query, kept, model_cache_dir=beh.model_cache_dir, logger=log)
        if beh.use_cross_encoder:
            log("  Running cross-encoder reranking...")
            kept = rerank_cross_encoder(query, kept, logger=log)
    else:
        log("[retrieval] Step 6/8: Skipping embedding reranking (use_embeddings=false).")

    # ── 7. MMR diversity selection ────────────────────────────────────────────
    div = config.diversity
    final_k = beh.final_k
    if beh.use_embeddings and len(kept) > final_k:
        log(f"[retrieval] Step 7/8: MMR diversity selection (k={final_k}, λ={div.lambda_mult})...")
        selected = mmr_select(kept, k=final_k, lambda_mult=div.lambda_mult, model_cache_dir=beh.model_cache_dir, logger=log)
    else:
        log(f"[retrieval] Step 7/8: Selecting top-{final_k} by metadata score...")
        selected = kept[:final_k]
    log(f"  Selected: {len(selected)} papers")

    # ── 8. Optional PDF download ──────────────────────────────────────────────
    pdf_dir = run_dir / "downloaded_pdfs"
    if beh.download_pdfs:
        log("[retrieval] Step 8/8: Downloading PDFs for selected papers...")
        _download_pdfs(selected, pdf_dir)
    else:
        log("[retrieval] Step 8/8: PDF download skipped (download_pdfs=false).")

    # ── Write selected papers ─────────────────────────────────────────────────
    selected_records = []
    for rank, sc in enumerate(selected, 1):
        c = sc.candidate
        selected_records.append({
            "rank": rank,
            "paper_id": c.paper_id,
            "title": c.title,
            "abstract": c.abstract[:300] + "..." if len(c.abstract) > 300 else c.abstract,
            "authors": c.authors[:5],
            "year": c.year,
            "venue": c.venue,
            "source_names": c.source_names,
            "arxiv_id": c.arxiv_id,
            "doi": c.doi,
            "pdf_url": c.pdf_url,
            "citation_count": c.citation_count,
            "metadata_score": sc.metadata_score,
            "combined_score": sc.score_breakdown.get("combined_score", sc.metadata_score),
            "matched_positive_phrases": sc.matched_positive_phrases,
            "matched_anchor_phrases": sc.matched_anchor_phrases,
            "retrieval_queries": c.retrieval_queries,
            "score_breakdown": sc.score_breakdown,
        })
    _write_json(run_dir / "selected_papers.json", selected_records)

    # ── Summary report ────────────────────────────────────────────────────────
    summary = _build_summary(
        config=config, intent=intent, expanded=expanded,
        expansion_method=expansion_method, backend_status=backend_status,
        raw_count=len(raw_candidates), deduped_count=len(deduped),
        kept_count=len(kept), rejected=rejected, selected=selected,
        run_dir=run_dir,
    )
    (run_dir / "retrieval_summary.md").write_text(summary, encoding="utf-8")
    _log(f"\n[retrieval] Done. Summary: {run_dir / 'retrieval_summary.md'}")
    return run_dir


def run(
    query: str,
    *,
    sources: list[str] | None = None,
    max_results_per_query: int = 50,
    max_raw_candidates: int = 500,
    final_k: int = 20,
    use_paper_search_mcp: bool = True,
    use_embeddings: bool = True,
    use_cross_encoder: bool = False,
    use_citation_expansion: bool = False,
    download_pdfs: bool = False,
    output_dir: Path | None = None,
    model_cache_dir: str | None = None,
    llm_base_url: str | None = None,
    keep_threshold: float = 10.0,
    lambda_mult: float = 0.75,
) -> Path:
    """Backwards-compatible run() — builds a RetrievalConfig on the fly."""
    from .config import (
        DiversityConfig, LoggingConfig, QueryConfig, RetrievalBehaviorConfig,
        RetrievalConfig, RunConfig, SourceConfig,
    )

    src_list = sources or ["arxiv", "semantic_scholar", "openalex"]
    cfg = RetrievalConfig(
        run=RunConfig(description="ad-hoc run"),
        query=QueryConfig(text=query, intent="balanced"),
        sources=SourceConfig(
            enabled=src_list,
            max_results_per_query=max_results_per_query,
            max_raw_candidates=max_raw_candidates,
            use_paper_search_mcp=use_paper_search_mcp,
        ),
        behavior=RetrievalBehaviorConfig(
            final_k=final_k,
            use_embeddings=use_embeddings,
            use_cross_encoder=use_cross_encoder,
            use_citation_expansion=use_citation_expansion,
            download_pdfs=download_pdfs,
            llm_base_url=llm_base_url,
            model_cache_dir=model_cache_dir,
        ),
        diversity=DiversityConfig(lambda_mult=lambda_mult),
        logging=LoggingConfig(output_dir=str(output_dir) if output_dir else None),
    )
    cfg.scoring.keep_threshold = keep_threshold
    return run_with_config(cfg)


# ── PDF download ──────────────────────────────────────────────────────────────

def _download_pdfs(scored: list, pdf_dir: Path) -> None:
    import requests
    pdf_dir.mkdir(parents=True, exist_ok=True)
    for sc in scored:
        c = sc.candidate
        urls = [u for u in [c.pdf_url, _arxiv_pdf(c.arxiv_id)] if u]
        downloaded = False
        for url in urls:
            safe = (c.arxiv_id or c.paper_id).replace("/", "_").replace(":", "_")
            dest = pdf_dir / f"{safe}.pdf"
            if dest.exists():
                c.pdf_url = str(dest)
                downloaded = True
                break
            try:
                with requests.get(url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with dest.open("wb") as f:
                        for chunk in r.iter_content(1024 * 256):
                            if chunk:
                                f.write(chunk)
                c.pdf_url = str(dest)
                downloaded = True
                break
            except Exception:
                continue
        if not downloaded:
            _log(f"    No PDF available for {c.title[:50]}")


def _arxiv_pdf(arxiv_id: str | None) -> str:
    if not arxiv_id:
        return ""
    bare = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
    return f"https://arxiv.org/pdf/{bare}"


# ── Summary report ────────────────────────────────────────────────────────────

def _build_summary(*, config, intent, expanded, expansion_method, backend_status,
                   raw_count, deduped_count, kept_count, rejected, selected, run_dir) -> str:
    from collections import Counter
    query = config.query.text
    lines = [
        "# Retrieval Summary", "",
        f"**Query:** {query}",
        f"**Profile:** {intent.profile_name or 'none (generic)'}",
        f"**Intent mode:** {intent.intent_mode}",
        f"**Expansion method:** {expansion_method}",
        f"**Backends used:** {', '.join(backend_status.get('backends_used', []))}",
        f"**Venue mode:** {backend_status.get('venue_mode', config.venues.mode)}",
        "",
        "## Expanded Queries",
    ]
    for i, q in enumerate(expanded):
        lines.append(f"{i+1}. {q}")

    lines += [
        "", "## Candidate Pipeline",
        "| Stage | Count |",
        "|---|---:|",
        f"| Raw candidates | {raw_count} |",
        f"| After deduplication | {deduped_count} |",
        f"| After relevance filter | {kept_count} |",
        f"| Final selected | {len(selected)} |",
        "", "## Per-Source Counts",
    ]
    for src, cnt in backend_status.get("per_source_counts", {}).items():
        lines.append(f"- **{src}**: {cnt} raw results")

    lines += ["", "## Active Phrase Filter"]
    lines.append(f"- **Must-have (positive):** {', '.join(intent.must_have_phrases[:6]) or 'none'}")
    lines.append(f"- **Should-have (anchor):** {', '.join(intent.should_have_phrases[:4]) or 'none'}")
    lines.append(f"- **Exclude (negative):** {', '.join(intent.exclude_phrases[:6]) or 'none'}")

    lines += ["", "## Selected Papers"]
    for i, sc in enumerate(selected, 1):
        c = sc.candidate
        year = c.year or "?"
        score = sc.score_breakdown.get("combined_score", sc.metadata_score)
        lines.append(f"{i}. **{c.title}** ({year}) — score={score:.2f}, sources={c.source_names}")
        if sc.matched_positive_phrases:
            lines.append(f"   - Matched: {', '.join(sc.matched_positive_phrases[:3])}")

    lines += ["", "## Rejection Reasons (top 8)"]
    reasons = Counter(r.rejection_reason for r in rejected)
    for reason, cnt in reasons.most_common(8):
        lines.append(f"- `{reason}`: {cnt} papers")

    lines += ["", "## Top Rejected Examples (20)"]
    for sc in rejected[:20]:
        lines.append(f"- [{sc.candidate.title[:70]}] score={sc.metadata_score:.1f} — {sc.rejection_reason}")
        if sc.matched_negative_phrases:
            lines.append(f"  neg_phrases: {sc.matched_negative_phrases}")

    lines += ["", "## Output Files"]
    for fname in [
        "effective_retrieval_config.yaml",
        "query_expansion.json", "backend_status.json",
        "raw_candidates.jsonl", "deduped_candidates.jsonl",
        "candidates_scored.jsonl", "rejected_candidates.jsonl",
        "selected_papers.json",
    ]:
        lines.append(f"- `{run_dir / fname}`")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Config-driven multi-source research paper retrieval")
    p.add_argument("--config", default=None,
                   help="Path to a retrieval YAML config (e.g. configs/retrieval_icl_theory.yaml)")
    p.add_argument("--query", default=None,
                   help="Research query — overrides config.query.text if provided")
    # Legacy / override flags (all optional; config file takes precedence unless overridden)
    p.add_argument("--sources", nargs="+", default=None)
    p.add_argument("--max-results-per-query", type=int, default=None)
    p.add_argument("--max-raw-candidates", type=int, default=None)
    p.add_argument("--final-k", type=int, default=None)
    p.add_argument("--use-paper-search-mcp", type=lambda x: x.lower() in ("true","1","yes"), default=None)
    p.add_argument("--use-embeddings", type=lambda x: x.lower() in ("true","1","yes"), default=None)
    p.add_argument("--use-cross-encoder", type=lambda x: x.lower() in ("true","1","yes"), default=None)
    p.add_argument("--download-pdfs", type=lambda x: x.lower() in ("true","1","yes"), default=None)
    p.add_argument("--output-dir", default=None)
    p.add_argument("--llm-base-url", default=None)
    p.add_argument("--keep-threshold", type=float, default=None)
    p.add_argument("--lambda-mult", type=float, default=None)
    args = p.parse_args()

    if not args.config and not args.query:
        p.error("Provide --config <path> and/or --query <text>")

    # Build CLI overrides dict (only non-None values)
    overrides: dict = {}
    if args.sources:           overrides.setdefault("sources", {})["enabled"] = args.sources
    if args.max_results_per_query: overrides.setdefault("sources", {})["max_results_per_query"] = args.max_results_per_query
    if args.max_raw_candidates: overrides.setdefault("sources", {})["max_raw_candidates"] = args.max_raw_candidates
    if args.final_k is not None: overrides.setdefault("behavior", {})["final_k"] = args.final_k
    if args.use_paper_search_mcp is not None: overrides.setdefault("sources", {})["use_paper_search_mcp"] = args.use_paper_search_mcp
    if args.use_embeddings is not None: overrides.setdefault("behavior", {})["use_embeddings"] = args.use_embeddings
    if args.use_cross_encoder is not None: overrides.setdefault("behavior", {})["use_cross_encoder"] = args.use_cross_encoder
    if args.download_pdfs is not None: overrides.setdefault("behavior", {})["download_pdfs"] = args.download_pdfs
    if args.output_dir:         overrides.setdefault("logging", {})["output_dir"] = args.output_dir
    if args.llm_base_url:       overrides.setdefault("behavior", {})["llm_base_url"] = args.llm_base_url
    if args.keep_threshold is not None: overrides.setdefault("scoring", {})["keep_threshold"] = args.keep_threshold
    if args.lambda_mult is not None: overrides.setdefault("diversity", {})["lambda_mult"] = args.lambda_mult

    config = _load_config(args.config, args.query, overrides)
    run_with_config(config)


if __name__ == "__main__":
    main()
