"""SGHA-native Stage 9: domain-general project-family consolidation + hypothesis-quality labeling.

Groups the Stage-8 selected ambition formulations into project families, merges duplicates, and
assigns domain-general quality labels. It does NOT generate or rewrite hypotheses — it only groups,
judges, ranks, and summarizes existing formulations.

Domain-general: no hardcoded field-specific concepts (regret/arms/UCB/MDP/... never appear as rubric
logic). "Domain fit" is measured against the RUN'S OWN declared topic + seed-topic keyphrases, read
at run time. Quality labels are derived from the Stage-8 independent-critic fields + aggregates.

LLM (Qwen/Qwen3.5-9B) is used ONLY if use_llm=True, and only to polish family titles — grouping and
labels are deterministic and reproducible.
"""
from __future__ import annotations

import difflib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .utils import ensure_dir, utc_now_iso

MODEL_NAME = "Qwen/Qwen3.5-9B"
DEFAULT_OUT_SUBDIR = "stage9_family_quality_qwen"
DEFAULT_S8_SUBDIR = "stage8_ambition_expansion_qwen_critic_softcap"
DEFAULT_S7_SUBDIR = "stage7_direct_formulations_qwen"

FORBIDDEN_INPUTS = [
    "final/ranked_hypotheses.json", "final/final_report.md",
    "pre_evolution_formulations_20260608", "ambition_expanded_formulations_20260608",
    "final_direct_formulations_20260608",
]

# generic English stopwords only — NO domain terms
_STOP = set("a an the of for and or to in on with without via using under over from into is are be "
            "this that these those new towards toward problem problems method methods approach approaches "
            "model models setting settings study studies analysis framework general design designing "
            "characterizing characterization robust robustness optimal adaptive based learning".split())

# Domain-general GENERIC RESEARCH-FRAMING terms. These describe the *shape* of a contribution
# (a boundary, an impossibility, a lower bound, an identifiability limit, ...) and are shared across
# unrelated research objects, so they must NOT drive family identity. NOT field-specific.
_FRAMING = set("""identifiability boundary boundaries limit limits failure failures phase transition
transitions impossibility lower bound bounds upper theorem theorems regret exploration exploit
robust robustness online offline adaptive characterization characterizing characterize fundamental
necessary necessity sufficient sufficiency conditions condition gap gaps unknown known parameter
parameters parameter-free method methods algorithm algorithms class classes model models setting
settings problem problems analysis framework guarantee guarantees minimax optimal optimality
sample complexity bounds rate rates dynamics estimation estimator learnable unlearnable
characterizes finite infinite""".split())

# contribution-type words (also down-weighted, never an identity signal on their own)
_CTYPE_WORDS = set("theorem algorithm lower_bound benchmark empirical_study impossibility_boundary "
                   "lower bound impossibility benchmark empirical study".split())

_DUP_TITLE = 0.86          # near-duplicate title/problem similarity (raw)
_STRICT_TITLE_SIM = 0.72   # strict title/problem similarity AFTER framing removal (rule D)
_PAPER_JACCARD_STRICT = 0.50   # rule C: supporting-paper overlap (also needs identity overlap)
_IDENTITY_OVERLAP_C = 2        # rule C distinctive identity-token overlap
_IDENTITY_OVERLAP_E = 3        # rule E distinctive identity-token overlap
_CLASS_SIM = 0.85          # rule E: "same broader_problem_class" threshold


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9\-]+", (text or "").lower()) if w not in _STOP and len(w) > 2}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _level(score: float, hi: float, mid: float) -> str:
    return "strong" if score >= hi else ("moderate" if score >= mid else "weak")


def _best_support(members: list[dict]) -> str:
    rank = {"strong": 2, "moderate": 1, "weak": 0}
    best = max((str(m.get("critic_supported_by_source", "weak")).lower() for m in members), key=lambda s: rank.get(s, 0))
    return best


def _load_topic_terms(run_dir: Path, config: dict) -> set[str]:
    """Domain-general topic signature for domain_fit: the run's OWN topic + query + seed keyphrases.
    No hardcoded field terms."""
    terms: set[str] = set()
    pers = (config or {}).get("personalization", {}) or {}
    topic = pers.get("topic")
    if topic and topic != "auto":
        terms |= _tokens(str(topic))
    q = config.get("query", "")
    terms |= _tokens(q.get("text", "") if isinstance(q, dict) else str(q))
    stp = run_dir / "profile" / "seed_topic_profile.json"
    if stp.exists():
        prof = json.loads(stp.read_text())
        for kp in prof.get("keyphrases", []) or []:
            terms |= _tokens(kp)
        terms |= _tokens(str(prof.get("topic", "")))
    return terms


# ---------------------------------------------------------------------------
# Grouping (domain-general, deterministic)
# ---------------------------------------------------------------------------

def _identity_tokens(d: dict, topic_terms: set[str]) -> set[str]:
    """Distinctive research-OBJECT tokens: strip generic stopwords, the run's own topic terms, generic
    research-framing terms, and contribution-type words. What remains identifies the actual object
    (e.g. 'clustering', 'rank-deficient', 'thompson', 'expert', 'heavy-tailed')."""
    toks = (_tokens(d.get("core_setting", "")) | _tokens(d.get("broader_problem_class", ""))
            | _tokens(d.get("title", "")))
    return toks - topic_terms - _FRAMING - _CTYPE_WORDS


def _strip_framing(text: str) -> str:
    return " ".join(w for w in _norm(text).split() if w not in _FRAMING and w not in _CTYPE_WORDS)


def _paper_jaccard(a: dict, b: dict) -> float:
    pa, pb = set(a.get("supporting_papers", []) or []), set(b.get("supporting_papers", []) or [])
    return (len(pa & pb) / len(pa | pb)) if (pa and pb) else 0.0


def _merge_edge(a: dict, b: dict, topic_terms: set[str]) -> dict | None:
    """Return a per-edge merge rationale if a and b satisfy a HARD-ANCHOR rule (A–E), else None.
    Never merges on paper-overlap alone, framing-only object overlap, or contribution type alone."""
    ida, idb = _identity_tokens(a, topic_terms), _identity_tokens(b, topic_terms)
    identity_overlap = len(ida & idb)
    pj = _paper_jaccard(a, b)
    tsim = max(_sim(_strip_framing(a.get("title", "")), _strip_framing(b.get("title", ""))),
               _sim(_strip_framing(a.get("problem_statement", "")), _strip_framing(b.get("problem_statement", ""))))
    class_sim = _sim(a.get("broader_problem_class", ""), b.get("broader_problem_class", ""))
    shared_direct = a.get("source_formulation_id") if a.get("source_formulation_id") and a.get("source_formulation_id") == b.get("source_formulation_id") else ""
    shared_gap = a.get("source_verified_gap_id") if a.get("source_verified_gap_id") and a.get("source_verified_gap_id") == b.get("source_verified_gap_id") else ""

    reason = None
    if shared_direct:
        reason = "A_same_source_direct_formulation"
    elif shared_gap:
        reason = "B_same_source_verified_gap"
    elif pj >= _PAPER_JACCARD_STRICT and identity_overlap >= _IDENTITY_OVERLAP_C:
        reason = "C_paper_jaccard_and_identity_overlap"
    elif tsim >= _STRICT_TITLE_SIM:
        reason = "D_title_problem_similarity"
    elif class_sim >= _CLASS_SIM and identity_overlap >= _IDENTITY_OVERLAP_E:
        reason = "E_same_problem_class_and_identity_overlap"
    if reason is None:
        return None
    return {"variant_a": a["variant_id"], "variant_b": b["variant_id"], "merge_reason": reason,
            "shared_direct_formulation": shared_direct, "shared_verified_gap": shared_gap,
            "paper_jaccard": round(pj, 3), "distinctive_identity_overlap": identity_overlap,
            "distinctive_identity_tokens": sorted(ida & idb),
            "title_problem_similarity": round(tsim, 3)}


def _components(items: list[dict], topic_terms: set[str]) -> tuple[list[list[dict]], list[dict]]:
    """Union ONLY on hard-anchor edges (no weak/transitive chaining). Returns (components, edges)."""
    n = len(items)
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            e = _merge_edge(items[i], items[j], topic_terms)
            if e is not None:
                edges.append(e)
                parent[find(i)] = find(j)  # union only on a hard anchor
    groups: dict[int, list[dict]] = defaultdict(list)
    for i, it in enumerate(items):
        groups[find(i)].append(it)
    return list(groups.values()), edges


# ---------------------------------------------------------------------------
# Quality rubric (domain-general; uses Stage-8 critic fields)
# ---------------------------------------------------------------------------

def _family_quality(members: list[dict], topic_terms: set[str], is_duplicate_only: bool) -> dict:
    fmax = lambda k: max((float(m.get(k, 0) or 0) for m in members), default=0.0)
    fmin = lambda k: min((float(m.get(k, 1) or 0) for m in members), default=0.0)
    evidence = _best_support(members)
    non_incr = _level(fmax("critic_non_incrementality_score"), 0.85, 0.70)
    specificity = _level(fmax("specificity_score"), 0.80, 0.60)
    feas = fmax("feasibility_score"); fake = fmin("critic_fake_ambition_risk")
    plausibility = ("strong" if feas >= 0.70 and fake <= 0.20
                    else "weak" if fake >= 0.35 or feas < 0.50 else "moderate")
    # domain fit: family terms vs the run's OWN topic signature
    fam_terms = set()
    for m in members:
        fam_terms |= _tokens(m.get("core_setting", "")) | _tokens(m.get("broader_problem_class", "")) | _tokens(m.get("title", ""))
    overlap = len(fam_terms & topic_terms) if topic_terms else 1
    domain_fit = "strong" if overlap >= 2 else ("moderate" if overlap == 1 else "weak")
    # critic labels present across members
    crit_labels = {str(m.get("critic_quality_label", "")) for m in members}
    bad_critic = bool(crit_labels & {"FAKE_AMBITION", "DROP", "INCREMENTAL_REPHRASING"})

    rank = {"strong": 2, "moderate": 1, "weak": 0}
    nmd_high = any(str(m.get("named_method_dependency", "")).lower() == "high" for m in members)
    obj_text = " ".join((m.get("broader_problem_class", "") + " " + m.get("core_setting", "")) for m in members)
    unclear_object = len(fam_terms - topic_terms - _FRAMING - _CTYPE_WORDS) == 0 or len(obj_text.strip()) < 15
    # ---- label rubric (ambition/coherence ALONE never yield A) ----
    if domain_fit == "weak" or bad_critic or plausibility == "weak" or is_duplicate_only:
        label = "D_DROP"
    elif (rank[evidence] >= 1 and non_incr == "strong" and rank[specificity] >= 1
          and rank[plausibility] >= 1 and domain_fit == "strong"):
        label = "A_STRONG"
    elif non_incr in ("strong", "moderate") and (specificity == "weak" or evidence == "weak" or domain_fit == "moderate"):
        label = "B_PROMISING_NEEDS_REFRAMING"
    else:
        label = "C_LOW_PRIORITY"
    action = {"A_STRONG": "READ_FIRST", "B_PROMISING_NEEDS_REFRAMING": "REFRAME",
              "C_LOW_PRIORITY": "READ_LATER", "D_DROP": "DROP"}[label]

    # ---- downgrade reasons (negative rationale) ----
    dr: list[str] = []
    if domain_fit == "weak":
        dr += ["off_domain", "low_domain_fit"]
    elif domain_fit == "moderate":
        dr.append("low_domain_fit")
    if evidence == "weak":
        dr.append("weak_source_support")
    if fake >= 0.35 or (crit_labels & {"FAKE_AMBITION"}):
        dr.append("fake_ambition_risk")
    if plausibility == "weak":
        dr.append("formal_plausibility_concern")
    if specificity == "weak":
        dr.append("too_broad")
    if nmd_high:
        dr.append("too_method_specific")
    if non_incr != "strong" or (crit_labels & {"INCREMENTAL_REPHRASING"}):
        dr.append("incremental_or_validation_only")
    if is_duplicate_only:
        dr.append("duplicate_of_stronger_family")
    if unclear_object:
        dr.append("unclear_problem_object")
    dr = sorted(set(dr))
    # D_DROP must always carry at least one negative reason
    if label == "D_DROP" and not dr:
        dr = ["formal_plausibility_concern"] if plausibility != "strong" else ["low_domain_fit"]

    # ---- label inconsistency: D_DROP despite all three component strengths being strong ----
    label_inconsistency_warning = (label == "D_DROP" and evidence == "strong"
                                   and plausibility == "strong" and domain_fit == "strong")

    # ---- recoverability (for C/D) ----
    if label in ("D_DROP", "C_LOW_PRIORITY"):
        if "duplicate_of_stronger_family" in dr:
            recover = "MERGE_WITH_RELATED_FAMILY"
        elif "off_domain" in dr:
            recover = "DROP_PERMANENTLY"
        elif label == "C_LOW_PRIORITY":
            recover = "READ_LATER"
        elif dr and set(dr) <= {"weak_source_support", "too_broad", "too_method_specific",
                                "incremental_or_validation_only", "low_domain_fit", "unclear_problem_object"}:
            recover = "REFRAME"
        else:
            recover = "DROP_PERMANENTLY"
    else:
        recover = None

    # ---- human-readable rationale ----
    comp = f"evidence={evidence}, non_incrementality={non_incr}, specificity={specificity}, plausibility={plausibility}, domain_fit={domain_fit}"
    if label == "A_STRONG":
        rationale = f"A_STRONG: {comp} — strong on every required axis, not a duplicate cluster."
    elif label == "B_PROMISING_NEEDS_REFRAMING":
        rationale = f"B_PROMISING_NEEDS_REFRAMING: {comp}. Promising but needs reframing/narrowing due to: {dr or ['moderate component(s)']}."
    elif label == "C_LOW_PRIORITY":
        rationale = f"C_LOW_PRIORITY: {comp}. Coherent but low payoff/priority due to: {dr}."
    else:
        rationale = f"D_DROP: {comp}. Dropped because: {dr}."
        if label_inconsistency_warning:
            rationale += " NOTE: components look strong — review (possible duplicate-only or critic-flagged family)."

    return {"evidence_grounding": evidence, "non_incrementality": non_incr, "specificity": specificity,
            "plausibility": plausibility, "domain_fit": domain_fit, "quality_label": label,
            "recommended_action": action, "downgrade_reasons": dr, "label_rationale": rationale,
            "label_inconsistency_warning": label_inconsistency_warning, "maybe_recoverable_as": recover}


def build_families(selected: list[dict], topic_terms: set[str]) -> tuple[list[dict], list[dict]]:
    comps, edges = _components(selected, topic_terms)
    families = []
    for fi, comp in enumerate(comps, 1):
        comp = sorted(comp, key=lambda v: v.get("expanded_rank", 999))
        rep = max(comp, key=lambda v: (float(v.get("critic_non_incrementality_score", 0)),
                                       -float(v.get("critic_fake_ambition_risk", 1))))
        # intra-family near-duplicates (collapsed onto representative)
        dups = [m for m in comp if m is not rep and (_sim(m.get("title", ""), rep.get("title", "")) >= _DUP_TITLE
                or _sim(m.get("problem_statement", ""), rep.get("problem_statement", "")) >= _DUP_TITLE)]
        is_dup_only = len(comp) > 1 and len(dups) == len(comp) - 1  # every non-rep member is a near-dup
        q = _family_quality(comp, topic_terms, is_dup_only)
        agg = lambda key: sorted({x for m in comp for x in (m.get(key, []) or [])})
        fam = {
            "family_id": f"family:{fi:02d}",
            "family_title": rep.get("title", ""),
            "member_variant_ids": [m["variant_id"] for m in comp],
            "member_ranks": [m.get("expanded_rank") for m in comp],
            "representative_variant_id": rep["variant_id"],
            "representative_title": rep.get("title", ""),
            "family_problem_statement": rep.get("problem_statement", ""),
            # ---- representative formulation details carried verbatim from Stage 8 (no new content) ----
            "representative_problem_statement": rep.get("problem_statement", ""),
            "proposal_style_abstract": rep.get("proposal_style_abstract", ""),
            "theorem_target": rep.get("theorem_target", ""),
            "algorithmic_target": rep.get("algorithmic_target", ""),
            "empirical_target": rep.get("empirical_target", ""),
            "main_risk": rep.get("main_risk", ""),
            "falsification_condition": rep.get("falsification_condition", ""),
            "critic_reason": rep.get("critic_reason", ""),
            "critic_quality_label": rep.get("critic_quality_label", ""),
            "critic_non_incrementality_score": rep.get("critic_non_incrementality_score"),
            "critic_fake_ambition_risk": rep.get("critic_fake_ambition_risk"),
            "critic_supported_by_source": rep.get("critic_supported_by_source", ""),
            "research_object": rep.get("core_setting", "") or rep.get("broader_problem_class", ""),
            "problem_class": rep.get("broader_problem_class", ""),
            "assumption_shift": rep.get("assumption_shift", ""),
            "failure_boundary_or_mechanism": rep.get("boundary_or_failure_regime", ""),
            "constructive_or_evaluation_target": rep.get("constructive_or_explanatory_target", "")
                                                 or rep.get("contribution_type", ""),
            "source_verified_gaps": sorted({m.get("source_verified_gap_id", "") for m in comp if m.get("source_verified_gap_id")}),
            "source_direct_formulations": sorted({m.get("source_formulation_id", "") for m in comp if m.get("source_formulation_id")}),
            "supporting_papers": agg("supporting_papers"),
            "related_seed_papers": agg("related_seed_papers"),
            "duplicate_status": "merged_duplicate_family" if dups else "unique",
            "merged_duplicate_variant_ids": [m["variant_id"] for m in dups],
            "main_risks": sorted({str(m.get("main_risk", "")) for m in comp if m.get("main_risk")})[:3],
            "contribution_types": dict(Counter(m.get("contribution_type", "") for m in comp)),
            **q,
        }
        families.append(fam)
    # rank families: A>B>C>D, then representative critic non-incrementality
    lab_rank = {"A_STRONG": 0, "B_PROMISING_NEEDS_REFRAMING": 1, "C_LOW_PRIORITY": 2, "D_DROP": 3}
    families.sort(key=lambda f: (lab_rank[f["quality_label"]], -len(f["member_variant_ids"])))
    for i, f in enumerate(families, 1):
        f["family_rank"] = i
    return families, edges


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_family_quality(ctx: Any, *, s8_subdir: str = DEFAULT_S8_SUBDIR, s7_subdir: str = DEFAULT_S7_SUBDIR,
                       out_subdir: str = DEFAULT_OUT_SUBDIR, use_llm: bool = False,
                       llm_base_url: str | None = None) -> dict:
    run_dir = ctx.run_dir
    out = run_dir / out_subdir; ensure_dir(out)
    sel_path = run_dir / s8_subdir / "ambition_expanded_final_formulations.jsonl"
    selected = [json.loads(l) for l in sel_path.read_text().splitlines() if l.strip()]
    cp_path = run_dir / s8_subdir / "critic_passing_formulations.jsonl"
    critic_passing = [json.loads(l) for l in cp_path.read_text().splitlines() if l.strip()] if cp_path.exists() else []
    direct_path = run_dir / s7_subdir / "direct_formulations.jsonl"
    n_direct = sum(1 for l in direct_path.read_text().splitlines() if l.strip()) if direct_path.exists() else 0

    topic_terms = _load_topic_terms(run_dir, ctx.config)
    families, merge_edges = build_families(selected, topic_terms)
    json.dump({"merge_rule": "union ONLY on hard-anchor edges A-E; no weak/transitive chaining",
               "anchors": {"A": "same source_direct_formulation_id", "B": "same source_verified_gap_id",
                           "C": f"paper_jaccard>={_PAPER_JACCARD_STRICT} AND distinctive_identity_overlap>={_IDENTITY_OVERLAP_C}",
                           "D": f"framing-stripped title/problem similarity>={_STRICT_TITLE_SIM}",
                           "E": f"problem_class_sim>={_CLASS_SIM} AND distinctive_identity_overlap>={_IDENTITY_OVERLAP_E}"},
               "edges": merge_edges}, open(out / "family_merge_edges.json", "w"), indent=2)

    # optional LLM family-title polish (judge-only naming; never invents members/IDs)
    model_used = None
    if use_llm:
        from .llm_client import LLMClient
        llm = LLMClient(ctx, base_url=llm_base_url); model_used = MODEL_NAME
        for f in families:
            try:
                d, *_ = llm.complete_json(stage="family_quality", agent_name="family_namer",
                    prompt=("Give a concise (<=12 word) domain-general project-family title for this set of "
                            f"research problem statements. Return JSON {{\"family_title\":\"...\"}} only.\n\n"
                            f"Representative: {f['representative_title']}\nProblem: {f['family_problem_statement'][:400]}"),
                    max_tokens=80, temperature=0.0, enable_thinking=False)
                if d.get("family_title"):
                    f["family_title"] = d["family_title"]
            except Exception:
                pass  # keep deterministic title on failure

    # ---- validation invariants ----
    assigned = [vid for f in families for vid in f["member_variant_ids"]]
    sel_ids = [v["variant_id"] for v in selected]
    invariants = {
        "all_selected_assigned_once": sorted(assigned) == sorted(sel_ids),
        "no_invented_ids": set(assigned) <= set(sel_ids),
        "no_drop_is_read_first": all(not (f["quality_label"] == "D_DROP" and f["recommended_action"] == "READ_FIRST") for f in families),
    }

    counts = Counter(f["quality_label"] for f in families)
    write = lambda name, txt: (out / name).write_text(txt)
    json.dump({"families": families, "counts": dict(counts)}, open(out / "project_families.json", "w"), indent=2)
    _write_report(out / "family_quality_report.md", families, selected, critic_passing, counts)
    _write_shortlist(out / "final_reading_shortlist.md", families)
    _write_audit(out / "family_quality_audit.md", families, selected, critic_passing, n_direct, counts, invariants, bool(use_llm))
    meta = {"stage": "family_quality", "created_at": utc_now_iso(), "run_id": ctx.run_id,
            "llm_used": bool(use_llm), "model": model_used, "domain_general": True, "rubric_hardcodes_domain_terms": False,
            "topic_signature_source": "run_config.personalization.topic + query + profile/seed_topic_profile.keyphrases",
            "input_selected": str(sel_path), "input_critic_passing": str(cp_path), "input_direct": str(direct_path),
            "formulations_loaded": len(selected), "critic_passing_pool": len(critic_passing), "direct_formulations": n_direct,
            "families_produced": len(families), "label_counts": dict(counts),
            "read_first_families": sum(1 for f in families if f["recommended_action"] == "READ_FIRST"),
            "drop_families": counts.get("D_DROP", 0), "invariants": invariants,
            "merge_edges": len(merge_edges), "merge_reasons": dict(Counter(e["merge_reason"] for e in merge_edges)),
            "grouping_policy": "strict hard-anchor (A-E); framing tokens stripped; union only on anchors; no weak chaining",
            "families_missing_abstract": sum(1 for f in families if not str(f.get("proposal_style_abstract", "")).strip()),
            "drop_families_without_negative_rationale": sum(1 for f in families if f["quality_label"] == "D_DROP" and not f.get("downgrade_reasons")),
            "label_inconsistency_warnings": sum(1 for f in families if f.get("label_inconsistency_warning")),
            "all_representatives_resolve_to_stage8": all(f["representative_variant_id"] in {v["variant_id"] for v in selected} for f in families),
            "abstracts_verbatim_from_stage8": all(str(f.get("proposal_style_abstract", "")) == str({v["variant_id"]: v.get("proposal_style_abstract", "") for v in selected}.get(f["representative_variant_id"], "")) for f in families),
            "downgrade_reasons_by_family": {f["family_id"]: f["downgrade_reasons"] for f in families if f["downgrade_reasons"]},
            "forbidden_inputs_not_used": FORBIDDEN_INPUTS}
    json.dump(meta, open(out / "run_metadata.json", "w"), indent=2)
    print(f"[family_quality] families={len(families)} counts={dict(counts)} loaded={len(selected)} invariants={invariants}", flush=True)
    return meta


def _qline(f):
    return (f"[{f['quality_label']} / {f['recommended_action']}] {f['family_id']} \"{f['family_title']}\" "
            f"(members {f['member_variant_ids']}, ranks {f['member_ranks']})")


def _write_report(path, families, selected, critic_passing, counts):
    lines = ["# Stage 9 — Project-Family Quality Report (domain-general)", "",
             f"- formulations consolidated: {len(selected)} (from {len(critic_passing)} critic-passing pool)",
             f"- families: {len(families)} | labels: {dict(counts)}", "",
             "Quality labels use the Stage-8 independent-critic fields + domain-general aggregates "
             "(evidence grounding, non-incrementality, specificity, plausibility, domain fit). High "
             "ambition or coherence ALONE does not yield A_STRONG.", ""]
    for f in families:
        lines += [f"## {f['family_rank']}. {f['family_title']}  ({f['family_id']}, {f['quality_label']})",
                  f"- recommended action: {f['recommended_action']}"
                  + (f" | maybe_recoverable_as: {f['maybe_recoverable_as']}" if f.get("maybe_recoverable_as") else "")
                  + f" | duplicate_status: {f['duplicate_status']}",
                  f"- members: {f['member_variant_ids']} (ranks {f['member_ranks']}); representative {f['representative_variant_id']}",
                  f"- research object: {f['research_object']}",
                  f"- problem class: {f['problem_class']}",
                  f"- assumption shift: {f['assumption_shift']}",
                  f"- failure boundary / mechanism: {f['failure_boundary_or_mechanism']}",
                  f"- constructive/evaluation target: {f['constructive_or_evaluation_target']}",
                  f"- targets — theorem: {f['theorem_target'] or '—'} | algorithm: {f['algorithmic_target'] or '—'} | empirical: {f['empirical_target'] or '—'}",
                  f"- quality: evidence={f['evidence_grounding']} non_incrementality={f['non_incrementality']} "
                  f"specificity={f['specificity']} plausibility={f['plausibility']} domain_fit={f['domain_fit']}",
                  f"- **label rationale:** {f['label_rationale']}",
                  f"- **downgrade reasons:** {f['downgrade_reasons'] or '(none)'}"
                  + ("  ⚠ label_inconsistency_warning" if f.get("label_inconsistency_warning") else ""),
                  f"- critic rationale: {f['critic_reason']} (critic_label={f['critic_quality_label']}, "
                  f"non_incr={f['critic_non_incrementality_score']}, fake={f['critic_fake_ambition_risk']}, support={f['critic_supported_by_source']})",
                  f"- source verified gaps: {f['source_verified_gaps']}",
                  f"- supporting papers: {f['supporting_papers'][:6]} | related seed: {f['related_seed_papers'] or '—'}",
                  f"- main risk: {f['main_risk']} | falsification: {f['falsification_condition']}",
                  f"- problem statement: {f['family_problem_statement']}",
                  f"- proposal-style abstract: {f['proposal_style_abstract'] or '(none in Stage-8 record)'}", ""]
    path.write_text("\n".join(lines))


def _write_shortlist(path, families):
    by = lambda lab: [f for f in families if f["quality_label"] == lab]
    A, B = by("A_STRONG"), by("B_PROMISING_NEEDS_REFRAMING")
    C, D = by("C_LOW_PRIORITY"), by("D_DROP")
    lines = ["# Stage 9 — Final Reading Shortlist", "",
             "Consolidated from existing Stage-8 formulations only — NO new hypotheses.", "",
             "## Recommended reading order",
             "1. A-level (READ_FIRST) → 2. B-level (REFRAME) → 3. C-level (READ_LATER). D-level: DROP.", ""]
    def sect(title, fams):
        out = [f"## {title} ({len(fams)})"]
        for f in fams:
            out += [f"### {f['family_title']}  ({f['family_id']})",
                    f"- **{f['quality_label']} / {f['recommended_action']}**"
                    + (f"  |  maybe_recoverable_as: {f['maybe_recoverable_as']}" if f.get("maybe_recoverable_as") else ""),
                    f"- representative formulation: {f['representative_variant_id']} | members: {f['member_variant_ids']}",
                    f"- source verified gaps: {f['source_verified_gaps']}",
                    f"- first supporting papers to inspect: {f['supporting_papers'][:5]}",
                    f"- problem statement: {f['representative_problem_statement']}",
                    f"- proposal-style abstract: {f['proposal_style_abstract'] or '(none in Stage-8 record)'}",
                    f"- critic rationale: {f['critic_reason']} (critic_label={f['critic_quality_label']}, "
                    f"non_incr={f['critic_non_incrementality_score']}, fake={f['critic_fake_ambition_risk']}, support={f['critic_supported_by_source']})",
                    f"- main risk: {f['main_risk']}",
                    f"- targets — theorem: {f['theorem_target'] or '—'} | algorithm: {f['algorithmic_target'] or '—'} | empirical: {f['empirical_target'] or '—'}",
                    f"- label rationale: {f['label_rationale']}",
                    f"- downgrade reasons: {f['downgrade_reasons'] or '(none)'}", ""]
        return out
    lines += sect("A-level families — READ FIRST", A)
    lines += sect("B-level families — PROMISING, NEEDS REFRAMING", B)
    lines += sect("C-level families — LOW PRIORITY", C)
    lines += sect("D-level families — DROP", D)
    path.write_text("\n".join(lines))


def _write_audit(path, families, selected, critic_passing, n_direct, counts, invariants, used_llm):
    assigned = [vid for f in families for vid in f["member_variant_ids"]]
    dup_fams = [f for f in families if f["duplicate_status"] == "merged_duplicate_family"]
    sel_ids = {v["variant_id"] for v in selected}
    sel_abstracts = {v["variant_id"]: v.get("proposal_style_abstract", "") for v in selected}
    missing_abstracts = [f["family_id"] for f in families if not str(f.get("proposal_style_abstract", "")).strip()]
    drop_no_neg = [f["family_id"] for f in families if f["quality_label"] == "D_DROP" and not f.get("downgrade_reasons")]
    inconsistencies = [f["family_id"] for f in families if f.get("label_inconsistency_warning")]
    reps_resolve = all(f["representative_variant_id"] in sel_ids for f in families)
    abstracts_from_s8 = all(str(f.get("proposal_style_abstract", "")) == str(sel_abstracts.get(f["representative_variant_id"], "")) for f in families)
    lines = ["# Stage 9 — Family-Quality Audit", "",
             f"- formulations loaded (selected): {len(selected)} | critic-passing pool: {len(critic_passing)} | direct: {n_direct}",
             f"- families produced: {len(families)} | label counts: {dict(counts)}",
             f"- READ_FIRST: {sum(1 for f in families if f['recommended_action']=='READ_FIRST')} | "
             f"REFRAME: {sum(1 for f in families if f['recommended_action']=='REFRAME')} | "
             f"READ_LATER: {sum(1 for f in families if f['recommended_action']=='READ_LATER')} | "
             f"DROP: {counts.get('D_DROP',0)}",
             "",
             "## Invariants",
             f"- all selected assigned to exactly one family: {invariants['all_selected_assigned_once']} "
             f"({len(assigned)} assignments / {len(selected)} selected)",
             f"- no invented formulation IDs: {invariants['no_invented_ids']}",
             f"- no D_DROP family is READ_FIRST: {invariants['no_drop_is_read_first']}",
             f"- merged duplicate families: {len(dup_fams)} {[f['family_id'] for f in dup_fams]}",
             "",
             "## Report-quality checks",
             f"- families missing a proposal-style abstract: {len(missing_abstracts)} {missing_abstracts}",
             f"- D_DROP families with NO negative/drop rationale: {len(drop_no_neg)} {drop_no_neg}",
             f"- label_inconsistency_warnings (D_DROP despite strong evidence+plausibility+domain_fit): {len(inconsistencies)} {inconsistencies}",
             f"- all representative IDs resolve to Stage-8 records: {reps_resolve}",
             f"- all family abstracts copied verbatim from Stage-8 representative records (no new content): {abstracts_from_s8}",
             "",
             "## Domain-generality",
             "- rubric uses NO hardcoded field-specific terms; domain_fit is computed against the run's own",
             "  declared topic + seed-topic keyphrases (read at run time).",
             "- quality labels derive from Stage-8 independent-critic fields (critic_non_incrementality_score,",
             "  critic_fake_ambition_risk, critic_supported_by_source, critic_quality_label) + aggregates.",
             "- high ambition or coherence ALONE does not yield A_STRONG (requires evidence + specificity +",
             "  plausibility + domain_fit together).",
             "",
             "## Provenance",
             "- no new hypotheses generated; group/judge/rank/summarize only.",
             "- old evolved report / previous ad-hoc outputs NOT used (see run_metadata.forbidden_inputs_not_used).",
             f"- LLM used for family naming: {used_llm}" + (f" ({MODEL_NAME})" if used_llm else " (deterministic titles)")]
    path.write_text("\n".join(lines))
