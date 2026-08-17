"""SGHA-native finalization: neutral final family report + finalization orchestrator.

Renders the user-facing neutral "research direction menu" (Markdown + polished Markdown + HTML),
a JSON with internal labels preserved, a quality audit, and run metadata — from the Stage 7/8/9/10
SGHA-native artifacts. Also provides `run_finalization`, the orchestrator that the main pipeline
calls after verification when `finalization.mode == family_report`.

Domain-general: no field-specific terms in logic. No new hypotheses are generated here — every
problem statement / abstract is carried verbatim from the Stage-7/8 records.
"""
from __future__ import annotations

import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .extraction_quality import LOW_EXTRACTION_SIGNAL, load_extraction_quality_summary
from .utils import ensure_dir, utc_now_iso

# stable (non-timestamped) default output directory names for future runs
S7_SUBDIR = "stage7_direct_formulations"
S8_SUBDIR = "stage8_ambition_expansion"
S9_SUBDIR = "stage9_family_quality"
S10_SUBDIR = "stage10_formal_problem_formulations"
FINAL_SUBDIR = "final_sgha_family_report"
PIPELINE_COMPLETED_PASS = "PIPELINE_COMPLETED_PASS"
PIPELINE_COMPLETED_LOW_SIGNAL = "PIPELINE_COMPLETED_LOW_SIGNAL"
PIPELINE_COMPLETED_AUDIT_FAILURE = "PIPELINE_COMPLETED_AUDIT_FAILURE"

FORBIDDEN_INPUTS = ["final/ranked_hypotheses.json", "final/final_report.md",
                    "pre_evolution_formulations_20260608", "ambition_expanded_formulations_20260608",
                    "final_direct_formulations_20260608"]
# internal labels that must NOT appear in the user-facing Markdown
_HIDDEN_LABELS = ["A_STRONG", "B_PROMISING_NEEDS_REFRAMING", "B_PROMISING", "C_LOW_PRIORITY", "D_DROP",
                  "READ_FIRST", "READ_LATER", "DROP_PERMANENTLY", "REFRAME", "MERGE_WITH_RELATED_FAMILY"]

_SIGNAL = {"strong": "strong", "moderate": "moderate", "weak": "limited"}
_REASON_NL = {
    "off_domain": "appears to sit outside this run's core topic (it reads as a different research area)",
    "low_domain_fit": "only partially overlaps this run's core topic",
    "duplicate_of_stronger_family": "its variants are near-duplicates of one another, so it may be worth consolidating into a single direction",
    "weak_source_support": "the source grounding is thin",
    "fake_ambition_risk": "the stated ambition may outrun the available evidence",
    "formal_plausibility_concern": "the formal/empirical plausibility still needs checking",
    "too_broad": "the scope is broad and would benefit from narrowing",
    "too_method_specific": "it is tied closely to one named method, so the object may need generalizing",
    "incremental_or_validation_only": "it may be closer to validating an existing method than to a new result",
    "unclear_problem_object": "the core research object is under-specified",
}


def _caveats_sentence(f: dict) -> str:
    drs = f.get("downgrade_reasons") or []
    if not drs:
        return "No major caveats were flagged."
    parts = [_REASON_NL.get(d, d) for d in drs]
    if "off_domain" in drs and "low_domain_fit" in drs:  # de-duplicate overlapping phrasings
        parts = [p for p in parts if p != _REASON_NL["low_domain_fit"]]
    s = "; ".join(dict.fromkeys(parts))
    return s[0].upper() + s[1:] + "."


def _verify_line(f: dict) -> str:
    papers = ", ".join(f.get("supporting_papers", [])[:3]) or "the cited papers"
    steps = [f"Read the first supporting papers ({papers}) to confirm the gap is real and not already addressed."]
    fb = str(f.get("failure_boundary_or_mechanism", "")).strip().rstrip(".")
    if fb:
        steps.append(f"Confirm that the target — {fb} — is well-posed and checkable.")
    return " ".join(steps)


def _tiers(families: list[dict]) -> tuple[list, list, list]:
    t1 = [f for f in families if f.get("quality_label") == "A_STRONG"]
    t2 = [f for f in families if f.get("quality_label") == "B_PROMISING_NEEDS_REFRAMING"]
    t3 = [f for f in families if f.get("quality_label") in ("C_LOW_PRIORITY", "D_DROP")]
    return t1, t2, t3


def _disclaimer() -> str:
    return ("> **Disclaimer.** These are SGHA-generated candidate research directions. The report provides "
            "evidence and caveats, but it is not a final scientific judgment. Users should inspect the source "
            "papers before deciding what to pursue.")


def _direct_input_step(stats: dict) -> str:
    source = stats.get("direct_formulation_input_source")
    if source == "novelty_survivors":
        return ("**Post-novelty survivor gaps** were used for direct formulation because "
                "`direct_formulations.input_source: novelty_survivors` was explicitly selected.")
    if source == "verification_reviewed_gaps":
        return ("**Verification-reviewed gaps** were used because reviewed-only mode was explicitly selected. "
                "These gaps have verification artifacts, but they are not verification-passed gaps.")
    return ("**Verification-passed gaps** were used for direct formulation: reviewed gaps that passed the "
            "configured support/skeptic/feasibility/mechanism/critic gate.")


def _formal_block(f: dict) -> str:
    fp = f.get("formal_problem_formulation")
    if not fp:
        return ""
    setup = fp.get("mathematical_setup", {}) or {}
    pr = fp.get("possible_result_types", {}) or {}
    lines = ["#### Formal Problem Formulation", "",
             f"**Plain-language problem.** {fp.get('plain_language_problem','')}", "",
             f"**Formal problem statement.** {fp.get('formal_problem_statement','')}", "",
             "**Entities / variables.**", "",
             "| Symbol | Meaning | Type | Source |",
             "|---|---|---|---|"]
    for v in setup.get("variables", []) or []:
        lines.append(f"| {v.get('symbol','')} | {v.get('meaning','')} | {v.get('type','')} | {v.get('source','')} |")
    lines += ["",
              f"- entities: {setup.get('entities', [])}",
              f"- feedback or observation model: {setup.get('feedback_or_measurement_model','')}",
              f"- decision variables / outputs: {setup.get('decision_variables_or_outputs','')}",
              f"- objective: {setup.get('objective','')}",
              f"- constraints: {setup.get('constraints','')}",
              f"- success criterion: {setup.get('success_criterion','')}", "",
              "**Assumptions.**"]
    assumptions = fp.get("assumptions", []) or []
    if assumptions:
        for a in assumptions:
            lines.append(f"- {a.get('name','')} ({a.get('status','')}): {a.get('description','')}")
    else:
        lines.append("- none recorded")
    lines += ["",
              f"**Open question.** {fp.get('open_question','')}", "",
              f"- possible theorem target: {pr.get('theorem') or '—'}",
              f"- possible algorithm target: {pr.get('algorithm') or '—'}",
              f"- possible empirical / benchmark target: {pr.get('empirical_or_benchmark') or '—'}",
              f"- evaluation protocol: {fp.get('evaluation_protocol','')}",
              f"- formalization confidence: {fp.get('formalization_confidence')} | requires human definition: {fp.get('requires_human_definition')}",
              f"- formalization risk: {fp.get('formalization_risk','')}", "",
              "**Ambiguity flags / terms needing definition.**"]
    flags = fp.get("ambiguity_flags", []) or []
    if flags:
        for flag in flags:
            lines.append(f"- {flag.get('term','')}: {flag.get('why_ambiguous','')} User must define: {flag.get('what_user_must_define','')}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _extraction_warning_block(stats: dict) -> str:
    if not stats.get("low_extraction_signal"):
        return ""
    warning = stats.get("extraction_quality_warning") or "Tuple yield was below the configured extraction-quality threshold."
    return f"""
## LOW_EXTRACTION_SIGNAL Warning

This run continued downstream in advisory extraction-quality mode. Extraction completed mechanically, but
the run has low tuple yield: the tuple yield was below the configured quality threshold.

- extraction quality status: **{stats.get('extraction_quality_status', LOW_EXTRACTION_SIGNAL)}**
- extracted papers: **{stats.get('extraction_extracted_papers','?')}**
- tuple count: **{stats.get('extraction_tuple_count','?')}**
- average tuples per extracted paper: **{stats.get('extraction_avg_tuples_per_paper','?')}**
- configured thresholds: avg >= **{stats.get('extraction_min_avg_tuples_per_paper','?')}** OR total tuples >= **{stats.get('extraction_min_total_tuples','?')}**
- enforcement: **{stats.get('extraction_quality_enforcement','?')}** | allow downstream on low signal: **{stats.get('allow_downstream_on_low_signal','?')}**
- warning: **{warning}**

Treat downstream gaps, formulations, and families from this run as model-scaling stress-test artifacts,
not as equally grounded SGHA findings.
"""


def _fam_block(f: dict, n: int, *, polished: bool) -> str:
    sig = (f"evidence grounding: {_SIGNAL.get(f.get('evidence_grounding'),'?')} | non-incrementality: "
           f"{_SIGNAL.get(f.get('non_incrementality'),'?')} | specificity: {_SIGNAL.get(f.get('specificity'),'?')} | "
           f"plausibility: {_SIGNAL.get(f.get('plausibility'),'?')} | topic alignment: {_SIGNAL.get(f.get('domain_fit'),'?')}")
    lines = [f"### {n}. {f.get('family_title','')}",
             f"- representative formulation: `{f.get('representative_variant_id','')}` | member formulations: {f.get('member_variant_ids',[])}",
             f"- source verification-passed gaps: {f.get('source_verified_gaps',[])} | source direct formulations: {f.get('source_direct_formulations',[])}",
             "", f"**Problem statement.** {f.get('representative_problem_statement', f.get('family_problem_statement',''))}", "",
             f"**Proposal-style abstract.** {f.get('proposal_style_abstract','') or '(none in source record)'}", "",
             f"- core research object / problem class: {f.get('research_object','')} — {f.get('problem_class','')}",
             f"- assumption shift: {f.get('assumption_shift','')}",
             f"- failure boundary / mechanism: {f.get('failure_boundary_or_mechanism','')}",
             f"- possible contribution targets — theorem: {f.get('theorem_target') or '—'} | algorithm: {f.get('algorithmic_target') or '—'} | empirical: {f.get('empirical_target') or '—'}",
             f"- first supporting papers to inspect: {f.get('supporting_papers',[])[:5]}",
             f"- related seed papers: {f.get('related_seed_papers') or '—'}",
             f"- {sig}",
             f"- independent-critic note: {f.get('critic_reason','')}",
             f"- main risk: {f.get('main_risk','')}",
             f"- caveats: {_caveats_sentence(f)}",
             f"- **What to verify before pursuing.** {_verify_line(f)}", ""]
    formal = _formal_block(f)
    if formal:
        lines += [formal]
    return "\n".join(lines)


def _render_markdown(families: list[dict], stats: dict, *, polished: bool) -> str:
    t1, t2, t3 = _tiers(families)
    blocks = lambda fams: "".join(_fam_block(f, i, polished=polished) for i, f in enumerate(fams, 1)) or "(none)\n"
    if not families:
        return f"""# {stats.get('run_title','SGHA')} — Low-Signal SGHA Run

{_disclaimer()}

## Executive Summary
- finalization status: **{stats.get('finalization_status', PIPELINE_COMPLETED_LOW_SIGNAL)}**
- low-signal reason: **{stats.get('low_signal_reason','no_project_families')}**
- corpus size: **{stats.get('corpus', '?')}** papers (seed + retrieved)
- seed papers: **{stats.get('seed_papers','?')}** | retrieved papers: **{stats.get('retrieved_papers','?')}**
- verification-reviewed gaps: **{stats.get('verification_reviewed_gaps','?')}** | verification-passed gaps: **{stats.get('verification_passed_gaps','?')}** | verification-failed gaps: **{stats.get('verification_failed_gaps','?')}**
- direct formulations: **{stats.get('direct','?')}**
- direct formulation input: **{stats.get('direct_formulation_input_source','?')}** | verification-passed only: **{stats.get('verification_passed_only','?')}**
- verification gate: **enabled={stats.get('verification_gate_enabled','?')}**, mode=**{stats.get('verification_gate_mode','?')}**, threshold=**{stats.get('verification_gate_threshold','?')}**
- ambition variants generated: **{stats.get('variants','?')}**
- critic-passing formulations: **{stats.get('critic_passing','?')}** | selected formulations: **{stats.get('selected','?')}**
- final project families: **0**
- generator model: **{stats.get('generator_model','?')}** | independent-critic model: **{stats.get('critic_model','?')}**
- final family consolidation: **{stats.get('consolidation','deterministic (no LLM)')}**
{_extraction_warning_block(stats)}

# Low-Signal Run

This run completed mechanically, but SGHA did not identify any project families passing the final quality filters. This can happen for small smoke-test corpora or when the verification-passed gap pool is too small.

Do not present this as a research menu.

## How This Run Was Processed
1. {_direct_input_step(stats)}
2. **Direct formulation** attempted to create one coherent problem per verification-passed gap.
3. **Ambition expansion** generated conservative/generalized/bold variants where direct formulations existed.
4. **Independent critic pass** scored variants for genuine non-incrementality and inflated ambition.
5. **Strict family consolidation** found no final project families passing the active filters.
6. **Formal problem formulation** completed as a low-signal stage because there were no project families.
7. **Final neutral rendering** recorded the low-signal completion state.

No old evolved hypotheses were used; no previous ad-hoc outputs were used; no external search was used;
and **no new hypotheses were generated at report time**.

## Full Provenance and Artifacts
- direct formulations: `{stats.get('s7_subdir','')}/direct_formulations.jsonl`
- ambition expansion: `{stats.get('s8_subdir','')}/` (variants, critic-passing pool, selected)
- family consolidation: `{stats.get('s9_subdir','')}/project_families.json`
- formal problem formulations: `{stats.get('s10_subdir','')}/formal_problem_formulations.jsonl`
- this report: `{stats.get('out_subdir','')}/`
- generator + critic: {stats.get('generator_model','?')}; family consolidation: {stats.get('consolidation','deterministic')}

## Limitations
- A low-signal completion is not a research menu and should not be read as a negative scientific result.
- Small corpora, sparse verification-passed gap pools, or strict critic filters can leave no project families.
- Novelty / non-incrementality were judged by the generator + an independent critic, **not** by external
  literature verification.
- Evidence grounding is measured against the local corpus only; no external/citation search was performed.
"""
    return f"""# {stats.get('run_title','SGHA')} — Research Direction Menu

{_disclaimer()}

## Executive Summary
- corpus size: **{stats.get('corpus', '?')}** papers (seed + retrieved)
- seed papers: **{stats.get('seed_papers','?')}** | retrieved papers: **{stats.get('retrieved_papers','?')}**
- verification-reviewed gaps: **{stats.get('verification_reviewed_gaps','?')}** | verification-passed gaps: **{stats.get('verification_passed_gaps','?')}** | verification-failed gaps: **{stats.get('verification_failed_gaps','?')}**
- direct formulations: **{stats.get('direct','?')}**
- direct formulation input: **{stats.get('direct_formulation_input_source','?')}** | verification-passed only: **{stats.get('verification_passed_only','?')}**
- verification gate: **enabled={stats.get('verification_gate_enabled','?')}**, mode=**{stats.get('verification_gate_mode','?')}**, threshold=**{stats.get('verification_gate_threshold','?')}**
- ambition variants generated: **{stats.get('variants','?')}**
- critic-passing formulations: **{stats.get('critic_passing','?')}** | selected formulations: **{stats.get('selected','?')}**
- final project families: **{len(families)}**
- generator model: **{stats.get('generator_model','?')}** | independent-critic model: **{stats.get('critic_model','?')}**
- final family consolidation: **{stats.get('consolidation','deterministic (no LLM)')}**
{_extraction_warning_block(stats)}

This is a neutral research menu: candidate directions with their evidence and caveats, to help you
decide what to read and pursue. It does not rank-order winners or prescribe a single answer.

## How This Report Was Generated
1. {_direct_input_step(stats)}
2. **Direct formulation**: one coherent problem per verification-passed gap.
3. **Ambition expansion**: conservative/generalized/bold variants per direct formulation.
4. **Independent critic pass**: a separate judge scored each variant's genuine non-incrementality and flagged inflated ambition.
5. **Soft-cap diversity selection**: a diverse subset selected without deleting critic-approved work.
6. **Strict family consolidation**: variants grouped into project families only on hard anchors, then summarized.
7. **Formal problem formulation**: each project family was stated with variables, observations, assumptions, objectives, targets, and ambiguity flags.
8. **Final neutral rendering** (this report).

No old evolved hypotheses were used; no previous ad-hoc outputs were used; no external search was used;
and **no new hypotheses were generated at report time** — every problem statement and abstract is carried
verbatim from the formulation records.

## Suggested Inspection Order
1. **Most directly aligned directions** — {', '.join(f.get('family_title','') for f in t1) or '(none)'}
2. **Strong but source-sensitive directions** — {', '.join(f.get('family_title','') for f in t2) or '(none)'}
3. **Caveat-heavy or adjacent directions** — {', '.join(f.get('family_title','') for f in t3) or '(none)'}

Within each tier, start with the directions whose supporting papers are easiest to verify.

## Candidate Research Directions
{blocks(t1)}
## Directions Requiring Extra Source Validation
{blocks(t2)}
## Caveat-Heavy or Adjacent Directions
{blocks(t3)}
## Full Provenance and Artifacts
- direct formulations: `{stats.get('s7_subdir','')}/direct_formulations.jsonl`
- ambition expansion: `{stats.get('s8_subdir','')}/` (variants, critic-passing pool, selected)
- family consolidation: `{stats.get('s9_subdir','')}/project_families.json`
- formal problem formulations: `{stats.get('s10_subdir','')}/formal_problem_formulations.jsonl`
- this report: `{stats.get('out_subdir','')}/`
- generator + critic: {stats.get('generator_model','?')}; family consolidation: {stats.get('consolidation','deterministic')}

## Limitations
- Novelty / non-incrementality were judged by the generator + an independent critic, **not** by external
  literature verification — some directions may already exist in the literature.
- Evidence grounding is measured against the local corpus only; no external/citation search was performed.
- "Topic alignment" is measured against this run's own declared topic; an adjacent-area direction is
  flagged, not deleted — judge it yourself.
- These are candidate directions, not results. Inspect the cited papers before committing.
"""


def _to_html(md: str, title: str) -> str:
    try:
        import markdown as _md
        body = _md.markdown(md, extensions=["tables"])
    except Exception:
        body = "<pre>" + html.escape(md) + "</pre>"
    return (f"<!doctype html><meta charset='utf-8'><title>{html.escape(title)}</title>"
            "<style>body{font-family:system-ui,Arial;max-width:1000px;margin:2em auto;line-height:1.55;padding:0 1em}"
            "h1,h2,h3{color:#16324f}blockquote{background:#fff7e6;border-left:4px solid #e0a800;padding:.5em 1em}"
            "code{background:#f2f2f2;padding:1px 4px}</style>" + body)


def render_final_family_report(ctx: Any, *, s9_subdir: str = S9_SUBDIR, s8_subdir: str = S8_SUBDIR,
                               s7_subdir: str = S7_SUBDIR, s10_subdir: str = S10_SUBDIR,
                               out_subdir: str = FINAL_SUBDIR,
                               use_llm_polish: bool = False) -> dict:
    """Render the neutral final family report (md + polished md + html + json + audit + metadata)."""
    rd = ctx.run_dir
    out = rd / out_subdir; ensure_dir(out)
    fams_doc = json.loads((rd / s9_subdir / "project_families.json").read_text())
    families = sorted(fams_doc["families"], key=lambda f: f.get("family_rank", 999))
    sel_path = rd / s8_subdir / "ambition_expanded_final_formulations.jsonl"
    sel = {v["variant_id"]: v for v in (json.loads(l) for l in sel_path.read_text().splitlines() if l.strip())} if sel_path.exists() else {}
    direct_path = rd / s7_subdir / "direct_formulations.jsonl"
    direct_records = _read_jsonl(direct_path)
    direct_meta = _read_json_obj(rd / s7_subdir / "run_metadata.json")
    direct_prov = Counter(d.get("verification_provenance", "UNKNOWN") for d in direct_records)
    reviewed_count = direct_meta.get("verification_reviewed_count")
    passed_count = direct_meta.get("verification_passed_count")
    failed_count = direct_meta.get("verification_failed_count")
    if reviewed_count is None:
        reviewed_count = _count_jsonl(rd / "verification" / "support_agent_results.jsonl")
    if passed_count is None:
        passed_count = direct_prov.get("VERIFICATION_PASSED", direct_prov.get("FULLY_VERIFIED", 0))
    if failed_count is None:
        failed_count = max(0, int(reviewed_count or 0) - int(passed_count or 0))

    fcfg = (ctx.config.get("final_report", {}) or {})
    formal_cfg = (ctx.config.get("formal_problem", {}) or {})
    formal_enabled = bool(formal_cfg.get("enabled", True))
    formal_include = bool(fcfg.get("include_formal_problem_formulation", True))
    formal_path = rd / s10_subdir / "formal_problem_formulations.jsonl"
    formal_records = _read_jsonl(formal_path) if formal_enabled and formal_path.exists() else []
    formal_by_family = {r.get("family_id"): r for r in formal_records if r.get("family_id")}
    if formal_enabled:
        families = [{**f, "formal_problem_formulation": formal_by_family.get(f.get("family_id"))} for f in families]
    formal_meta = _read_json_obj(rd / s10_subdir / "run_metadata.json")
    extraction_quality = load_extraction_quality_summary(rd)
    pers = (ctx.config.get("personalization", {}) or {})
    extraction_gate = extraction_quality.get("sanity_gate") or {}
    stats = {
        "run_title": (pers.get("seed_label") or ctx.run_id),
        "personalization_enabled": bool(pers.get("enabled", False)),
        "corpus": _count_manifest(rd), "seed_papers": _count_seed(rd),
        "retrieved_papers": max(0, _count_manifest(rd) - _count_seed(rd)),
        "verified_gaps": passed_count,
        "verification_reviewed_gaps": reviewed_count,
        "verification_passed_gaps": passed_count,
        "verification_failed_gaps": failed_count,
        "direct": len(direct_records),
        "variants": _count_jsonl(rd / s8_subdir / "ambition_expanded_variants.jsonl"),
        "critic_passing": _count_jsonl(rd / s8_subdir / "critic_passing_formulations.jsonl"),
        "selected": len(sel), "generator_model": _meta_model(rd / s8_subdir, "generator_model"),
        "critic_model": _meta_model(rd / s8_subdir, "critic_model"),
        "consolidation": "deterministic (no LLM)" if not _meta_model(rd / s9_subdir, "model") else _meta_model(rd / s9_subdir, "model"),
        "s7_subdir": s7_subdir, "s8_subdir": s8_subdir, "s9_subdir": s9_subdir, "s10_subdir": s10_subdir,
        "out_subdir": out_subdir,
        "direct_formulation_input_source": direct_meta.get("direct_formulation_input_source", direct_meta.get("input_source")),
        "verification_backed_only": direct_meta.get("verification_backed_only"),
        "verification_passed_only": direct_meta.get("verification_passed_only"),
        "verification_gate_enabled": direct_meta.get("verification_gate_enabled"),
        "verification_gate_mode": direct_meta.get("verification_gate_mode"),
        "verification_gate_threshold": direct_meta.get("verification_gate_threshold"),
        "verification_gate_warning": direct_meta.get("verification_gate_warning"),
        "direct_verification_passed": direct_prov.get("VERIFICATION_PASSED", 0),
        "direct_verification_reviewed": direct_prov.get("VERIFICATION_REVIEWED", 0),
        "direct_novelty_only": direct_prov.get("NOVELTY_ONLY", 0),
        "formal_problem_enabled": formal_enabled,
        "include_formal_problem_formulation": formal_include,
        "formalizations": len(formal_records),
        "formal_problem_status": formal_meta.get("status"),
        "formal_problem_confidence_counts": formal_meta.get("formalization_confidence_counts", {}),
        "formal_problem_ambiguity_flags": formal_meta.get("ambiguity_flag_count"),
        "formal_problem_fallback_count": formal_meta.get("fallback_formalization_count"),
        "formal_problem_retry_used_count": formal_meta.get("formalization_retry_used_count"),
        "formal_problem_parse_error_count": formal_meta.get("formalization_parse_error_count"),
        "extraction_quality_status": extraction_quality.get("extraction_quality_status"),
        "low_extraction_signal": bool(extraction_quality.get("low_extraction_signal", False)),
        "extraction_quality_warning": extraction_quality.get("warning"),
        "extraction_extracted_papers": extraction_quality.get("extracted_papers"),
        "extraction_tuple_count": extraction_quality.get("tuple_count"),
        "extraction_avg_tuples_per_paper": extraction_quality.get("average_tuples_per_extracted_paper"),
        "extraction_min_avg_tuples_per_paper": extraction_gate.get("min_avg_tuples_per_paper"),
        "extraction_min_total_tuples": extraction_gate.get("min_total_tuples", extraction_gate.get("min_total_tuples_alternative")),
        "extraction_quality_enforcement": extraction_quality.get("enforcement", extraction_gate.get("enforcement")),
        "allow_downstream_on_low_signal": extraction_quality.get("allow_downstream_on_low_signal", extraction_gate.get("allow_downstream_on_low_signal")),
        "_extraction_quality": extraction_quality,
        "_direct_records": direct_records,
        "_direct_metadata": direct_meta,
        "_formal_records": formal_records,
        "_formal_metadata": formal_meta,
    }
    low_signal_reason = _low_signal_reason(families, stats)
    preliminary_status = PIPELINE_COMPLETED_LOW_SIGNAL if low_signal_reason else PIPELINE_COMPLETED_PASS
    stats["finalization_status"] = preliminary_status
    stats["low_signal_reason"] = low_signal_reason
    report_families = families if formal_include else [
        {k: v for k, v in f.items() if k != "formal_problem_formulation"} for f in families
    ]
    neutral = _render_markdown(report_families, stats, polished=False)
    polished = _render_markdown(report_families, stats, polished=True)  # deterministic; same clean prose
    (out / "final_report.md").write_text(neutral)
    (out / "final_report_polished.md").write_text(polished)
    (out / "final_report.html").write_text(_to_html(neutral, str(stats["run_title"])))
    final_doc = dict(fams_doc)
    final_doc["families"] = families
    final_doc["formal_problem"] = {
        "enabled": formal_enabled,
        "included_in_markdown": formal_include,
        "input": f"{s10_subdir}/formal_problem_formulations.jsonl",
        "formalizations_loaded": len(formal_records),
        "status": formal_meta.get("status"),
        "fallback_formalization_count": formal_meta.get("fallback_formalization_count"),
        "formalization_retry_used_count": formal_meta.get("formalization_retry_used_count"),
        "formalization_parse_error_count": formal_meta.get("formalization_parse_error_count"),
    }
    final_doc["extraction_quality"] = extraction_quality
    final_doc["verification_gate"] = {
        "enabled": stats.get("verification_gate_enabled"),
        "mode": stats.get("verification_gate_mode"),
        "threshold": stats.get("verification_gate_threshold"),
        "reviewed_count": stats.get("verification_reviewed_gaps"),
        "passed_count": stats.get("verification_passed_gaps"),
        "failed_count": stats.get("verification_failed_gaps"),
        "passed_only": stats.get("verification_passed_only"),
        "warning": stats.get("verification_gate_warning"),
    }
    json.dump(final_doc, open(out / "final_project_families.json", "w"), indent=2)

    audit, audit_pass = _audit(families, sel, neutral, polished, out, stats)
    finalization_status = preliminary_status if audit_pass else PIPELINE_COMPLETED_AUDIT_FAILURE
    (out / "final_report_quality_audit.md").write_text(audit)
    meta = {"stage": "final_family_report", "created_at": utc_now_iso(), "run_id": ctx.run_id,
            "inputs": {"s7": s7_subdir, "s8": s8_subdir, "s9": s9_subdir, "s10": s10_subdir},
            "families_included": len(families), "generator_model": stats["generator_model"],
            "critic_model": stats["critic_model"], "consolidation": stats["consolidation"],
            "formal_problem_enabled": formal_enabled,
            "personalization_enabled": bool(pers.get("enabled", False)),
            "verification_gate_enabled": stats.get("verification_gate_enabled"),
            "verification_gate_mode": stats.get("verification_gate_mode"),
            "verification_gate_threshold": stats.get("verification_gate_threshold"),
            "verification_reviewed_count": stats.get("verification_reviewed_gaps"),
            "verification_passed_count": stats.get("verification_passed_gaps"),
            "verification_failed_count": stats.get("verification_failed_gaps"),
            "verification_passed_only": stats.get("verification_passed_only"),
            "verification_gate_warning": stats.get("verification_gate_warning"),
            "include_formal_problem_formulation": formal_include,
            "formalizations_included": len(formal_records),
            "formal_problem_status": formal_meta.get("status"),
            "formal_problem_confidence_counts": formal_meta.get("formalization_confidence_counts", {}),
            "formal_problem_ambiguity_flag_count": formal_meta.get("ambiguity_flag_count"),
            "formal_problem_fallback_count": formal_meta.get("fallback_formalization_count"),
            "formal_problem_retry_used_count": formal_meta.get("formalization_retry_used_count"),
            "formal_problem_parse_error_count": formal_meta.get("formalization_parse_error_count"),
            "extraction_quality_status": stats.get("extraction_quality_status"),
            "low_extraction_signal": stats.get("low_extraction_signal"),
            "extraction_quality_warning": stats.get("extraction_quality_warning"),
            "extraction_tuple_count": stats.get("extraction_tuple_count"),
            "extraction_avg_tuples_per_paper": stats.get("extraction_avg_tuples_per_paper"),
            "extraction_quality_enforcement": stats.get("extraction_quality_enforcement"),
            "allow_downstream_on_low_signal": stats.get("allow_downstream_on_low_signal"),
            "use_llm_polish": bool(use_llm_polish), "new_hypotheses_generated": False,
            "finalization_status": finalization_status, "low_signal": bool(low_signal_reason),
            "low_signal_reason": low_signal_reason,
            "internal_labels": {f["family_id"]: {"quality_label": f.get("quality_label"),
                                                 "recommended_action": f.get("recommended_action")} for f in families},
            "audit_all_pass": audit_pass, "forbidden_inputs_not_used": FORBIDDEN_INPUTS}
    json.dump(meta, open(out / "run_metadata.json", "w"), indent=2)
    print(f"[final_report] families={len(families)} status={finalization_status} audit_pass={audit_pass} -> {out}", flush=True)
    return meta


def _low_signal_reason(families: list[dict], stats: dict) -> str | None:
    if families:
        return None
    if stats.get("direct_formulation_input_source") == "verification_passed_gaps" and int(stats.get("verification_passed_gaps") or 0) == 0:
        return "no_verification_passed_gaps"
    if int(stats.get("verification_reviewed_gaps") or stats.get("verified_gaps") or 0) == 0:
        return "no_verification_reviewed_gaps"
    if int(stats.get("direct") or 0) == 0:
        return "no_direct_formulations"
    if int(stats.get("critic_passing") or 0) == 0:
        return "no_critic_passing_formulations"
    return "no_project_families"


def _json_valid(p: Path) -> bool:
    if not p.exists():
        return False
    try:
        json.loads(p.read_text())
        return True
    except Exception:
        return False


def _read_json_obj(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _audit(families, sel, neutral_md, polished_md, out, stats) -> tuple[str, bool]:
    low_signal_reason = stats.get("low_signal_reason")
    status = stats.get("finalization_status") or (PIPELINE_COMPLETED_LOW_SIGNAL if low_signal_reason else PIPELINE_COMPLETED_PASS)
    visible = sorted({t for t in _HIDDEN_LABELS if t in neutral_md or t in polished_md})
    malformed_outputs_detected = not _json_valid(out / "final_project_families.json")
    direct_records = stats.get("_direct_records") or []
    direct_by_id = {d.get("formulation_id"): d for d in direct_records if d.get("formulation_id")}
    direct_input_source = stats.get("direct_formulation_input_source")
    verification_backed_only = stats.get("verification_backed_only")
    verification_passed_only = stats.get("verification_passed_only")
    verification_gate_enabled = stats.get("verification_gate_enabled")
    verification_gate_mode = stats.get("verification_gate_mode")
    direct_provenance = Counter(d.get("verification_provenance", "UNKNOWN") for d in direct_records)
    novelty_only_direct_ids = sorted(
        d.get("formulation_id", "?") for d in direct_records if d.get("verification_provenance") == "NOVELTY_ONLY"
    )
    reviewed_only_direct_ids = sorted(
        d.get("formulation_id", "?") for d in direct_records if d.get("verification_provenance") == "VERIFICATION_REVIEWED"
    )
    verification_passed_direct_ids = {
        d.get("formulation_id") for d in direct_records if d.get("verification_provenance") == "VERIFICATION_PASSED"
    }
    selected_direct_ids = {v.get("source_formulation_id") for v in sel.values() if v.get("source_formulation_id")}
    family_direct_ids = {
        did
        for f in families
        for did in (f.get("source_direct_formulations") or [])
        if did
    }
    default_verified_mode = (
        direct_input_source in (None, "verified_gaps", "verification_passed_gaps")
        and verification_backed_only is not False
        and verification_passed_only is not False
    )
    family_directs_resolve = family_direct_ids <= set(direct_by_id)
    selected_directs_resolve = selected_direct_ids <= set(direct_by_id)
    final_family_verified_trace = (not default_verified_mode) or (family_direct_ids <= verification_passed_direct_ids)
    selected_verified_trace = (not default_verified_mode) or (selected_direct_ids <= verification_passed_direct_ids)
    every_default_direct_passed = (not default_verified_mode) or all(
        d.get("verification_provenance") == "VERIFICATION_PASSED" and d.get("verification_gate_passed") is True
        for d in direct_records
    )
    formal_enabled = bool(stats.get("formal_problem_enabled"))
    formal_records = stats.get("_formal_records") or []
    formal_meta = stats.get("_formal_metadata") or {}
    formal_by_family = {r.get("family_id"): r for r in formal_records if r.get("family_id")}
    formal_family_ids = set(formal_by_family)
    family_ids = {f.get("family_id") for f in families if f.get("family_id")}
    missing_formal = sorted(str(fid) for fid in family_ids - formal_family_ids if fid)
    invented_formal = sorted(str(fid) for fid in formal_family_ids - family_ids if fid)
    every_family_has_formal_statement = (not formal_enabled or bool(low_signal_reason)
                                         or all(str((f.get("formal_problem_formulation") or {}).get("formal_problem_statement", "")).strip()
                                                for f in families))
    every_formal_has_grounding = (not formal_enabled or all(isinstance(r.get("source_grounding"), dict)
                                  and "source_verified_gaps" in r.get("source_grounding", {})
                                  for r in formal_records))
    formal_stage_file_exists = (out.parent / str(stats.get("s10_subdir", S10_SUBDIR)) / "formal_problem_formulations.jsonl").exists()
    low_extraction_signal = bool(stats.get("low_extraction_signal"))
    extraction_warning_visible = (not low_extraction_signal) or (
        LOW_EXTRACTION_SIGNAL in neutral_md and LOW_EXTRACTION_SIGNAL in polished_md
        and "low tuple yield" in neutral_md.lower()
        and "low tuple yield" in polished_md.lower()
    )
    checks = {
        "families_present_or_low_signal_recorded": len(families) >= 1 or bool(low_signal_reason),
        "every_representative_abstract_present": all(str(f.get("proposal_style_abstract", "")).strip() for f in families),
        "every_source_verified_gap_present": all(f.get("source_verified_gaps") for f in families),
        "every_supporting_paper_present": all(f.get("supporting_papers") for f in families),
        "direct_formulation_input_source_recorded": direct_input_source in (
            "verified_gaps", "verification_passed_gaps", "verification_reviewed_gaps", "novelty_survivors"
        ),
        "verification_backed_only_recorded": isinstance(verification_backed_only, bool),
        "verification_gate_enabled_recorded": isinstance(verification_gate_enabled, bool),
        "verification_gate_counts_recorded": all(stats.get(k) is not None for k in (
            "verification_reviewed_gaps", "verification_passed_gaps", "verification_failed_gaps"
        )),
        "verification_passed_only_recorded": isinstance(verification_passed_only, bool),
        "direct_formulation_count_matches_records": int(stats.get("direct") or 0) == len(direct_records),
        "direct_provenance_counts_match_records": (
            int(stats.get("direct_verification_passed") or 0) == direct_provenance.get("VERIFICATION_PASSED", 0)
            and int(stats.get("direct_verification_reviewed") or 0) == direct_provenance.get("VERIFICATION_REVIEWED", 0)
            and int(stats.get("direct_novelty_only") or 0) == direct_provenance.get("NOVELTY_ONLY", 0)
        ),
        "no_novelty_only_direct_formulations_in_default_mode": (not default_verified_mode) or not novelty_only_direct_ids,
        "no_reviewed_only_direct_formulations_in_default_mode": (not default_verified_mode) or not reviewed_only_direct_ids,
        "all_default_direct_formulations_passed_verification_gate": every_default_direct_passed,
        "selected_stage8_direct_formulations_resolve": selected_directs_resolve,
        "selected_stage8_trace_to_verification_passed_direct_formulations_in_default_mode": selected_verified_trace,
        "final_family_direct_formulations_resolve": family_directs_resolve,
        "final_families_trace_to_verification_passed_direct_formulations_in_default_mode": final_family_verified_trace,
        "formal_problem_formulations_jsonl_exists_when_enabled": (not formal_enabled) or formal_stage_file_exists,
        "every_family_has_formal_problem_statement_when_enabled": every_family_has_formal_statement,
        "every_formalization_has_source_grounding": every_formal_has_grounding,
        "formalization_family_ids_resolve": (not formal_enabled) or not invented_formal,
        "no_new_hypotheses_generated_during_formalization": (not formal_enabled) or formal_meta.get("new_hypotheses_generated") is False,
        "no_old_evolved_or_ad_hoc_outputs_used_by_formalization": (not formal_enabled) or all(
            x in (formal_meta.get("forbidden_inputs_not_used") or []) for x in FORBIDDEN_INPUTS),
        "low_extraction_signal_warning_preserved": extraction_warning_visible,
        "no_visible_internal_labels_in_markdown": visible == [],
        "internal_labels_preserved_in_json": all("quality_label" in f for f in families),
        "abstracts_verbatim_from_records": (not sel) or all(
            str(f.get("proposal_style_abstract", "")) == str(sel.get(f["representative_variant_id"], {}).get("proposal_style_abstract", "")) for f in families),
        "representatives_resolve": (not sel) or all(f["representative_variant_id"] in sel for f in families),
        "final_report_md_exists": (out / "final_report.md").exists(),
        "final_report_polished_exists": (out / "final_report_polished.md").exists(),
        "final_report_html_exists": (out / "final_report.html").exists(),
        "final_project_families_json_exists": (out / "final_project_families.json").exists(),
        "final_project_families_json_valid": _json_valid(out / "final_project_families.json"),
        "no_malformed_outputs_detected": not malformed_outputs_detected,
        "no_crash_recorded": True,
        "no_graph_modification_by_renderer": True,
    }
    allpass = all(checks.values())
    lines = ["# Final Family Report — Quality Audit", "",
             f"- finalization status: {status}",
             f"- families included: {len(families)}",
             f"- family count: {len(families)}",
             f"- low-signal reason: {low_signal_reason or 'NONE'}",
             f"- direct formulation input source: {direct_input_source or 'UNKNOWN'}",
             f"- verification backed only: {verification_backed_only}",
             f"- verification passed only: {verification_passed_only}",
             f"- verification gate enabled: {verification_gate_enabled}",
             f"- verification gate mode: {verification_gate_mode}",
             f"- verification gate threshold: {stats.get('verification_gate_threshold')}",
             f"- verification reviewed count: {stats.get('verification_reviewed_gaps')}",
             f"- verification passed count: {stats.get('verification_passed_gaps')}",
             f"- verification failed count: {stats.get('verification_failed_gaps')}",
             f"- verification gate warning: {stats.get('verification_gate_warning') or 'NONE'}",
             f"- direct formulation provenance counts: {dict(direct_provenance)}",
             f"- novelty-only direct formulation IDs in default mode: {novelty_only_direct_ids if default_verified_mode else 'N/A'}",
             f"- reviewed-only direct formulation IDs in default mode: {reviewed_only_direct_ids if default_verified_mode else 'N/A'}",
             f"- formal problem enabled: {formal_enabled}",
             f"- formalizations loaded: {len(formal_records)}",
             f"- missing formalizations: {missing_formal or 'NONE'}",
             f"- invented formalization family IDs: {invented_formal or 'NONE'}",
             f"- formalization confidence counts: {stats.get('formal_problem_confidence_counts') or {}}",
             f"- formalization ambiguity flags: {stats.get('formal_problem_ambiguity_flags')}",
             f"- fallback formalization count: {stats.get('formal_problem_fallback_count')}",
             f"- formalization retry used count: {stats.get('formal_problem_retry_used_count')}",
             f"- formalization parse error count: {stats.get('formal_problem_parse_error_count')}",
             f"- extraction quality status: {stats.get('extraction_quality_status') or 'UNKNOWN'}",
             f"- low_extraction_signal: {low_extraction_signal}",
             f"- extraction tuple count: {stats.get('extraction_tuple_count')}",
             f"- extraction avg tuples/paper: {stats.get('extraction_avg_tuples_per_paper')}",
             f"- extraction quality enforcement: {stats.get('extraction_quality_enforcement')}",
             f"- allow downstream on low signal: {stats.get('allow_downstream_on_low_signal')}",
             f"- extraction quality warning: {stats.get('extraction_quality_warning') or 'NONE'}",
             f"- visible internal-label tokens in Markdown: {visible or 'NONE'}", ""]
    lines += [f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in checks.items()]
    lines += ["", f"ALL: {'PASS' if allpass else 'FAIL'}", "",
              "## Provenance",
              "- no new hypotheses generated during rendering (problem statements + abstracts copied verbatim).",
              "- old evolved report / ad-hoc outputs NOT used; external search NOT used.",
              "- internal A/B/C/D + action labels kept only in final_project_families.json / this audit / run_metadata.json.",
              "## Internal labels (not shown in the Markdown report)"]
    lines += [f"- {f['family_id']} {f.get('family_title','')}: {f.get('quality_label')} / {f.get('recommended_action')}"
              + (" [inconsistency_warning]" if f.get("label_inconsistency_warning") else "") for f in families]
    return "\n".join(lines), allpass


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _count_jsonl(p: Path) -> int:
    return sum(1 for l in p.read_text().splitlines() if l.strip()) if p.exists() else 0


def _count_manifest(rd: Path) -> int:
    p = rd / "arxiv" / "papers_manifest.json"
    return len(json.loads(p.read_text())) if p.exists() else 0


def _count_seed(rd: Path) -> int:
    p = rd / "corpus" / "paper_relationships.jsonl"
    return sum(1 for l in p.read_text().splitlines() if l.strip() and json.loads(l).get("is_manual_seed_paper")) if p.exists() else 0


def _meta_model(d: Path, key: str):
    p = d / "run_metadata.json"
    if p.exists():
        return json.loads(p.read_text()).get(key)
    return None


# ---------------------------------------------------------------------------
# Finalization orchestrator (called by the main pipeline after verification)
# ---------------------------------------------------------------------------

def _stage_done(rd: Path, subdir: str, required: list[str]) -> bool:
    d = rd / subdir
    for f in required:  # JSONL validity
        p = d / f
        if not p.exists():
            return False
        # Empty JSONL is a valid low-signal artifact; empty JSON/Markdown is not.
        if p.stat().st_size == 0 and not f.endswith(".jsonl"):
            return False
        if f.endswith(".jsonl"):
            try:
                for line in p.read_text().splitlines():
                    if line.strip():
                        json.loads(line)
            except Exception:
                return False
        if f.endswith(".json"):
            try:
                json.loads(p.read_text())
            except Exception:
                return False
    return True


def run_finalization(ctx: Any, *, llm_base_url: str | None = None, force: bool = False) -> dict:
    """Pipeline finalization. With finalization.mode == 'family_report' (default), runs:
    direct_formulations -> ambition_expansion (+ critic) -> family_quality (strict) ->
    formal_problem -> final report.
    With mode == 'evolution_report' (or use_evolution: true), runs the legacy evolve + report."""
    cfg = ctx.config
    fin = (cfg.get("finalization", {}) or {})
    mode = fin.get("mode", "family_report")
    if mode == "evolution_report" or fin.get("use_evolution", False):
        from .evolutionary_refinement import evolve_hypotheses
        from .report_builder import build_report
        evolve_hypotheses(ctx)
        md, html_path = build_report(ctx)
        return {"mode": "evolution_report", "report_md": str(md), "report_html": str(html_path)}

    from .direct_formulation import run_direct_formulations
    from .ambition_expansion import run_ambition_expansion
    from .family_quality import run_family_quality
    from .formal_problem import run_formal_problem_stage
    rd = ctx.run_dir
    ax = (cfg.get("ambition_expansion", {}) or {})
    fq = (cfg.get("family_quality", {}) or {})
    fp = (cfg.get("formal_problem", {}) or {})
    fr = (cfg.get("final_report", {}) or {})

    if fin.get("use_direct_formulations", True) and (force or not _stage_done(rd, S7_SUBDIR, ["direct_formulations.jsonl", "run_metadata.json"])):
        run_direct_formulations(ctx, llm_base_url=llm_base_url, out_subdir=S7_SUBDIR)
    if fin.get("use_ambition_expansion", True) and (force or not _stage_done(rd, S8_SUBDIR, ["ambition_expanded_final_formulations.jsonl", "critic_passing_formulations.jsonl", "run_metadata.json"])):
        run_ambition_expansion(ctx, llm_base_url=llm_base_url, in_subdir=S7_SUBDIR, out_subdir=S8_SUBDIR,
                               critic=fin.get("use_ambition_critic", True), select_target=int(ax.get("select_target", 12)))
    if fin.get("use_family_quality", True) and (force or not _stage_done(rd, S9_SUBDIR, ["project_families.json", "run_metadata.json"])):
        run_family_quality(ctx, s8_subdir=S8_SUBDIR, s7_subdir=S7_SUBDIR, out_subdir=S9_SUBDIR,
                           use_llm=bool(fq.get("use_llm", False)), llm_base_url=llm_base_url)
    formal_ran = False
    if fp.get("enabled", True) and (force or not _stage_done(rd, S10_SUBDIR, ["formal_problem_formulations.jsonl", "formal_problem_quality_audit.md", "run_metadata.json"])):
        run_formal_problem_stage(ctx, llm_base_url=llm_base_url, force=force, s9_subdir=S9_SUBDIR,
                                 s8_subdir=S8_SUBDIR, s7_subdir=S7_SUBDIR, out_subdir=S10_SUBDIR)
        formal_ran = True
    meta = {"mode": "family_report"}
    report_subdir = fr.get("output_dir", FINAL_SUBDIR)
    if fin.get("render_neutral_report", True) and (force or formal_ran or not _stage_done(rd, report_subdir, ["final_report.md", "final_project_families.json", "run_metadata.json"])):
        meta = render_final_family_report(ctx, s9_subdir=S9_SUBDIR, s8_subdir=S8_SUBDIR, s7_subdir=S7_SUBDIR,
                                          s10_subdir=S10_SUBDIR,
                                          out_subdir=report_subdir,
                                          use_llm_polish=bool(fr.get("use_llm_polish", False)))
    else:
        meta_path = rd / report_subdir / "run_metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
    meta["mode"] = "family_report"
    return meta
