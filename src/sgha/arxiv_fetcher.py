from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .corpus_manifest import write_manifest
from .extraction_schemas import ArxivPaper
from .pdf_downloader import download_pdf, log_download
from .utils import ensure_dir, safe_symlink_or_copy, slugify, write_json



def fetch_arxiv_corpus(ctx: Any, *, query: str, max_results: int, output_dir: str | Path | None = None,
                       retrieval_config_path: str | None = None) -> list[ArxivPaper]:
    # --- Personalized (manual seed) corpus construction (Feature B) ---
    # When personalization is enabled with a manual seed source, build the corpus from the
    # uploaded seed papers + normal OpenReview topic retrieval (seeds first). No Google Scholar,
    # no citation crawl, no Semantic Scholar/OpenAlex. Non-personalized runs are unaffected.
    _pers = (ctx.config.get("personalization", {}) or {})
    if _pers.get("enabled", False) and (_pers.get("seed_paper_dir") or _pers.get("seed_papers_file")
                                        or _pers.get("bibtex_file")):
        return _fetch_personalized_corpus(ctx, query=query, max_results=max_results,
                                          retrieval_config_path=retrieval_config_path)

    # Venue retrieval mode: NeurIPS/ICML/ICLR papers via Semantic Scholar + LLM selection
    if retrieval_config_path and Path(retrieval_config_path).exists():
        import yaml as _yaml
        with open(retrieval_config_path, "r") as _f:
            _ret_raw = _yaml.safe_load(_f) or {}
        if _ret_raw.get("mode") == "venue":
            from .venue_retrieval import fetch_venue_papers
            return fetch_venue_papers(ctx, retrieval_config_path=retrieval_config_path)

    # Use multi-source retrieval pipeline when configured
    retrieval_cfg: dict = ctx.config.get("retrieval", {})
    if retrieval_cfg.get("enabled", False):
        return _fetch_multi_source(ctx, query=query, max_results=max_results, cfg=retrieval_cfg,
                                   retrieval_config_path=retrieval_config_path)
    # Fallback: arXiv-only (single or multi-query)
    queries: list[str] = ctx.config.get("queries", [])
    if queries:
        return _fetch_multi_query(ctx, queries=queries, max_per_query=max_results, output_dir=output_dir)
    return _fetch_single_query(ctx, query=query, max_results=max_results, output_dir=output_dir)


def seed_papers_to_arxiv(ctx: Any, seeds: list, *, download_fn=download_pdf,
                         timeout: int = 60) -> list[ArxivPaper]:
    """Convert manual SeedPapers to ArxivPaper records and download/cache their PDFs so the
    parse stage can read them. On download failure: download_status='failed: …', local_pdf_path
    stays empty (never fabricated). `download_fn` is injectable for offline tests."""
    from .utils import model_dump, sha256_file
    out: list[ArxivPaper] = []
    pdf_dir = ctx.path("arxiv", "downloaded_pdfs")
    ensure_dir(pdf_dir)
    for s in seeds:
        d = model_dump(s) if hasattr(s, "model_dump") else dict(s)
        aid = (d.get("arxiv_id") or d.get("seed_paper_id") or d.get("doi") or (d.get("title", "")[:40])).strip()
        pdf_url = d.get("pdf_url") or (f"https://arxiv.org/pdf/{d['arxiv_id']}" if d.get("arxiv_id") else "")
        local = pdf_dir / f"{slugify(aid)}.pdf"
        p = ArxivPaper(arxiv_id=str(aid), title=d.get("title", ""), abstract=d.get("abstract", ""),
                       authors=d.get("authors", []) or [], published=str(d.get("year", "") or ""),
                       pdf_url=pdf_url, local_pdf_path="", download_status="not_downloaded",
                       source_query="manual_seed")
        try:
            if local.exists():
                p.local_pdf_path = str(local); p.download_status = "cached"; p.sha256 = sha256_file(local)
            elif pdf_url:
                _, digest = download_fn(pdf_url, local, timeout=timeout)
                p.local_pdf_path = str(local); p.download_status = "downloaded"; p.sha256 = digest
            else:
                p.download_status = "no_pdf_url"
        except Exception as exc:
            p.download_status = f"failed: {exc}"; p.local_pdf_path = ""  # honest, no fabrication
        log_download(ctx.path("arxiv", "download_log.jsonl"),
                     {"arxiv_id": p.arxiv_id, "status": p.download_status, "path": p.local_pdf_path,
                      "provenance": "uploaded_seed_paper"})
        out.append(p)
    return out


def merge_personalized_corpus(seed_papers: list[ArxivPaper], openreview_papers: list[ArxivPaper],
                              *, final_k: int | None = None) -> tuple[list[ArxivPaper], list[dict]]:
    """Merge seed + OpenReview ArxivPapers, dedupe (arxiv id / openreview id / normalized title),
    preserve provenance, and cap to final_k (seeds always kept; OpenReview fills the remainder).
    Returns (manifest_papers, relationship_records). PDF paths are preserved (not reset)."""
    from .personalization import normalize_title
    def key(p: ArxivPaper) -> str:
        oid = getattr(p, "openreview_id", "") or ""
        if p.arxiv_id:
            return f"arxiv:{p.arxiv_id}"
        if oid:
            return f"or:{oid}"
        return f"title:{normalize_title(p.title)}"
    merged: dict[str, ArxivPaper] = {}
    prov: dict[str, list[str]] = {}
    is_seed: dict[str, bool] = {}
    for p in seed_papers:
        k = key(p); merged[k] = p; prov[k] = ["uploaded_seed_paper"]; is_seed[k] = True
    for p in openreview_papers:
        k = key(p)
        if k in merged:
            prov[k] = list(dict.fromkeys(prov[k] + ["openreview_topic_retrieval"]))  # overlap
        else:
            merged[k] = p; prov[k] = ["openreview_topic_retrieval"]; is_seed[k] = False
    # cap: keep all seeds, then OpenReview up to final_k total
    keys = list(merged.keys())
    if final_k and len(keys) > final_k:
        seed_keys = [k for k in keys if is_seed.get(k)]
        or_keys = [k for k in keys if not is_seed.get(k)]
        keys = seed_keys + or_keys[: max(0, final_k - len(seed_keys))]
    papers = [merged[k] for k in keys]
    rels = []
    for k in keys:
        p = merged[k]; pr = prov[k]
        relation = ("seed_and_openreview_overlap" if len(pr) > 1
                    else ("uploaded_seed_paper" if is_seed.get(k) else "openreview_topic_retrieval"))
        rels.append({"paper_id": p.arxiv_id or getattr(p, "openreview_id", "") or k,
                     "title": p.title, "relation_to_seed_profile": relation, "provenance": pr,
                     "is_manual_seed_paper": bool(is_seed.get(k)), "local_pdf_path": p.local_pdf_path,
                     "download_status": p.download_status})
    return papers, rels


def _fetch_personalized_corpus(ctx: Any, *, query: str, max_results: int,
                               retrieval_config_path: str | None = None) -> list[ArxivPaper]:
    """Manual-seed personalized corpus: seed papers (PDFs downloaded) + OpenReview topic papers
    (PDFs from the venue path). Merged/deduped with provenance; manifest carries real PDF paths.
    No Google Scholar / citation crawl / Semantic Scholar / OpenAlex."""
    import json as _json
    from .personalization import (ManualSeedPaperIngestor, build_seed_topic_profile,
                                  write_seed_topic_profile)
    from .utils import model_dump
    pers = (ctx.config.get("personalization", {}) or {})
    ccfg = pers.get("corpus", {}) or {}
    final_k = int((pers.get("openreview_expansion", {}) or {}).get("final_k", ctx.config.get("max_results", 250)))

    # 1) ingest seeds + write profile/seed_papers.jsonl + seed topic profile
    ing = ManualSeedPaperIngestor(ctx.config)
    seeds, issues = ing.ingest()
    ing.write(ctx.run_dir, seeds, issues)
    profile = build_seed_topic_profile(ctx.config, seeds)
    write_seed_topic_profile(ctx.run_dir, profile)

    # 2) seed papers -> ArxivPaper + download PDFs
    seed_arxiv = seed_papers_to_arxiv(ctx, seeds)

    # 3) OpenReview topic papers via the existing venue path (already downloads PDFs)
    or_arxiv: list[ArxivPaper] = []
    if ccfg.get("include_openreview_topic_papers", True) and retrieval_config_path and Path(retrieval_config_path).exists():
        import yaml as _yaml
        with open(retrieval_config_path) as _f:
            if (_yaml.safe_load(_f) or {}).get("mode") == "venue":
                from .venue_retrieval import fetch_venue_papers
                or_arxiv = fetch_venue_papers(ctx, retrieval_config_path=retrieval_config_path)

    # 4) merge + dedupe + provenance + cap
    papers, rels = merge_personalized_corpus(seed_arxiv, or_arxiv, final_k=final_k)

    # 5) write corpus provenance + selected papers (dicts) + 6) merged manifest (real PDF paths)
    cdir = ctx.path("corpus"); ensure_dir(cdir)
    with open(cdir / "paper_relationships.jsonl", "w") as f:
        for r in rels:
            f.write(_json.dumps(r) + "\n")
    rel_by_id = {r["paper_id"]: r for r in rels}
    with open(cdir / "selected_papers.jsonl", "w") as f, open(cdir / "selected_seed_papers.jsonl", "w") as f2:
        for p in papers:
            d = model_dump(p); r = rel_by_id.get(p.arxiv_id, {})
            d["relation_to_seed_profile"] = r.get("relation_to_seed_profile", "")
            d["provenance"] = r.get("provenance", [])
            d["is_manual_seed_paper"] = r.get("is_manual_seed_paper", False)
            line = _json.dumps(d) + "\n"; f.write(line); f2.write(line)
    write_manifest(ctx.run_dir, papers)

    n_seed = sum(1 for r in rels if r["is_manual_seed_paper"])
    n_parseable = sum(1 for p in papers if p.local_pdf_path)
    print(f"[personalized] seeds={len(seed_arxiv)} openreview={len(or_arxiv)} merged={len(papers)} "
          f"(seed_in_corpus={n_seed}) parseable_pdfs={n_parseable} final_k={final_k}", flush=True)
    return papers


def _fetch_multi_source(ctx: Any, *, query: str, max_results: int, cfg: dict,
                         retrieval_config_path: str | None = None) -> list[ArxivPaper]:
    """Run the multi-source retrieval pipeline and convert results to ArxivPaper."""
    import sys
    from pathlib import Path as _Path

    ctx.stage_start("fetch_arxiv")

    project_root = str(_Path(__file__).parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from retrieval.candidate_collector import collect_candidates, collect_candidates_with_config
    from retrieval.dedup import deduplicate
    from retrieval.embedding_reranker import rerank
    from retrieval.mmr import mmr_select
    from retrieval.query_expander import attach_profile_expansions, expand_from_intent, expand_query
    from retrieval.query_intent import build_intent
    from retrieval.relevance_filter import score_and_filter_with_intent
    from retrieval.config import QueryConfig, RetrievalConfig

    use_embeddings = bool(cfg.get("use_embeddings", False))
    model_cache = cfg.get("model_cache_dir") or ctx.config.get("model_cache_root")
    llm_base_url = ctx.config.get("llm", {}).get("base_url") or cfg.get("llm_base_url")

    def _log(msg: str) -> None:
        print(msg, flush=True)

    # Load retrieval config from file if provided — gives full profile (phrases, expansions, venues)
    if retrieval_config_path and _Path(retrieval_config_path).exists():
        ret_cfg = RetrievalConfig.from_yaml(retrieval_config_path)
        # query from CLI/sgha config takes priority if explicitly passed, else use config file's query
        if query:
            ret_cfg.query.text = query
        else:
            query = ret_cfg.query.text
        intent = build_intent(ret_cfg)
        intent = attach_profile_expansions(intent, ret_cfg)
        expanded = expand_from_intent(intent, max_queries=int(cfg.get("max_expanded_queries", 10)))
        _log(f"[retrieval] using profile: {intent.profile_name or 'none'}")
        raw, backend_status = collect_candidates_with_config(expanded, ret_cfg, intent, logger=_log)
    else:
        # No retrieval config — build a generic intent from the query text
        intent_cfg = RetrievalConfig(query=QueryConfig(text=query, intent="balanced"))
        intent = build_intent(intent_cfg)
        expanded = expand_query(query, max_queries=int(cfg.get("max_expanded_queries", 10)))
        sources = cfg.get("sources", ["arxiv", "semantic_scholar", "openalex"])
        _log(f"[retrieval] {len(expanded)} queries × {sources}")
        raw, backend_status = collect_candidates(
            expanded,
            sources=sources,
            max_results_per_query=int(cfg.get("max_results_per_query", 50)),
            max_raw_candidates=int(cfg.get("max_raw_candidates", 500)),
            use_paper_search_mcp=bool(cfg.get("use_paper_search_mcp", False)),
            logger=_log,
        )

    final_k = int(cfg.get("final_k", max_results))
    write_json(ctx.path("arxiv", "backend_status.json"), backend_status)
    _log(f"[retrieval] {len(raw)} raw → dedup...")

    deduped = deduplicate(raw)
    # Use threshold=0 so all candidates pass metadata scoring; LLM judge below does the real filtering
    kept, rejected = score_and_filter_with_intent(deduped, intent, keep_threshold=0.0)
    _log(f"[retrieval] {len(deduped)} deduped → {len(kept)} after metadata pass")

    write_json(ctx.path("arxiv", "rejected_papers.json"), [
        {"title": r.candidate.title, "score": r.metadata_score, "reason": r.rejection_reason}
        for r in rejected
    ])

    # LLM relevance filter: ask the model to judge each paper against the query
    if llm_base_url and kept:
        _log(f"[retrieval] LLM relevance filtering {len(kept)} candidates...")
        kept = _llm_relevance_filter(query, kept, llm_base_url=llm_base_url,
                                     model=ctx.config.get("llm", {}).get("model", "Qwen/Qwen3.5-9B"),
                                     logger=_log)
        _log(f"[retrieval] {len(kept)} kept after LLM filter")
        write_json(ctx.path("arxiv", "llm_relevance_filter.json"),
                   [{"title": sc.candidate.title, "score": sc.metadata_score,
                     "llm_relevant": True} for sc in kept])

    if use_embeddings and kept:
        kept = rerank(query, kept, model_cache_dir=model_cache, logger=_log)
        if len(kept) > final_k:
            kept = mmr_select(kept, k=final_k, model_cache_dir=model_cache, logger=_log)

    selected_candidates = [sc.candidate for sc in kept[:final_k]]
    _log(f"[retrieval] {len(selected_candidates)} papers selected — downloading PDFs...")

    papers = _candidates_to_arxiv_papers(ctx, selected_candidates, query=query)
    write_manifest(ctx.run_dir, papers)
    write_json(ctx.path("arxiv", "query.json"), {"query": query, "expanded_queries": expanded, "max_results": max_results})
    ctx.stage_end("fetch_arxiv", papers=len(papers))
    return papers


def _llm_relevance_filter(
    query: str,
    scored: list,
    *,
    llm_base_url: str,
    model: str = "Qwen/Qwen3.5-9B",
    batch_size: int = 8,
    logger=None,
) -> list:
    """Ask the LLM to judge each paper's relevance to the query. Returns only relevant papers."""
    import json as _json
    _log = logger or (lambda m: None)

    try:
        from openai import OpenAI
        client = OpenAI(base_url=llm_base_url, api_key="EMPTY", timeout=60)
    except Exception as exc:
        _log(f"[retrieval] LLM filter unavailable ({exc}), skipping")
        return scored

    kept = []
    for i in range(0, len(scored), batch_size):
        batch = scored[i: i + batch_size]
        papers_text = "\n\n".join(
            f"[{j+1}] Title: {sc.candidate.title}\nAbstract: {sc.candidate.abstract[:400]}"
            for j, sc in enumerate(batch)
        )
        prompt = (
            f"You are a research paper relevance judge.\n"
            f"Research topic: \"{query}\"\n\n"
            f"For each paper below, decide if it is directly relevant to the topic above. "
            f"A paper is relevant if its main contribution studies, analyzes, or substantially advances the topic. "
            f"Papers that merely cite the topic as background are NOT relevant.\n\n"
            f"{papers_text}\n\n"
            f"Return a JSON array of the 1-based indices of the RELEVANT papers only. "
            f"Example: [1, 3, 5]. Return [] if none are relevant. No explanation."
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You return strict JSON only. No markdown fences."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=128,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            content = (resp.choices[0].message.content or "[]").strip()
            # Strip markdown fences if present
            if content.startswith("```"):
                content = content.split("```")[1].lstrip("json").strip()
            indices = _json.loads(content)
            if not isinstance(indices, list):
                indices = []
            for idx in indices:
                if isinstance(idx, int) and 1 <= idx <= len(batch):
                    kept.append(batch[idx - 1])
        except Exception as exc:
            _log(f"[retrieval] LLM filter batch {i//batch_size+1} failed ({exc}), keeping all in batch")
            kept.extend(batch)

    return kept


def _candidates_to_arxiv_papers(ctx: Any, candidates: list, *, query: str) -> list[ArxivPaper]:
    """Convert PaperCandidate list to ArxivPaper list with PDF download."""
    dataset_arxiv_dir = ctx.dataset_path("arxiv")
    pdf_root = ensure_dir(dataset_arxiv_dir / "downloaded_pdfs")
    ensure_dir(ctx.path("arxiv", "downloaded_pdfs"))
    timeout = int(ctx.config.get("request_timeout_seconds", 60))

    papers: list[ArxivPaper] = []
    for candidate in candidates:
        # Build a stable file-safe ID
        if candidate.arxiv_id:
            file_id = candidate.arxiv_id.replace("/", "_")
            paper_id = candidate.arxiv_id
        else:
            raw_id = candidate.paper_id.replace("doi:", "").replace("s2:", "").replace("openalex:", "")
            file_id = slugify(raw_id[:40])
            paper_id = candidate.paper_id

        safe_name = slugify(file_id)
        local_pdf = pdf_root / f"{safe_name}.pdf"

        # Pick best PDF url: openAccessPdf (S2) > arxiv > OA url
        pdf_url = candidate.pdf_url or ""
        if candidate.arxiv_id and not pdf_url:
            bare = candidate.arxiv_id.split("v")[0] if "v" in candidate.arxiv_id else candidate.arxiv_id
            pdf_url = f"https://arxiv.org/pdf/{bare}"

        paper = ArxivPaper(
            arxiv_id=paper_id,
            title=candidate.title,
            authors=candidate.authors,
            abstract=candidate.abstract,
            categories=candidate.categories or candidate.fields_of_study,
            published=candidate.published_date,
            updated=candidate.updated_date,
            pdf_url=pdf_url,
            local_pdf_path=str(local_pdf),
            download_status="not_downloaded",
            source_query=query,
        )
        try:
            if local_pdf.exists():
                from .utils import sha256_file
                paper.sha256 = sha256_file(local_pdf)
                paper.download_status = "exists"
            elif pdf_url:
                _, digest = download_pdf(pdf_url, local_pdf, timeout=timeout)
                paper.sha256 = digest
                paper.download_status = "downloaded"
            else:
                paper.download_status = "no_pdf_url"
            if local_pdf.exists():
                safe_symlink_or_copy(local_pdf, ctx.path("arxiv", "downloaded_pdfs", local_pdf.name))
            log_download(
                ctx.path("arxiv", "download_log.jsonl"),
                {"arxiv_id": paper_id, "status": paper.download_status, "path": str(local_pdf)},
            )
        except Exception as exc:
            paper.download_status = f"failed: {exc}"
            log_download(
                ctx.path("arxiv", "download_log.jsonl"),
                {"arxiv_id": paper_id, "status": "failed", "error": str(exc), "url": pdf_url},
            )
            ctx.audit.failure("fetch_arxiv.download", exc, arxiv_id=paper_id)
        papers.append(paper)
    return papers


def _fetch_multi_query(ctx: Any, *, queries: list[str], max_per_query: int, output_dir: str | Path | None = None) -> list[ArxivPaper]:
    ctx.stage_start("fetch_arxiv")
    seen_ids: set[str] = set()
    all_papers: list[ArxivPaper] = []
    for q in queries:
        batch = _fetch_single_query(ctx, query=q, max_results=max_per_query, output_dir=output_dir, seen_ids=seen_ids)
        for p in batch:
            seen_ids.add(p.arxiv_id)
            all_papers.append(p)
    # Rewrite manifest with the full merged set
    from .corpus_manifest import write_manifest
    write_manifest(ctx.run_dir, all_papers)
    ctx.stage_end("fetch_arxiv", papers=len(all_papers))
    return all_papers


def _fetch_single_query(ctx: Any, *, query: str, max_results: int, output_dir: str | Path | None = None, seen_ids: set[str] | None = None) -> list[ArxivPaper]:
    is_multi = seen_ids is not None
    if not is_multi:
        ctx.stage_start("fetch_arxiv")
    try:
        import arxiv
    except ImportError as exc:  # pragma: no cover - dependency installed by setup
        raise RuntimeError("Install the arxiv package to fetch papers") from exc

    dataset_arxiv_dir = Path(output_dir) if output_dir else ctx.dataset_path("arxiv")
    pdf_root = ensure_dir(dataset_arxiv_dir / "downloaded_pdfs")
    ensure_dir(ctx.path("arxiv", "downloaded_pdfs"))
    write_json(ctx.path("arxiv", "query.json"), {"query": query, "max_results": max_results})

    allowed_categories: list[str] = ctx.config.get("allowed_categories", [])
    anchor_terms: list[str] = ctx.config.get("anchor_terms", [])
    min_year: int = int(ctx.config.get("min_year", 0))
    if seen_ids is None:
        seen_ids = set()

    # Fetch extra to compensate for papers filtered out by category + year + anchor
    has_filters = bool(allowed_categories or min_year or anchor_terms)
    fetch_limit = min(max_results * 5, 500) if has_filters else max_results

    client = arxiv.Client(page_size=50, delay_seconds=float(ctx.config.get("polite_delay_seconds", 5.0)), num_retries=3)
    search = arxiv.Search(query=query, max_results=fetch_limit, sort_by=arxiv.SortCriterion.Relevance)
    papers: list[ArxivPaper] = []
    for result in client.results(search):
        if len(papers) >= max_results:
            break

        # Skip duplicates across queries
        if result.get_short_id() in seen_ids:
            continue

        # Stage 1: year filter — skip papers older than min_year
        if min_year and result.published and result.published.year < min_year:
            continue

        # Stage 2: category filter — all categories must be in allowed list
        if allowed_categories and not all(cat in allowed_categories for cat in result.categories):
            continue

        # Stage 3: anchor-term filter — at least one term must appear in title or abstract
        if anchor_terms:
            text = (result.title + " " + result.summary).lower()
            if not any(term.lower() in text for term in anchor_terms):
                continue

        arxiv_id = result.get_short_id()
        safe_name = slugify(arxiv_id.replace("/", "_"))
        local_pdf = pdf_root / f"{safe_name}.pdf"
        paper = ArxivPaper(
            arxiv_id=arxiv_id,
            title=result.title,
            authors=[a.name for a in result.authors],
            abstract=result.summary,
            categories=list(result.categories),
            published=result.published.isoformat() if result.published else "",
            updated=result.updated.isoformat() if result.updated else "",
            pdf_url=result.pdf_url,
            local_pdf_path=str(local_pdf),
            download_status="not_downloaded",
            source_query=query,
        )
        try:
            if local_pdf.exists():
                from .utils import sha256_file

                paper.sha256 = sha256_file(local_pdf)
                paper.download_status = "exists"
            else:
                _, digest = download_pdf(result.pdf_url, local_pdf, timeout=int(ctx.config.get("request_timeout_seconds", 60)))
                paper.sha256 = digest
                paper.download_status = "downloaded"
            safe_symlink_or_copy(local_pdf, ctx.path("arxiv", "downloaded_pdfs", local_pdf.name))
            log_download(ctx.path("arxiv", "download_log.jsonl"), {"arxiv_id": arxiv_id, "status": paper.download_status, "path": str(local_pdf), "sha256": paper.sha256})
        except Exception as exc:
            paper.download_status = f"failed: {exc}"
            log_download(ctx.path("arxiv", "download_log.jsonl"), {"arxiv_id": arxiv_id, "status": "failed", "error": str(exc), "url": result.pdf_url})
            ctx.audit.failure("fetch_arxiv.download", exc, arxiv_id=arxiv_id)
        papers.append(paper)
        time.sleep(float(ctx.config.get("polite_delay_seconds", 3.0)))

    if not is_multi:
        write_manifest(ctx.run_dir, papers)
        ctx.stage_end("fetch_arxiv", papers=len(papers))
    return papers
