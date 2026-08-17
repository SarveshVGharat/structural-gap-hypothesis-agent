"""Embedding-based reranking using sentence-transformers."""
from __future__ import annotations

import math
from typing import Any

from .relevance_filter import ScoredCandidate

_PREFERRED_MODEL = "BAAI/bge-small-en-v1.5"
_FALLBACK_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Module-level cache so rerank() and mmr_select() share the same loaded model
_MODEL_CACHE: dict[str, Any] = {}


def get_model(model_name: str, cache_dir: str | None = None) -> Any:
    key = f"{model_name}:{cache_dir}"
    if key not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer
        kwargs: dict[str, Any] = {}
        if cache_dir:
            kwargs["cache_folder"] = cache_dir
        try:
            _MODEL_CACHE[key] = SentenceTransformer(model_name, **kwargs)
        except Exception:
            _MODEL_CACHE[key] = SentenceTransformer(_FALLBACK_MODEL, **kwargs)
    return _MODEL_CACHE[key]


def rerank(
    query: str,
    scored: list[ScoredCandidate],
    *,
    model_name: str | None = None,
    model_cache_dir: str | None = None,
    weight_metadata: float = 1.0,
    embedding_weight: float = 12.0,
    logger: Any = None,
) -> list[ScoredCandidate]:
    """Add combined_score to each ScoredCandidate. Returns sorted by combined_score."""
    if not scored:
        return scored
    _log = logger or (lambda m: None)

    try:
        import numpy as np

        name = model_name or _PREFERRED_MODEL
        model = get_model(name, model_cache_dir)

        texts = [f"{s.candidate.title}\n{s.candidate.abstract[:512]}" for s in scored]
        _log(f"  Encoding {len(texts)} papers with sentence-transformers...")
        embeddings = model.encode([query] + texts, normalize_embeddings=True, show_progress_bar=False)
        query_emb = embeddings[0]
        paper_embs = embeddings[1:]

        for i, sc in enumerate(scored):
            emb_sim = float(np.dot(query_emb, paper_embs[i]))
            source_bonus = 1.0 if len(sc.candidate.source_names) > 1 else 0.0
            cit = sc.candidate.citation_count or 0
            citation_bonus = min(math.log10(cit + 1), 3.0) if cit > 0 else 0.0
            combined = (
                weight_metadata * sc.metadata_score
                + embedding_weight * emb_sim
                + source_bonus
                + citation_bonus
            )
            sc.score_breakdown["embedding_similarity"] = round(emb_sim, 6)
            sc.score_breakdown["source_bonus"] = source_bonus
            sc.score_breakdown["citation_bonus"] = round(citation_bonus, 4)
            sc.score_breakdown["combined_score"] = round(combined, 4)

        scored.sort(key=lambda s: s.score_breakdown.get("combined_score", s.metadata_score), reverse=True)
        _log(f"  Embedding reranking done.")

    except ImportError:
        _log("  Warning: sentence-transformers not available, skipping embedding reranking")
    except Exception as exc:
        _log(f"  Warning: embedding reranking failed ({exc}), using metadata score only")

    return scored


def rerank_cross_encoder(
    query: str,
    scored: list[ScoredCandidate],
    *,
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    top_k: int = 100,
    logger: Any = None,
) -> list[ScoredCandidate]:
    """Optional cross-encoder reranking on top_k candidates only."""
    _log = logger or (lambda m: None)
    if not scored:
        return scored
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(model_name)
        top = scored[:top_k]
        pairs = [(query, f"{s.candidate.title}\n{s.candidate.abstract[:512]}") for s in top]
        _log(f"  Cross-encoder scoring {len(pairs)} pairs...")
        ce_scores = model.predict(pairs)
        for sc, ce_score in zip(top, ce_scores):
            sc.score_breakdown["cross_encoder_score"] = round(float(ce_score), 6)
            base = sc.score_breakdown.get("combined_score", sc.metadata_score)
            sc.score_breakdown["combined_score"] = round(base + float(ce_score) * 2.0, 4)
        top.sort(key=lambda s: s.score_breakdown.get("combined_score", 0), reverse=True)
        return top + scored[top_k:]
    except Exception as exc:
        _log(f"  Warning: cross-encoder failed ({exc}), skipping")
        return scored
