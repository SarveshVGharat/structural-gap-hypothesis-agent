"""Multi-source candidate collection.

When a RetrievalConfig + RetrievalIntent are provided, OpenReview is
initialised with the profile's phrase filter.  The legacy signature
(list of queries + keyword args) is preserved for backwards compatibility.
"""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from .backends.arxiv_backend import ArxivBackend
from .backends.base import BaseBackend, PaperCandidate
from .backends.openalex_backend import OpenAlexBackend
from .backends.openreview_backend import OpenReviewBackend
from .backends.paper_search_mcp_backend import PaperSearchMCPBackend
from .backends.semantic_scholar_backend import SemanticScholarBackend

if TYPE_CHECKING:
    from .config import RetrievalConfig
    from .query_intent import RetrievalIntent
    from .venue_registry import VenueSpec

Logger = Callable[[str], None]


def collect_candidates_with_config(
    queries: list[str],
    config: "RetrievalConfig",
    intent: "RetrievalIntent",
    *,
    logger: Logger | None = None,
) -> tuple[list[PaperCandidate], dict[str, Any]]:
    """Config-driven collection — uses intent phrases for OpenReview filtering."""
    from .venue_registry import get_venue_specs

    _log = logger or (lambda m: None)
    src_cfg = config.sources
    venue_cfg = config.venues
    sources = list(src_cfg.enabled)

    # Build backend stack
    mcp = PaperSearchMCPBackend(sources=sources)
    arxiv = ArxivBackend()
    ss = SemanticScholarBackend()
    oa = OpenAlexBackend()

    # OpenReview gets the profile's phrase filter (empty = no filter = collect everything)
    venue_specs = get_venue_specs(venue_cfg)
    or_venues = [(s.invitation, s.venueid, s.name) for s in venue_specs if s.has_openreview]
    or_ = OpenReviewBackend(
        venues=or_venues or None,
        filter_phrases=intent.must_have_phrases + intent.should_have_phrases,
        min_abstract_hits=intent.openreview_min_abstract_hits,
    )

    backend_status: dict[str, Any] = {
        "paper_search_mcp_available": mcp.available,
        "sources_requested": sources,
        "backends_used": [],
        "venue_mode": venue_cfg.mode,
    }

    if src_cfg.use_paper_search_mcp and mcp.available:
        active_backends: list[BaseBackend] = [mcp]
        backend_status["backends_used"] = ["paper_search_mcp"]
        _log("  Backend: paper-search-mcp (multi-source)")
    else:
        if src_cfg.use_paper_search_mcp:
            _log("  paper-search-mcp not available — using direct API backends")
        active_backends = []
        if "arxiv" in sources:
            active_backends.append(arxiv)
        if "semantic_scholar" in sources:
            active_backends.append(ss)
        if "openalex" in sources:
            active_backends.append(oa)
        if "openreview" in sources and venue_cfg.include_openreview and or_.available:
            active_backends.append(or_)
        backend_status["backends_used"] = [b.name for b in active_backends]
        _log(f"  Backends: {', '.join(b.name for b in active_backends)}")

    return _run_collection(
        queries=queries,
        active_backends=active_backends,
        max_results_per_query=src_cfg.max_results_per_query,
        max_raw_candidates=src_cfg.max_raw_candidates,
        backend_status=backend_status,
        logger=_log,
    )


def collect_candidates(
    queries: list[str],
    *,
    sources: list[str] | None = None,
    max_results_per_query: int = 50,
    max_raw_candidates: int = 500,
    use_paper_search_mcp: bool = True,
    logger: Logger | None = None,
) -> tuple[list[PaperCandidate], dict[str, Any]]:
    """Backwards-compatible collection (no config/intent required)."""
    sources = sources or ["arxiv", "semantic_scholar", "openalex"]
    _log = logger or (lambda m: None)

    mcp = PaperSearchMCPBackend(sources=sources)
    arxiv = ArxivBackend()
    ss = SemanticScholarBackend()
    oa = OpenAlexBackend()
    or_ = OpenReviewBackend()  # no filter phrases → collect all

    backend_status: dict[str, Any] = {
        "paper_search_mcp_available": mcp.available,
        "sources_requested": sources,
        "backends_used": [],
    }

    if use_paper_search_mcp and mcp.available:
        active_backends: list[BaseBackend] = [mcp]
        backend_status["backends_used"] = ["paper_search_mcp"]
        _log("  Backend: paper-search-mcp (multi-source)")
    else:
        if use_paper_search_mcp:
            _log("  paper-search-mcp not available — using direct API backends")
        active_backends = []
        if "arxiv" in sources:
            active_backends.append(arxiv)
        if "semantic_scholar" in sources:
            active_backends.append(ss)
        if "openalex" in sources:
            active_backends.append(oa)
        if "openreview" in sources and or_.available:
            active_backends.append(or_)
        backend_status["backends_used"] = [b.name for b in active_backends]
        _log(f"  Backends: {', '.join(b.name for b in active_backends)}")

    return _run_collection(
        queries=queries,
        active_backends=active_backends,
        max_results_per_query=max_results_per_query,
        max_raw_candidates=max_raw_candidates,
        backend_status=backend_status,
        logger=_log,
    )


def _run_collection(
    *,
    queries: list[str],
    active_backends: list[BaseBackend],
    max_results_per_query: int,
    max_raw_candidates: int,
    backend_status: dict[str, Any],
    logger: Logger,
) -> tuple[list[PaperCandidate], dict[str, Any]]:
    all_candidates: list[PaperCandidate] = []
    per_source_counts: dict[str, int] = {}

    for i, query in enumerate(queries):
        if len(all_candidates) >= max_raw_candidates:
            logger(f"  Reached max_raw_candidates={max_raw_candidates}, stopping")
            break
        logger(f"  Query {i+1}/{len(queries)}: {query[:80]}")
        for backend in active_backends:
            try:
                results = backend.search(query, max_results=max_results_per_query)
                logger(f"    {backend.name}: {len(results)} results")
                per_source_counts[backend.name] = per_source_counts.get(backend.name, 0) + len(results)
                all_candidates.extend(results)
            except Exception as exc:
                logger(f"    {backend.name}: ERROR — {exc}")

    backend_status["per_source_counts"] = per_source_counts
    backend_status["total_raw"] = len(all_candidates)
    logger(f"  Total raw candidates: {len(all_candidates)}")
    return all_candidates, backend_status
