"""Maximal Marginal Relevance selection for diversity-aware final selection."""
from __future__ import annotations

from typing import Any

from .embedding_reranker import get_model
from .relevance_filter import ScoredCandidate


def mmr_select(
    scored: list[ScoredCandidate],
    *,
    k: int = 20,
    lambda_mult: float = 0.75,
    model_name: str = "BAAI/bge-small-en-v1.5",
    model_cache_dir: str | None = None,
    logger: Any = None,
) -> list[ScoredCandidate]:
    """Select k diverse candidates using MMR over embedding space."""
    _log = logger or (lambda m: None)
    if len(scored) <= k:
        return scored

    try:
        import numpy as np

        model = get_model(model_name, model_cache_dir)

        texts = [f"{s.candidate.title}\n{s.candidate.abstract[:512]}" for s in scored]
        _log(f"  MMR: encoding {len(texts)} candidates...")
        embs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

        # Relevance = combined_score, normalized
        relevances = np.array([s.score_breakdown.get("combined_score", s.metadata_score) for s in scored])
        rel_min, rel_max = relevances.min(), relevances.max()
        if rel_max > rel_min:
            relevances = (relevances - rel_min) / (rel_max - rel_min)

        selected_idx: list[int] = []
        remaining = list(range(len(scored)))

        while len(selected_idx) < k and remaining:
            if not selected_idx:
                best = max(remaining, key=lambda i: relevances[i])
            else:
                sel_embs = embs[selected_idx]
                best, best_score = -1, float("-inf")
                for i in remaining:
                    rel = float(relevances[i])
                    sim = float(np.max(np.dot(sel_embs, embs[i])))
                    mmr_score = lambda_mult * rel - (1.0 - lambda_mult) * sim
                    if mmr_score > best_score:
                        best_score, best = mmr_score, i
            selected_idx.append(best)
            remaining.remove(best)

        result = [scored[i] for i in selected_idx]
        for sc in result:
            sc.score_breakdown["mmr_selected"] = True
        _log(f"  MMR selected {len(result)} papers")
        return result

    except Exception as exc:
        _log(f"  Warning: MMR failed ({exc}), returning top-k by score")
        return scored[:k]
