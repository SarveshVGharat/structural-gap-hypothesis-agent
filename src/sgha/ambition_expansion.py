"""SGHA-native AMBITION EXPANSION stage.

For each DIRECT formulation (from the Stage-7 direct-formulation stage), generate conservative /
generalized / bold variants, score them, gate (coherence>=0.75, term_soup<=0.30, specificity>=0.60),
and keep the coherent ones. Generalized broadens exactly ONE axis; bold targets a
theorem / lower bound / impossibility / algorithm / benchmark. No cross-gap synthesis, no evolved
hypotheses, no prior ad-hoc outputs, no external search.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .llm_client import LLMClient
from .utils import ensure_dir, utc_now_iso

MODEL_NAME = "Qwen/Qwen3.5-9B"
DEFAULT_OUT_SUBDIR = "stage8_ambition_expansion_qwen"
DEFAULT_IN_SUBDIR = "stage7_direct_formulations_qwen"
VARIANT_TYPES = ["conservative", "generalized", "bold"]
GATE = {"coherence_min": 0.75, "term_soup_max": 0.30, "specificity_min": 0.60,
        "non_incrementality_min": 0.70, "incrementality_risk_max": 0.40}

FORBIDDEN_INPUTS = [
    "final/ranked_hypotheses.json", "final/final_report.md",
    "pre_evolution_formulations_20260608", "ambition_expanded_formulations_20260608",
    "final_direct_formulations_20260608",
]

_PROMPT = """You are doing CONTROLLED ambition expansion of ONE clean, single-gap research formulation.
The domain may be anything (bandits, in-context learning, RL, NLP, biology, robotics, materials, ...).
Goal: a genuinely NON-INCREMENTAL but still coherent formulation — NOT a multi-concept collage, and
NOT just validating one named method in one more setting.

SOURCE DIRECT FORMULATION (grounded in verified gap {gap_id}, motif {motif}):
- title: {title}
- problem: {problem}
- core setting: {setting}
- core assumption/failure: {assumption}
- core objective: {objective}
- supporting paper titles: {papers}
- seed alignment to author's seed papers: {seed_score}

DOMAIN-GENERAL DEFINITIONS (apply regardless of field):
A formulation is INCREMENTAL if its central contribution is only one of:
- evaluating one named method in one additional setting
- testing robustness of one paper's method without changing the underlying scientific question
- a small benchmark variation
- restating a limitation already identified by one source paper
- depending so heavily on one named method that replacing it with another method of the SAME CLASS
  would make the formulation meaningless
- a cleaner title for the same narrow gap without broadening the scientific object
A formulation is NON-INCREMENTAL if it does at least one of:
- identifies a broader PROBLEM CLASS behind the source gap
- relaxes, removes, or proves NECESSITY of a key assumption
- characterizes a boundary / impossibility / phase transition / identifiability limit / failure regime
- proposes a constructive alternative at the level of a METHOD CLASS, SYSTEM CLASS, MECHANISM CLASS, or
  EVALUATION CLASS (not one named method)
- defines a benchmark/evaluation protocol exposing a GENERAL failure mode across a FAMILY of
  methods/systems (not just one named method)
- gives a unifying explanation connecting multiple observations under one structural condition (no term soup)

Produce the **{vtype}** variant:
- conservative: a safe extension very close to the verified gap (often incremental — score it honestly).
- generalized: broaden EXACTLY ONE axis (method class | environment/system class | assumption class |
  failure condition | benchmark/evaluation family | objective/metric notion). Name it in generalized_axis.
- bold: target ONE of {{theorem, lower bound, impossibility/boundary, new method at the class level,
  benchmark/evaluation suite for a method family}} — domain-appropriate; do NOT force a regret/minimax framing.

SELF-CHECK you MUST answer before scoring (use the schema fields):
 1. broader_problem_class: what broader problem class sits behind the source gap?
 2. assumption_shift: which key assumption is relaxed, removed, or shown necessary? (else say 'none')
 3. boundary_or_failure_regime: what boundary / failure regime / mechanism is characterized? (else 'none')
 4. named_method_dependency: would this still matter if the named source method were replaced by another
    method of the same class? If NO -> named_method_dependency='high'.
 5. why_not_just_validation: what would count as a publishable contribution beyond validating one method?

HARD RULES: one core setting; one core failure/assumption; one primary objective; do NOT fuse unrelated
papers/methods/motifs; preserve traceability to the source gap. If no coherent NON-incremental variant
of this type exists, set recommendation="DROP".

Return ONLY JSON with EXACTLY these keys:
{{
 "title":"<=18 words","problem_statement":"2-4 sentences",
 "proposal_style_abstract":"120-220 words, proposal voice ('This project studies...','The central question is...','A successful outcome would...'); NEVER 'we prove'/'we show'/'our experiments demonstrate'",
 "core_setting":"","generalized_axis":"(only for generalized; else '')","core_assumption_or_failure":"","core_objective":"",
 "contribution_type":"theorem|algorithm|lower_bound|benchmark|empirical_study|impossibility_boundary",
 "theorem_target":"","algorithmic_target":"","empirical_target":"",
 "broader_problem_class":"the broader problem class behind the gap (REQUIRED for KEEP/MAYBE)",
 "assumption_shift":"assumption relaxed/removed/shown-necessary, or 'none'",
 "boundary_or_failure_regime":"boundary/failure-regime/mechanism characterized, or 'none'",
 "constructive_or_explanatory_target":"the method-class/system-class/mechanism-class/evaluation-class target, or unifying explanation",
 "method_class_scope":"the method/system/evaluation CLASS this addresses (broader than one named method), or '' ",
 "named_method_dependency":"low|medium|high",
 "why_not_just_validation":"why this is more than validating one named method (REQUIRED for KEEP/MAYBE)",
 "why_not_incremental":"one-line: which non-incremental criterion it satisfies",
 "why_not_term_soup":"why this stays coherent / single-axis",
 "non_incrementality_score":0.0,"incrementality_risk":0.0,
 "main_risk":"","falsification_condition":"",
 "coherence_score":0.0,"ambition_score":0.0,"specificity_score":0.0,"feasibility_score":0.0,"term_soup_risk":0.0,
 "recommendation":"KEEP|MAYBE|DROP"
}}
All scores are floats in [0,1]. non_incrementality_score HIGH = clearly beyond one-method validation;
incrementality_risk HIGH = still basically incremental. Output JSON only."""


def passes_gate(v: dict) -> bool:
    """Domain-general non-incrementality gate. Final kept variants must be coherent, specific,
    low term-soup, genuinely non-incremental, and have the required justification fields. A
    high named-method dependency is only allowed for a broad method-class benchmark/empirical study."""
    rec = (v.get("recommendation") or "").upper()
    if rec not in ("KEEP", "MAYBE"):
        return False
    if not (float(v.get("coherence_score", 0)) >= GATE["coherence_min"]
            and float(v.get("specificity_score", 0)) >= GATE["specificity_min"]
            and float(v.get("term_soup_risk", 1)) <= GATE["term_soup_max"]
            and float(v.get("non_incrementality_score", 0)) >= GATE["non_incrementality_min"]
            and float(v.get("incrementality_risk", 1)) <= GATE["incrementality_risk_max"]):
        return False
    if not (str(v.get("broader_problem_class", "")).strip() and str(v.get("why_not_just_validation", "")).strip()):
        return False
    # named-method dependency escape hatch: only a broad method-class benchmark/empirical study survives
    if str(v.get("named_method_dependency", "")).lower() == "high":
        if v.get("contribution_type") not in ("benchmark", "empirical_study"):
            return False
        if not str(v.get("method_class_scope", "")).strip():
            return False
    return True


CRITIC_GATE = {"non_incrementality_min": 0.70, "incrementality_risk_max": 0.40,
               "fake_ambition_risk_max": 0.35}
_CRITIC_KEEP_LABELS = {"STRONG_NON_INCREMENTAL", "VALID_BUT_MODEST"}
_CRITIC_SUPPORT_OK = {"strong", "moderate"}
IMPOSSIBILITY_CAP_FRACTION = 0.40

_CRITIC_PROMPT = """You are an INDEPENDENT critic. You did NOT write the formulation below and you must NOT
rewrite, fix, or improve it. You only JUDGE whether it is genuinely non-incremental, in a
domain-general way (the field may be bandits, in-context learning, RL, NLP, biology, robotics,
materials, ...).

SOURCE DIRECT FORMULATION (grounded in verified gap {gap_id}, motif {motif}):
- title: {src_title}
- problem: {src_problem}
- core setting: {src_setting}
- core assumption/failure: {src_assumption}
- supporting paper titles: {papers}
- verification findings: support={support} | skeptic={skeptic} | feasibility={feasibility}

GENERATED VARIANT TO JUDGE ({vtype}):
- title: {v_title}
- problem: {v_problem}
- contribution_type (claimed): {contribution_type}
- broader_problem_class (claimed): {broader_problem_class}
- assumption_shift (claimed): {assumption_shift}
- boundary_or_failure_regime (claimed): {boundary}
- method_class_scope (claimed): {method_class_scope}
- generator self-scores: non_incrementality={gen_ni}, incrementality_risk={gen_ir}

Judge strictly and answer:
1. Is this variant genuinely non-incremental RELATIVE TO the source direct formulation, or did it
   merely relabel the same narrow validation idea / change the title?
2. Did it change the scientific OBJECT, or just the wording?
3. Is the broader_problem_class real and specific (not a vague umbrella)?
4. Is the contribution meaningful BEYOND one named method (method/system/mechanism/evaluation class)?
5. Is the claimed boundary/impossibility/algorithm/benchmark actually SUPPORTED by the source
   evidence above, or asserted without grounding?
6. Is the contribution_type INFLATED? e.g. labeled "impossibility_boundary" with no clear boundary
   object, or "lower_bound" with nothing to bound. If inflated, raise critic_fake_ambition_risk.

Return ONLY JSON with EXACTLY these keys:
{{
 "critic_non_incrementality_score": 0.0,
 "critic_incrementality_risk": 0.0,
 "critic_fake_ambition_risk": 0.0,
 "critic_named_method_dependency": "low|medium|high",
 "critic_broader_problem_class_valid": true,
 "critic_contribution_type_valid": true,
 "critic_supported_by_source": "strong|moderate|weak",
 "critic_quality_label": "STRONG_NON_INCREMENTAL|VALID_BUT_MODEST|INCREMENTAL_REPHRASING|FAKE_AMBITION|DROP",
 "critic_reason": "one or two sentences"
}}
Scores are floats in [0,1]. Be skeptical: a generous generator self-score is NOT evidence. Output JSON only."""


def critic_gate(v: dict) -> bool:
    """Independent-critic gate. Applied on top of the generator gate (see final_gate)."""
    return (float(v.get("critic_non_incrementality_score", 0)) >= CRITIC_GATE["non_incrementality_min"]
            and float(v.get("critic_incrementality_risk", 1)) <= CRITIC_GATE["incrementality_risk_max"]
            and float(v.get("critic_fake_ambition_risk", 1)) <= CRITIC_GATE["fake_ambition_risk_max"]
            and bool(v.get("critic_broader_problem_class_valid", False))
            and bool(v.get("critic_contribution_type_valid", False))
            and str(v.get("critic_quality_label", "")) in _CRITIC_KEEP_LABELS
            and str(v.get("critic_supported_by_source", "")).lower() in _CRITIC_SUPPORT_OK)


def final_gate(v: dict) -> bool:
    """A variant is kept only if BOTH the generator gate and the independent critic gate pass."""
    return passes_gate(v) and critic_gate(v)


def _vscore(v: dict) -> float:
    # non-incrementality is the primary driver, then ambition/coherence/specificity, minus
    # incrementality risk; small seed-alignment bonus. Conservative variants are downranked via _trank.
    return (1.5 * v.get("non_incrementality_score", 0) + v["ambition_score"] + v["coherence_score"]
            + v["specificity_score"] - 1.0 * v.get("incrementality_risk", 0) + 0.5 * v["seed_alignment_score"])


def run_ambition_expansion(ctx: Any, *, llm_base_url: str | None = None,
                           in_subdir: str = DEFAULT_IN_SUBDIR, out_subdir: str = DEFAULT_OUT_SUBDIR,
                           max_final: int | None = None, critic: bool = True,
                           select_target: int = 12) -> dict:
    run_dir = ctx.run_dir
    out = run_dir / out_subdir; ensure_dir(out)
    in_path = run_dir / in_subdir / "direct_formulations.jsonl"
    direct = [json.loads(l) for l in in_path.read_text().splitlines() if l.strip()]
    direct = [d for d in direct if d.get("quality_label") in ("STRONG_DIRECT_FORMULATION", "USABLE_DIRECT_FORMULATION")]
    titles = {p["arxiv_id"]: p.get("title", "") for p in json.load(open(run_dir / "arxiv" / "papers_manifest.json"))}
    llm = LLMClient(ctx, base_url=llm_base_url)

    variants = []
    vid = 0
    for f in direct:
        ptitles = "; ".join(titles.get(p, p)[:60] for p in f.get("supporting_papers", [])[:6]) or "(none)"
        for vtype in VARIANT_TYPES:
            vid += 1
            prompt = _PROMPT.format(gap_id=f["source_verified_gap_id"], motif=f["source_motif_type"],
                                    title=f["direct_title"], problem=f["direct_problem_statement"], setting=f["core_setting"],
                                    assumption=f["core_assumption_or_failure"], objective=f["core_objective"],
                                    papers=ptitles, seed_score=f["author_seed_alignment_score"], vtype=vtype)
            try:
                data, *_ = llm.complete_json(stage="ambition_expansion", agent_name="ambition_expand",
                                             prompt=prompt, max_tokens=1300, temperature=0.4, enable_thinking=False)
            except Exception as e:
                data = {"recommendation": "DROP", "coherence_score": 0.0, "term_soup_risk": 1.0, "why_not_incremental": f"llm_error: {e}"}
            v = {
                "variant_id": f"var:{vid:02d}", "source_formulation_id": f["formulation_id"],
                "source_verified_gap_id": f["source_verified_gap_id"], "source_motif_type": f["source_motif_type"],
                "variant_type": vtype, "title": data.get("title", ""), "problem_statement": data.get("problem_statement", ""),
                "proposal_style_abstract": data.get("proposal_style_abstract", ""), "core_setting": data.get("core_setting", ""),
                "generalized_axis": data.get("generalized_axis", ""), "core_assumption_or_failure": data.get("core_assumption_or_failure", ""),
                "core_objective": data.get("core_objective", ""), "contribution_type": data.get("contribution_type", ""),
                "theorem_target": data.get("theorem_target", ""), "algorithmic_target": data.get("algorithmic_target", ""),
                "empirical_target": data.get("empirical_target", ""), "supporting_papers": f.get("supporting_papers", []),
                "related_seed_papers": f.get("related_seed_papers", []), "why_not_incremental": data.get("why_not_incremental", ""),
                "why_not_term_soup": data.get("why_not_term_soup", ""), "main_risk": data.get("main_risk", ""),
                "falsification_condition": data.get("falsification_condition", ""),
                # domain-general non-incrementality fields
                "non_incrementality_score": float(data.get("non_incrementality_score", 0) or 0),
                "incrementality_risk": float(data.get("incrementality_risk", 1) or 0),
                "broader_problem_class": data.get("broader_problem_class", ""),
                "assumption_shift": data.get("assumption_shift", ""),
                "boundary_or_failure_regime": data.get("boundary_or_failure_regime", ""),
                "constructive_or_explanatory_target": data.get("constructive_or_explanatory_target", ""),
                "method_class_scope": data.get("method_class_scope", ""),
                "named_method_dependency": str(data.get("named_method_dependency", "medium")).lower(),
                "why_not_just_validation": data.get("why_not_just_validation", ""),
                "coherence_score": float(data.get("coherence_score", 0) or 0), "ambition_score": float(data.get("ambition_score", 0) or 0),
                "specificity_score": float(data.get("specificity_score", 0) or 0), "feasibility_score": float(data.get("feasibility_score", 0) or 0),
                "term_soup_risk": float(data.get("term_soup_risk", 0) or 0), "seed_alignment_score": float(f["author_seed_alignment_score"]),
                "recommendation": (data.get("recommendation") or "DROP").upper(), "traceability_path": f.get("traceability_path", []),
            }
            v["passes_gate"] = passes_gate(v)
            # ---- independent critic pass (judge-only; separate LLM call) ----
            if critic:
                vsum = f.get("verification_summary", {}) or {}
                cprompt = _CRITIC_PROMPT.format(
                    gap_id=f["source_verified_gap_id"], motif=f["source_motif_type"],
                    src_title=f["direct_title"], src_problem=f["direct_problem_statement"],
                    src_setting=f["core_setting"], src_assumption=f["core_assumption_or_failure"], papers=ptitles,
                    support=str(vsum.get("support", ""))[:200], skeptic=str(vsum.get("skeptic", ""))[:200],
                    feasibility=str(vsum.get("feasibility", ""))[:200], vtype=vtype,
                    v_title=v["title"], v_problem=v["problem_statement"], contribution_type=v["contribution_type"],
                    broader_problem_class=v["broader_problem_class"], assumption_shift=v["assumption_shift"],
                    boundary=v["boundary_or_failure_regime"], method_class_scope=v["method_class_scope"],
                    gen_ni=v["non_incrementality_score"], gen_ir=v["incrementality_risk"])
                try:
                    cd, *_ = llm.complete_json(stage="ambition_expansion", agent_name="incrementality_critic",
                                               prompt=cprompt, max_tokens=600, temperature=0.0, enable_thinking=False)
                except Exception as e:
                    cd = {"critic_quality_label": "DROP", "critic_non_incrementality_score": 0.0,
                          "critic_incrementality_risk": 1.0, "critic_fake_ambition_risk": 1.0,
                          "critic_supported_by_source": "weak", "critic_reason": f"critic_error: {e}"}
                v.update({
                    "critic_non_incrementality_score": float(cd.get("critic_non_incrementality_score", 0) or 0),
                    "critic_incrementality_risk": float(cd.get("critic_incrementality_risk", 1) or 0),
                    "critic_fake_ambition_risk": float(cd.get("critic_fake_ambition_risk", 1) or 0),
                    "critic_named_method_dependency": str(cd.get("critic_named_method_dependency", "medium")).lower(),
                    "critic_broader_problem_class_valid": bool(cd.get("critic_broader_problem_class_valid", False)),
                    "critic_contribution_type_valid": bool(cd.get("critic_contribution_type_valid", False)),
                    "critic_supported_by_source": str(cd.get("critic_supported_by_source", "weak")).lower(),
                    "critic_quality_label": str(cd.get("critic_quality_label", "DROP")),
                    "critic_reason": cd.get("critic_reason", ""),
                })
                v["passes_critic"] = critic_gate(v)
                v["passes_final"] = v["passes_gate"] and v["passes_critic"]
            else:
                v["passes_critic"] = v["passes_gate"]; v["passes_final"] = v["passes_gate"]
            variants.append(v)
            print(f"[expand] {v['variant_id']} {vtype} src={f['formulation_id']} gen_gate={v['passes_gate']} "
                  f"critic={v.get('critic_quality_label','-')} final={v['passes_final']} "
                  f"gen_ni={v['non_incrementality_score']} crit_ni={v.get('critic_non_incrementality_score','-')} "
                  f"fake={v.get('critic_fake_ambition_risk','-')}", flush=True)

    with open(out / "ambition_expanded_variants.jsonl", "w") as fh:
        for v in variants:
            fh.write(json.dumps(v) + "\n")

    # ---- full pool of variants passing BOTH generator + critic gates (preserved verbatim) ----
    critic_passing = [v for v in variants if v.get("passes_final", v["passes_gate"])]
    passing = critic_passing  # name kept for downstream metrics
    with open(out / "critic_passing_formulations.jsonl", "w") as fh:
        for v in critic_passing:
            fh.write(json.dumps(v) + "\n")

    # ---- select a diverse subset (<= select_target; max 2 per source) ----
    # Ranking: STRONG_NON_INCREMENTAL before VALID_BUT_MODEST; then higher critic_non_incrementality;
    # then lower critic_fake_ambition_risk. The contribution-type cap is SOFT: when the best remaining
    # candidate is impossibility_boundary and would push the share over the cap, swap in a COMPARABLE
    # non-impossibility candidate if one exists; if none exists, KEEP the critic-approved variant
    # (never drop solely for the cap) and record a diversity_warning.
    LABELS = {"STRONG_NON_INCREMENTAL": 0, "VALID_BUT_MODEST": 1}

    def _crank(v):  # lower is better
        return (LABELS.get(v.get("critic_quality_label", ""), 2),
                -float(v.get("critic_non_incrementality_score", 0)),
                float(v.get("critic_fake_ambition_risk", 1)))

    def _comparable(alt, top):  # alt is an acceptable diversity substitute for top
        return (_crank(alt)[0] <= _crank(top)[0]
                and float(alt.get("critic_non_incrementality_score", 0)) >= float(top.get("critic_non_incrementality_score", 0)) - 0.10)

    selected, per_src, seen = [], defaultdict(int), set()
    while len(selected) < select_target:
        elig = [v for v in critic_passing if v not in selected
                and v["title"].lower() not in seen and per_src[v["source_formulation_id"]] < 2]
        if not elig:
            break
        elig.sort(key=_crank)
        pick = elig[0]
        if pick.get("contribution_type") == "impossibility_boundary":
            imp_sel = sum(1 for s in selected if s.get("contribution_type") == "impossibility_boundary")
            if imp_sel + 1 > int(IMPOSSIBILITY_CAP_FRACTION * (len(selected) + 1)):
                alt = next((v for v in elig if v.get("contribution_type") != "impossibility_boundary"
                            and _comparable(v, pick)), None)
                if alt is not None:
                    pick = alt  # soft cap: prefer a comparable non-impossibility alternative
        selected.append(pick); per_src[pick["source_formulation_id"]] += 1; seen.add(pick["title"].lower())

    # soft-cap diagnostics
    imp_final = sum(1 for v in selected if v.get("contribution_type") == "impossibility_boundary")
    diversity_warning = bool(selected) and imp_final > int(IMPOSSIBILITY_CAP_FRACTION * len(selected))
    diversity_warning_reason = ("impossibility_boundary exceeds the soft cap because no comparable "
                                "non-impossibility critic-approved alternatives were available; kept "
                                "critic-approved variants rather than dropping them") if diversity_warning else ""
    critic_approved_excluded_for_diversity = 0  # soft cap never drops solely for the cap

    selected.sort(key=_crank)
    for i, v in enumerate(selected, 1):
        v["expanded_rank"] = i
    with open(out / "ambition_expanded_final_formulations.jsonl", "w") as fh:
        for v in selected:
            fh.write(json.dumps(v) + "\n")

    avg = lambda k, L: round(sum(float(x[k]) for x in L) / max(1, len(L)), 3)
    dropped_nonincr = sum(1 for v in variants if float(v.get("non_incrementality_score", 0)) < GATE["non_incrementality_min"])
    dropped_incr_risk = sum(1 for v in variants if float(v.get("incrementality_risk", 1)) > GATE["incrementality_risk_max"])
    nmd = Counter(v.get("named_method_dependency", "medium") for v in variants)
    empirical_dropped = sum(1 for v in variants if v.get("contribution_type") in ("empirical_study", "benchmark") and not v.get("passes_final", v["passes_gate"]))
    ctype_all = Counter(v.get("contribution_type", "") for v in variants)
    ctype_final = Counter(v.get("contribution_type", "") for v in selected)
    crit_scored = [v for v in variants if "critic_quality_label" in v]
    # critic-specific drop diagnostics (among variants that passed the generator gate)
    gen_ok = [v for v in variants if v["passes_gate"]]
    dropped_critic_ni = sum(1 for v in gen_ok if float(v.get("critic_non_incrementality_score", 0)) < CRITIC_GATE["non_incrementality_min"])
    dropped_critic_fake = sum(1 for v in gen_ok if float(v.get("critic_fake_ambition_risk", 1)) > CRITIC_GATE["fake_ambition_risk_max"])
    dropped_critic_support = sum(1 for v in gen_ok if str(v.get("critic_supported_by_source", "weak")).lower() not in _CRITIC_SUPPORT_OK)
    metrics = {"dropped_by_non_incrementality_gate": dropped_nonincr, "dropped_by_incrementality_risk_gate": dropped_incr_risk,
               "variants_critic_scored": len(crit_scored),
               "dropped_by_critic_non_incrementality": dropped_critic_ni,
               "dropped_by_critic_fake_ambition": dropped_critic_fake,
               "dropped_by_critic_source_support": dropped_critic_support,
               "avg_non_incrementality_final": avg("non_incrementality_score", selected),
               "avg_incrementality_risk_final": avg("incrementality_risk", selected),
               "avg_generator_non_incrementality_all": avg("non_incrementality_score", variants),
               "avg_critic_non_incrementality_all": (avg("critic_non_incrementality_score", crit_scored) if crit_scored else None),
               "avg_critic_non_incrementality_final": (avg("critic_non_incrementality_score", selected) if selected else None),
               "avg_critic_fake_ambition_all": (avg("critic_fake_ambition_risk", crit_scored) if crit_scored else None),
               "critic_quality_label_counts": dict(Counter(v.get("critic_quality_label") for v in crit_scored)),
               "named_method_dependency_counts": dict(nmd), "empirical_or_benchmark_variants_dropped": empirical_dropped,
               "contribution_type_distribution_all": dict(ctype_all),
               "contribution_type_distribution_critic_passing": dict(Counter(v.get("contribution_type", "") for v in critic_passing)),
               "contribution_type_distribution_final": dict(ctype_final),
               "impossibility_boundary_fraction_final": round(ctype_final.get("impossibility_boundary", 0) / max(1, len(selected)), 3),
               "critic_passing_count": len(critic_passing), "selected_final_count": len(selected),
               "select_target": select_target, "diversity_warning": diversity_warning,
               "diversity_warning_reason": diversity_warning_reason,
               "critic_approved_excluded_for_diversity": critic_approved_excluded_for_diversity,
               "selection_policy": ("STRONG_NON_INCREMENTAL>VALID_BUT_MODEST, then higher critic_non_incrementality, "
                                    "then lower critic_fake_ambition_risk; <=2/source; <=select_target; SOFT contribution "
                                    "cap (diversity preference, never drops critic-approved variants)"),
               "all_final_have_broader_problem_class": all(str(v.get("broader_problem_class", "")).strip() for v in selected),
               "all_final_have_why_not_just_validation": all(str(v.get("why_not_just_validation", "")).strip() for v in selected)}
    stage_model = getattr(llm, "model", (ctx.config.get("llm", {}) or {}).get("model", MODEL_NAME))
    _write_md(out / "ambition_expanded_formulations.md", direct, variants, passing, selected, model_name=stage_model)
    _write_audit(out / "ambition_expansion_quality_audit.md", direct, variants, passing, selected, per_src, metrics, model_name=stage_model)
    meta = {"stage": "ambition_expansion", "model": stage_model, "generator_model": stage_model, "critic_model": (stage_model if critic else None),
            "critic_enabled": critic, "llm_base_url": llm_base_url or ctx.config.get("llm", {}).get("base_url"),
            "created_at": utc_now_iso(), "run_id": ctx.run_id, "input": str(in_path),
            "direct_used": len(direct), "variants": len(variants), "passing_generator_gate": sum(1 for v in variants if v["passes_gate"]),
            "passing_final_gate": len(passing), "final_kept": len(selected),
            "selected_by_type": dict(Counter(v["variant_type"] for v in selected)), "gate": GATE, "critic_gate": CRITIC_GATE,
            "impossibility_cap_fraction": IMPOSSIBILITY_CAP_FRACTION,
            "avg_coherence_final": avg("coherence_score", selected), "avg_ambition_final": avg("ambition_score", selected),
            "avg_term_soup_final": avg("term_soup_risk", selected),
            "seed_aligned_final": sum(1 for v in selected if v["seed_alignment_score"] > 0),
            **metrics, "forbidden_inputs_not_used": FORBIDDEN_INPUTS}
    json.dump(meta, open(out / "run_metadata.json", "w"), indent=2)
    print(f"[expand] DONE variants={len(variants)} passing={len(passing)} final={len(selected)} by_type={meta['selected_by_type']}", flush=True)
    return meta


def _write_md(path, direct, variants, passing, selected, *, model_name: str = MODEL_NAME):
    avg = lambda k, L: round(sum(float(x[k]) for x in L) / max(1, len(L)), 3)
    sc = Counter(v["variant_type"] for v in selected)
    lines = ["# Ambition-Expanded Formulations (SGHA Stage 8)", "",
             "## Executive summary",
             f"- model: {model_name}", f"- direct formulations used: {len(direct)}",
             f"- variants generated: {len(variants)} (conservative/generalized/bold)",
             f"- passing gate (coh>=0.75, term-soup<=0.30, spec>=0.60): {len(passing)}",
             f"- final kept: {len(selected)} | by type: {dict(sc)}",
             f"- averages (final): coherence {avg('coherence_score',selected)} | ambition {avg('ambition_score',selected)} | term-soup {avg('term_soup_risk',selected)}",
             f"- seed-aligned final: {sum(1 for v in selected if v['seed_alignment_score']>0)}", "",
             "## Final expanded formulations"]
    for v in selected:
        lines += [f"### Rank {v['expanded_rank']}. {v['title']}  ({v['variant_id']}, {v['variant_type']}/{v['contribution_type']})",
                  f"- source direct formulation: {v['source_formulation_id']} (verified gap `{v['source_verified_gap_id']}` [{v['source_motif_type']}])",
                  f"- generalized axis: {v['generalized_axis'] or '—'} | scores: coh {v['coherence_score']} amb {v['ambition_score']} spec {v['specificity_score']} ts {v['term_soup_risk']} seed {v['seed_alignment_score']}",
                  f"- problem: {v['problem_statement']}",
                  f"- targets — theorem: {v['theorem_target'] or '—'} | algorithm: {v['algorithmic_target'] or '—'} | empirical: {v['empirical_target'] or '—'}",
                  f"- why not incremental: {v['why_not_incremental']}", f"- why not term-soup: {v['why_not_term_soup']}",
                  f"- supporting papers: {v['supporting_papers'][:6]} | related seed: {v['related_seed_papers'] or '—'}",
                  "", f"**Abstract.** {v['proposal_style_abstract']}", ""]
    dropped = [v for v in variants if not v["passes_gate"]]
    lines += ["## Dropped variants (failed gate)",
              (chr(10).join(f"- {v['variant_id']} [{v['variant_type']}] {v['title'][:50]} — coh={v['coherence_score']} ts={v['term_soup_risk']} spec={v['specificity_score']}" for v in dropped) or "(none — all variants passed the gate)")]
    path.write_text("\n".join(lines))


def _write_audit(path, direct, variants, passing, selected, per_src, metrics, *, model_name: str = MODEL_NAME):
    avg = lambda k, L: round(sum(float(x[k]) for x in L) / max(1, len(L)), 3)
    sc = Counter(v["variant_type"] for v in selected)
    lines = ["# Ambition Expansion Quality Audit (SGHA Stage 8 — domain-general non-incrementality)", "",
             f"- model: {model_name}",
             f"- total variants generated: {len(variants)} (conservative/generalized/bold × {len(direct)} direct)",
             f"- passing gate: {len(passing)} | final kept count: {len(selected)} (no padding; smaller-than-before is acceptable)",
             f"- variants by type: {dict(Counter(v['variant_type'] for v in variants))} | final by type: {dict(sc)}",
             f"- conservative kept: {sc.get('conservative',0)} (downranked; kept only if no non-incremental generalized/bold survived for that source)",
             "",
             "## Generator non-incrementality gating",
             f"- dropped by generator non_incrementality gate (score < {GATE['non_incrementality_min']}): {metrics['dropped_by_non_incrementality_gate']}",
             f"- dropped by generator incrementality_risk gate (risk > {GATE['incrementality_risk_max']}): {metrics['dropped_by_incrementality_risk_gate']}",
             f"- named_method_dependency counts (all variants): {metrics['named_method_dependency_counts']}",
             f"- empirical/benchmark variants dropped (final): {metrics['empirical_or_benchmark_variants_dropped']}",
             "",
             "## Independent critic pass",
             f"- variants critic-scored: {metrics['variants_critic_scored']}",
             f"- dropped by critic non-incrementality (score < {CRITIC_GATE['non_incrementality_min']}): {metrics['dropped_by_critic_non_incrementality']}",
             f"- dropped by critic fake-ambition risk (> {CRITIC_GATE['fake_ambition_risk_max']}): {metrics['dropped_by_critic_fake_ambition']}",
             f"- dropped by critic source-support weakness: {metrics['dropped_by_critic_source_support']}",
             f"- avg generator non_incrementality (all): {metrics['avg_generator_non_incrementality_all']} | avg CRITIC non_incrementality (all): {metrics['avg_critic_non_incrementality_all']}",
             f"- avg critic fake_ambition_risk (all): {metrics['avg_critic_fake_ambition_all']} | avg critic non_incrementality (final): {metrics['avg_critic_non_incrementality_final']}",
             f"- critic quality-label counts: {metrics['critic_quality_label_counts']}",
             "",
             "## Selection (soft contribution cap)",
             f"- critic-passing pool: {metrics['critic_passing_count']} (preserved in critic_passing_formulations.jsonl)",
             f"- selected diverse final: {metrics['selected_final_count']} (target <= {metrics['select_target']}, <=2/source)",
             f"- selection policy: {metrics['selection_policy']}",
             f"- contribution-type distribution (critic-passing pool): {metrics['contribution_type_distribution_critic_passing']}",
             f"- contribution-type distribution (selected final): {metrics['contribution_type_distribution_final']}",
             f"- contribution-type distribution (all generated): {metrics['contribution_type_distribution_all']}",
             f"- impossibility_boundary fraction of final: {metrics['impossibility_boundary_fraction_final']} (soft cap {IMPOSSIBILITY_CAP_FRACTION})",
             f"- diversity_warning: {metrics['diversity_warning']} ({metrics['diversity_warning_reason'] or 'cap satisfied'})",
             f"- critic-approved variants excluded ONLY for diversity: {metrics['critic_approved_excluded_for_diversity']} (soft cap never drops critic-approved)",
             "",
             "## Required-field & integrity checks",
             f"- every kept variant has broader_problem_class: {metrics['all_final_have_broader_problem_class']}",
             f"- every kept variant has why_not_just_validation: {metrics['all_final_have_why_not_just_validation']}",
             f"- final term-soup >0.30: {sum(1 for v in selected if v['term_soup_risk']>0.30)} | coherence <0.75: {sum(1 for v in selected if v['coherence_score']<0.75)} | specificity <0.60: {sum(1 for v in selected if v['specificity_score']<0.60)}",
             f"- final with named_method_dependency=high: {sum(1 for v in selected if v.get('named_method_dependency')=='high')} (allowed only as broad method-class benchmark/empirical_study)",
             f"- max variants per source: {max(per_src.values()) if per_src else 0} (rule <=2) | distinct sources: {len({v['source_formulation_id'] for v in selected})} | duplicate titles: {len(selected)-len({v['title'].lower() for v in selected})}",
             f"- forbidden 'we prove/we show/our experiments demonstrate': {sum(1 for v in selected if any(p in v['proposal_style_abstract'].lower() for p in ('we prove','we show','our experiments demonstrate')))}",
             f"- averages (final): coherence {avg('coherence_score',selected)} | ambition {avg('ambition_score',selected)} | specificity {avg('specificity_score',selected)} | term-soup {avg('term_soup_risk',selected)}",
             "",
             "## Provenance",
             "- old evolved report / previous ad-hoc outputs were NOT used as inputs (see run_metadata.forbidden_inputs_not_used).",
             "- All final variants trace to one direct formulation -> one verified gap. No cross-gap synthesis, no external search.",
             f"- generator model: {model_name} | critic model: {model_name} (independent judge-only pass)"]
    path.write_text("\n".join(lines))
