"""Venue-filtered retrieval: NeurIPS/ICML/ICLR (2020+) via OpenReview search + LLM selection."""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .corpus_manifest import write_manifest
from .extraction_schemas import ArxivPaper
from .pdf_downloader import download_pdf, log_download
from .utils import ensure_dir, safe_symlink_or_copy, slugify, write_json

_OR_BASE = "https://api2.openreview.net"
_POLITE_DELAY = 1.0  # seconds between OpenReview requests

# All venues covered, newest first so we get recent papers first.
# Each entry: (invitation, display_name, year)
_VENUE_INVITATIONS: list[tuple[str, str, int]] = [
    ("ICLR.cc/2025/Conference/-/Submission",    "ICLR 2025",    2025),
    ("NeurIPS.cc/2024/Conference/-/Submission", "NeurIPS 2024", 2024),
    ("ICML.cc/2024/Conference/-/Submission",    "ICML 2024",    2024),
    ("ICLR.cc/2024/Conference/-/Submission",    "ICLR 2024",    2024),
    ("NeurIPS.cc/2023/Conference/-/Submission", "NeurIPS 2023", 2023),
    ("ICML.cc/2023/Conference/-/Submission",    "ICML 2023",    2023),
    ("ICLR.cc/2023/Conference/-/Submission",    "ICLR 2023",    2023),
    ("NeurIPS.cc/2022/Conference/-/Submission", "NeurIPS 2022", 2022),
    ("ICML.cc/2022/Conference/-/Submission",    "ICML 2022",    2022),
    ("ICLR.cc/2022/Conference/-/Submission",    "ICLR 2022",    2022),
    ("NeurIPS.cc/2021/Conference/-/Submission", "NeurIPS 2021", 2021),
    ("ICLR.cc/2021/Conference/-/Submission",    "ICLR 2021",    2021),
    ("ICLR.cc/2020/Conference/-/Submission",    "ICLR 2020",    2020),
]


def _get_field(content: dict, key: str) -> str:
    v = content.get(key, "")
    return v.get("value", v) if isinstance(v, dict) else str(v or "")


def _search_openreview(
    queries: list[str],
    *,
    min_year: int,
    max_per_search: int,
    logger=None,
) -> list[dict]:
    """
    For every query × every venue (year >= min_year), call the OpenReview
    search endpoint and collect matching papers (title + abstract).
    Returns a deduplicated list of raw note dicts.
    """
    _log = logger or (lambda m: None)
    seen_ids: set[str] = set()
    candidates: list[dict] = []

    venues = [(inv, name, yr) for inv, name, yr in _VENUE_INVITATIONS if yr >= min_year]
    _log(
        f"[venue_retrieval] Searching {len(venues)} venue-years × "
        f"{len(queries)} queries via OpenReview"
    )

    for inv, venue_name, year in venues:
        venue_hits = 0
        for query in queries:
            params = urllib.parse.urlencode({
                "term": query,
                "invitation": inv,
                "limit": max_per_search,
            })
            url = f"{_OR_BASE}/notes/search?{params}"
            data = None
            for attempt in range(3):
                try:
                    resp = urllib.request.urlopen(url, timeout=20)
                    data = json.loads(resp.read())
                    break
                except Exception as exc:
                    is_429 = hasattr(exc, "code") and exc.code == 429
                    if is_429 and attempt < 2:
                        wait = 2.0 ** (attempt + 1)
                        _log(f"[venue_retrieval]   429 rate limit, retrying in {wait:.0f}s...")
                        time.sleep(wait)
                    else:
                        _log(f"[venue_retrieval]   {venue_name} / {query[:40]!r} failed: {exc}")
                        time.sleep(_POLITE_DELAY)
                        break
            if data is None:
                continue

            for note in data.get("notes", []):
                nid = note.get("id", "")
                if not nid or nid in seen_ids:
                    continue
                content = note.get("content", {})
                title = _get_field(content, "title").strip()
                abstract = _get_field(content, "abstract").strip()
                if not title:
                    continue
                seen_ids.add(nid)
                candidates.append({
                    "note_id": nid,
                    "title": title,
                    "abstract": abstract,
                    "venue": venue_name,
                    "year": year,
                    "authors": content.get("authors", {}).get("value", [])
                               if isinstance(content.get("authors"), dict)
                               else content.get("authors", []),
                    "pdf_url": f"https://openreview.net/pdf?id={nid}",
                    "forum_url": f"https://openreview.net/forum?id={nid}",
                    "keywords": content.get("keywords", {}).get("value", [])
                                if isinstance(content.get("keywords"), dict)
                                else content.get("keywords", []),
                })
                venue_hits += 1

            time.sleep(_POLITE_DELAY)

        if venue_hits:
            _log(f"[venue_retrieval]   {venue_name}: {venue_hits} new papers")

    _log(f"[venue_retrieval] {len(candidates)} unique papers collected")
    return candidates


def _llm_select_papers(
    topic_description: str,
    candidates: list[dict],
    *,
    llm_base_url: str,
    model: str,
    batch_size: int,
    logger=None,
) -> list[dict]:
    _log = logger or (lambda m: None)

    try:
        from openai import OpenAI
        client = OpenAI(base_url=llm_base_url, api_key="EMPTY", timeout=90)
    except Exception as exc:
        _log(f"[venue_retrieval] LLM unavailable ({exc}), returning all candidates")
        return candidates

    selected: list[dict] = []
    total_batches = (len(candidates) + batch_size - 1) // batch_size

    for batch_idx in range(0, len(candidates), batch_size):
        batch = candidates[batch_idx : batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1

        papers_block = ""
        for j, p in enumerate(batch, 1):
            abstract = p.get("abstract", "")[:500]
            papers_block += (
                f"[{j}] Title: {p['title']}\n"
                f"    Venue: {p.get('venue', '')} {p.get('year', '')}\n"
                f"    Abstract: {abstract}\n\n"
            )

        prompt = (
            f"You are a research paper relevance judge.\n\n"
            f"Research topic:\n{topic_description.strip()}\n\n"
            f"Papers:\n{papers_block}"
            f"Select ONLY papers whose main contribution directly studies or substantially "
            f"advances the research topic. Papers that only mention the topic as background "
            f"are NOT relevant.\n\n"
            f"Return a JSON array of the 1-based indices of relevant papers. "
            f"Example: [1, 3, 5]. Return [] if none qualify. "
            f"Return ONLY the JSON array, no explanation."
        )

        _log(
            f"[venue_retrieval] LLM batch {batch_num}/{total_batches} "
            f"({len(batch)} papers)..."
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You return strict JSON only. No markdown, no explanation.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=256,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            content = (resp.choices[0].message.content or "[]").strip()
            if content.startswith("```"):
                content = content.split("```")[1].lstrip("json").strip()
            indices = json.loads(content)
            if not isinstance(indices, list):
                indices = []
            n_sel = 0
            for idx in indices:
                if isinstance(idx, int) and 1 <= idx <= len(batch):
                    selected.append(batch[idx - 1])
                    n_sel += 1
            _log(f"[venue_retrieval]   → {n_sel} selected from batch {batch_num}")
        except Exception as exc:
            _log(f"[venue_retrieval] LLM batch {batch_num} failed ({exc}), keeping all")
            selected.extend(batch)

    return selected


def _raw_to_arxiv_papers(ctx: Any, raw_papers: list[dict]) -> list[ArxivPaper]:
    from .utils import sha256_file

    dataset_arxiv_dir = ctx.dataset_path("arxiv")
    pdf_root = ensure_dir(dataset_arxiv_dir / "downloaded_pdfs")
    ensure_dir(ctx.path("arxiv", "downloaded_pdfs"))
    timeout = int(ctx.config.get("request_timeout_seconds", 60))
    papers: list[ArxivPaper] = []

    for item in raw_papers:
        note_id = item.get("note_id", "")
        paper_id = f"openreview:{note_id}"
        file_id = slugify(note_id[:50])
        local_pdf = pdf_root / f"{file_id}.pdf"
        pdf_url = item.get("pdf_url", "")

        authors = item.get("authors", [])
        if isinstance(authors, dict):
            authors = authors.get("value", [])

        paper = ArxivPaper(
            arxiv_id=paper_id,
            title=item.get("title", ""),
            authors=authors if isinstance(authors, list) else [],
            abstract=item.get("abstract", ""),
            categories=item.get("keywords", [])[:5],
            published=str(item.get("year", "")),
            updated=str(item.get("year", "")),
            pdf_url=pdf_url,
            local_pdf_path=str(local_pdf),
            download_status="not_downloaded",
            source_query=item.get("venue", ""),
        )

        try:
            if local_pdf.exists():
                paper.sha256 = sha256_file(local_pdf)
                paper.download_status = "exists"
            elif pdf_url:
                _, digest = download_pdf(pdf_url, local_pdf, timeout=timeout)
                paper.sha256 = digest
                paper.download_status = "downloaded"
            else:
                paper.download_status = "no_pdf_url"
            if local_pdf.exists():
                safe_symlink_or_copy(
                    local_pdf, ctx.path("arxiv", "downloaded_pdfs", local_pdf.name)
                )
        except Exception as exc:
            paper.download_status = f"failed: {exc}"
            ctx.audit.failure("fetch_arxiv.download", exc, arxiv_id=paper_id)

        log_download(
            ctx.path("arxiv", "download_log.jsonl"),
            {"arxiv_id": paper_id, "status": paper.download_status, "pdf_url": pdf_url},
        )
        papers.append(paper)

    return papers


def fetch_venue_papers(ctx: Any, *, retrieval_config_path: str | None = None) -> list[ArxivPaper]:
    """
    Venue-filtered retrieval pipeline:
      1. Keyword-search OpenReview for NeurIPS/ICML/ICLR papers (year >= min_year)
      2. LLM batch-selects relevant papers based on title + abstract
      3. Download PDFs for selected papers
      4. Write manifest and return ArxivPaper list
    """
    ctx.stage_start("fetch_arxiv")

    venue_cfg: dict = {}
    if retrieval_config_path and Path(retrieval_config_path).exists():
        import yaml as _yaml
        with open(retrieval_config_path, "r") as _f:
            raw_cfg = _yaml.safe_load(_f) or {}
        venue_cfg = raw_cfg.get("venue_retrieval", {})

    llm_cfg = ctx.config.get("llm", {})
    min_year: int = int(venue_cfg.get("min_year", 2020))
    max_candidates: int = int(venue_cfg.get("max_candidates", 300))
    # Support both key names; configs use max_per_query
    max_per_search: int = int(venue_cfg.get("max_per_query", venue_cfg.get("max_per_search", 50)))
    final_k: int = int(venue_cfg.get("final_k", 30))
    batch_size: int = int(venue_cfg.get("llm_batch_size", 15))
    topic_description: str = venue_cfg.get("topic_description", ctx.config.get("query", ""))
    queries: list[str] = venue_cfg.get("queries", [ctx.config.get("query", "")])
    llm_base_url: str = llm_cfg.get("base_url", "")
    model: str = llm_cfg.get("model", "Qwen/Qwen3.5-9B")

    def _log(msg: str) -> None:
        print(msg, flush=True)

    _log(
        f"[venue_retrieval] Venues: NeurIPS / ICML / ICLR | "
        f"Year >= {min_year} | {len(queries)} queries"
    )

    # Step 1: OpenReview keyword search
    candidates = _search_openreview(
        queries,
        min_year=min_year,
        max_per_search=max_per_search,
        logger=_log,
    )

    if len(candidates) > max_candidates:
        candidates = candidates[:max_candidates]
        _log(f"[venue_retrieval] Capped to {max_candidates} candidates")

    write_json(
        ctx.path("arxiv", "backend_status.json"),
        {
            "mode": "venue",
            "source": "openreview",
            "venues": ["NeurIPS", "ICML", "ICLR"],
            "min_year": min_year,
            "queries": queries,
            "candidates_before_llm": len(candidates),
        },
    )

    # Step 2: LLM selection
    if llm_base_url and candidates:
        selected_raw = _llm_select_papers(
            topic_description,
            candidates,
            llm_base_url=llm_base_url,
            model=model,
            batch_size=batch_size,
            logger=_log,
        )
        _log(f"[venue_retrieval] LLM selected {len(selected_raw)} / {len(candidates)} papers")
    else:
        _log("[venue_retrieval] No LLM URL — skipping LLM selection, using all candidates")
        selected_raw = candidates

    if len(selected_raw) > final_k:
        selected_raw = selected_raw[:final_k]
        _log(f"[venue_retrieval] Trimmed to final_k={final_k}")

    write_json(
        ctx.path("arxiv", "selected_before_download.json"),
        [
            {
                "title": p.get("title", ""),
                "venue": p.get("venue", ""),
                "year": p.get("year"),
            }
            for p in selected_raw
        ],
    )

    # Step 3: PDF download
    _log(f"[venue_retrieval] Downloading PDFs for {len(selected_raw)} papers...")
    papers = _raw_to_arxiv_papers(ctx, selected_raw)

    write_manifest(ctx.run_dir, papers)
    write_json(
        ctx.path("arxiv", "query.json"),
        {
            "mode": "venue",
            "source": "openreview",
            "queries": queries,
            "topic_description": topic_description,
            "min_year": min_year,
            "final_k": final_k,
        },
    )

    ctx.stage_end("fetch_arxiv", papers=len(papers))
    return papers
