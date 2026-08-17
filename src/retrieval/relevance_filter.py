"""Query-faithful relevance scoring and hard rejection.

All phrase lists (positive, anchor, negative) come from a RetrievalIntent
(which is built from the active TopicProfileConfig).  There are no hardcoded
topic terms here — the scorer works for any ML research domain.

The legacy function `score_and_filter(candidates)` is kept for backwards
compatibility; it builds a generic intent from the candidates' collective titles.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .backends.base import PaperCandidate


@dataclass
class ScoredCandidate:
    candidate: PaperCandidate
    metadata_score: float = 0.0
    matched_positive_phrases: list[str] = field(default_factory=list)
    matched_anchor_phrases: list[str] = field(default_factory=list)
    matched_negative_phrases: list[str] = field(default_factory=list)
    keep: bool = True
    rejection_reason: str = ""
    score_breakdown: dict[str, Any] = field(default_factory=dict)


def score_and_filter_with_intent(
    candidates: list[PaperCandidate],
    intent: "Any",  # RetrievalIntent
    scoring_cfg: "Any | None" = None,  # ScoringConfig
    *,
    keep_threshold: float | None = None,
) -> tuple[list[ScoredCandidate], list[ScoredCandidate]]:
    """Score all candidates using phrases from the active RetrievalIntent."""
    threshold = keep_threshold
    if threshold is None:
        threshold = scoring_cfg.keep_threshold if scoring_cfg else 6.0

    pos_phrases = intent.must_have_phrases
    anchor_phrases = intent.should_have_phrases
    neg_phrases = intent.exclude_phrases
    on_fields = set(intent.on_domain_fields)
    off_fields = set(intent.off_domain_fields)

    kept, rejected = [], []
    for c in candidates:
        sc = _score_one(
            c,
            pos_phrases=pos_phrases,
            anchor_phrases=anchor_phrases,
            neg_phrases=neg_phrases,
            on_domain_fields=on_fields,
            off_domain_fields=off_fields,
            keep_threshold=threshold,
            scoring_cfg=scoring_cfg,
        )
        (kept if sc.keep else rejected).append(sc)
    kept.sort(key=lambda s: s.metadata_score, reverse=True)
    return kept, rejected


def score_and_filter(
    candidates: list[PaperCandidate],
    *,
    keep_threshold: float = 10.0,
) -> tuple[list[ScoredCandidate], list[ScoredCandidate]]:
    """Backwards-compatible entry point — derives phrases from candidate pool."""
    pos_phrases: list[str] = []
    kept, rejected = [], []
    for c in candidates:
        sc = _score_one(
            c,
            pos_phrases=pos_phrases,
            anchor_phrases=[],
            neg_phrases=[],
            on_domain_fields=set(),
            off_domain_fields=set(),
            keep_threshold=keep_threshold,
            scoring_cfg=None,
        )
        (kept if sc.keep else rejected).append(sc)
    kept.sort(key=lambda s: s.metadata_score, reverse=True)
    return kept, rejected


def _score_one(
    c: PaperCandidate,
    *,
    pos_phrases: list[str],
    anchor_phrases: list[str],
    neg_phrases: list[str],
    on_domain_fields: set[str],
    off_domain_fields: set[str],
    keep_threshold: float,
    scoring_cfg: "Any | None",
) -> ScoredCandidate:
    sc = ScoredCandidate(candidate=c)
    title = c.title.lower()
    abstract = c.abstract.lower()
    fos = " ".join(c.fields_of_study).lower() if hasattr(c, "fields_of_study") else ""
    breakdown: dict[str, float] = {}

    # ── Phrase matching ───────────────────────────────────────────────────────
    pos_title  = [p for p in pos_phrases    if p.lower() in title]
    pos_abs    = [p for p in pos_phrases    if p.lower() in abstract and p not in pos_title]
    anc_title  = [p for p in anchor_phrases if p.lower() in title]
    anc_abs    = [p for p in anchor_phrases if p.lower() in abstract and p not in anc_title]
    neg_title  = [p for p in neg_phrases    if p.lower() in title]
    neg_abs    = [p for p in neg_phrases    if p.lower() in abstract]

    sc.matched_positive_phrases = pos_title + pos_abs
    sc.matched_anchor_phrases   = anc_title + anc_abs
    sc.matched_negative_phrases = neg_title + neg_abs

    # ── Hard rejection ────────────────────────────────────────────────────────
    has_pos  = bool(pos_title or pos_abs)
    has_anc  = bool(anc_title or anc_abs)

    # When phrase lists ARE provided: require at least one positive or anchor hit
    if pos_phrases and not has_pos and not has_anc:
        sc.keep = False
        sc.rejection_reason = "no positive/anchor phrase in title+abstract"
        return sc

    if neg_title and not has_pos:
        sc.keep = False
        sc.rejection_reason = f"negative title phrase without positive signal: {neg_title[0]!r}"
        return sc

    if not c.abstract and len(title.split()) < 5:
        sc.keep = False
        sc.rejection_reason = "missing abstract and very short title"
        return sc

    if not has_pos and fos:
        off = [f for f in off_domain_fields if f in fos]
        if off and not has_anc:
            sc.keep = False
            sc.rejection_reason = f"off-domain fields with no positive/anchor signal: {off}"
            return sc

    # ── Scoring ───────────────────────────────────────────────────────────────
    cfg = scoring_cfg
    pw_t = cfg.pos_title_weight    if cfg else 6.0
    pw_a = cfg.pos_abstract_weight if cfg else 4.0
    aw_t = cfg.anchor_title_weight    if cfg else 4.0
    aw_a = cfg.anchor_abstract_weight if cfg else 3.0
    nw_t = cfg.neg_title_penalty    if cfg else -7.0
    nw_a = cfg.neg_abstract_penalty if cfg else -3.0
    ofd  = cfg.off_domain_penalty   if cfg else -4.0
    fos_b = cfg.fos_bonus           if cfg else 2.0
    cit_max = cfg.citation_bonus_max if cfg else 3.0
    ms_b = cfg.multi_source_bonus   if cfg else 1.0

    breakdown["pos_title"]    = pw_t * len(pos_title)
    breakdown["pos_abstract"] = pw_a * len(pos_abs)
    breakdown["anchor_title"] = aw_t * min(len(anc_title), 2)
    breakdown["anchor_abstract"] = aw_a * min(len(anc_abs), 2)
    score = sum(breakdown.values())

    # FoS bonus
    good = [f for f in on_domain_fields if f in fos]
    if good:
        breakdown["fos_bonus"] = fos_b * len(good)
        score += breakdown["fos_bonus"]

    # Multi-source bonus
    srcs = getattr(c, "source_names", [])
    if len(srcs) > 1:
        breakdown["multi_source"] = ms_b
        score += ms_b

    # Citation bonus
    cit = getattr(c, "citation_count", None)
    if cit and cit > 0 and "arxiv" not in srcs:
        bonus = min(math.log10(cit + 1), cit_max)
        breakdown["citation"] = bonus
        score += bonus

    # Negative penalties
    breakdown["neg_title"]    = nw_t * len(neg_title)
    breakdown["neg_abstract"] = nw_a * len(neg_abs)
    score += breakdown["neg_title"] + breakdown["neg_abstract"]

    # Off-domain field penalty
    off = [f for f in off_domain_fields if f in fos]
    if off:
        breakdown["off_domain"] = ofd * len(off)
        score += breakdown["off_domain"]

    sc.metadata_score = round(score, 4)
    sc.score_breakdown = breakdown

    if sc.metadata_score < keep_threshold:
        sc.keep = False
        sc.rejection_reason = f"metadata_score {sc.metadata_score:.1f} < threshold {keep_threshold}"

    return sc
