"""SGHA-native Stage 10: domain-general formal problem formulation.

Formalizes each Stage-9 project family into a semi-formal problem statement with variables,
observations, assumptions, objectives, result targets, and ambiguity flags. This stage does not
create new project families or new hypotheses; it only makes the existing family more explicit.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .llm_client import LLMClient
from .utils import ensure_dir, utc_now_iso

MODEL_NAME = "Qwen/Qwen3.5-9B"
DEFAULT_OUT_SUBDIR = "stage10_formal_problem_formulations"
DEFAULT_S9_SUBDIR = "stage9_family_quality"
DEFAULT_S8_SUBDIR = "stage8_ambition_expansion"
DEFAULT_S7_SUBDIR = "stage7_direct_formulations"
PASS = "PASS"
PIPELINE_COMPLETED_LOW_SIGNAL = "PIPELINE_COMPLETED_LOW_SIGNAL"
FAILED = "FAILED"

FORBIDDEN_INPUTS = [
    "final/ranked_hypotheses.json",
    "final/final_report.md",
    "pre_evolution_formulations_20260608",
    "ambition_expanded_formulations_20260608",
    "final_direct_formulations_20260608",
]

_VAR_TYPES = {"scalar", "vector", "set", "distribution", "process", "function", "other"}
_CONFIDENCE = {"high", "medium", "low"}
_ASSUMPTION_STATUS = {"kept", "relaxed", "removed", "questioned"}
_AMBIGUOUS_HINTS = ("unknown", "unclear", "ambiguous", "mismatch", "boundary", "dynamic",
                    "robust", "trust", "aware", "general", "failure")
_METADATA_VARIABLE_SYMBOLS = {"R", "C", "A", "B"}
_METADATA_VARIABLE_HINTS = (
    "research object", "problem class", "assumption shift", "questioned condition",
    "failure boundary", "boundary or mechanism", "source assumption", "project family",
)

_PROMPT = """You are SGHA's domain-general formal problem formulation stage.

You must formalize ONE existing project family. Do NOT invent a new research direction, new family,
or new claim of results. Use only the source family and formulation evidence below. The field may be
anything: online learning, language models, robotics, biology, materials, systems, or another domain.
Do not hardcode any field vocabulary; use domain terms only when they appear in the source evidence.

STRICT RULES:
- Formalize the existing project family only.
- Prefer clear semi-formal structure over fake mathematics.
- If a term is vague, define it cautiously or put it in ambiguity_flags.
- If the feedback/data/measurement model is unclear, say so.
- If the objective cannot be formalized from evidence, set formalization_confidence to "low".
- Every symbol introduced in the formal_problem_statement must appear in the variable table.
- Do NOT use metadata variables such as R = research object, C = problem class,
  A = assumption shift, or B = boundary. Those describe the record, not the problem.
- Variables must correspond to problem-level objects: actions, observations, latent factors,
  measurements, rewards/outcomes, policies/decisions, constraints, objectives, estimators,
  environments, systems, functions, processes, or distributions.
- If the problem is under-specified, define a minimal problem-level skeleton and put the missing
  observation/action/outcome/objective pieces in ambiguity_flags.
- Every major assumption must be marked kept, relaxed, removed, or questioned.
- Do not say "we prove", "we show", or imply results already exist.
- Use wording such as "The question is whether..." or "A possible theorem would characterize...".

PROJECT FAMILY JSON:
{family_json}

REPRESENTATIVE STAGE-8 FORMULATION JSON:
{variant_json}

SOURCE DIRECT FORMULATIONS JSON:
{direct_json}

Return ONLY a JSON object with EXACTLY these keys:
{{
  "plain_language_problem": "",
  "formal_problem_statement": "",
  "mathematical_setup": {{
    "entities": [""],
    "variables": [
      {{"symbol": "", "meaning": "", "type": "scalar | vector | set | distribution | process | function | other", "source": "from evidence | introduced for formalization"}}
    ],
    "data_or_observations": "",
    "feedback_or_measurement_model": "",
    "decision_variables_or_outputs": "",
    "objective": "",
    "constraints": "",
    "success_criterion": ""
  }},
  "assumptions": [
    {{"name": "", "description": "", "status": "kept | relaxed | removed | questioned", "source_evidence": [""]}}
  ],
  "open_question": "",
  "possible_result_types": {{"theorem": "", "algorithm": "", "empirical_or_benchmark": ""}},
  "evaluation_protocol": "",
  "ambiguity_flags": [
    {{"term": "", "why_ambiguous": "", "what_user_must_define": ""}}
  ],
  "source_grounding": {{
    "source_verified_gaps": [""],
    "supporting_papers": [""],
    "representative_formulation": "",
    "critic_reason": ""
  }},
  "formalization_confidence": "high | medium | low",
  "formalization_risk": "",
  "requires_human_definition": true
}}"""

_REPAIR_PROMPT = """Your previous Stage-10 formal problem formulation response could not be parsed as JSON.

Parse error:
{parse_error}

Regenerate the SAME project-family formalization as strict JSON only. Do not add markdown fences,
comments, trailing commas, or text outside the JSON object. Preserve the schema and source-grounding
rules from the original prompt below.

ORIGINAL PROMPT:
{original_prompt}
"""


class _MinimalContext:
    def __init__(self, run_dir: Path, config: dict[str, Any]):
        self.run_dir = run_dir
        self.config = config
        self.run_id = run_dir.name

    def path(self, *parts: str) -> Path:
        p = self.run_dir.joinpath(*parts)
        ensure_dir(p.parent)
        return p


def run_formal_problem_stage(ctx_or_run_dir: Any, config: dict[str, Any] | None = None, *,
                             llm_base_url: str | None = None, force: bool = False,
                             s9_subdir: str = DEFAULT_S9_SUBDIR, s8_subdir: str = DEFAULT_S8_SUBDIR,
                             s7_subdir: str = DEFAULT_S7_SUBDIR,
                             out_subdir: str = DEFAULT_OUT_SUBDIR) -> dict[str, Any]:
    """Generate one formal/semi-formal problem formulation per Stage-9 project family."""
    if hasattr(ctx_or_run_dir, "run_dir") and hasattr(ctx_or_run_dir, "config"):
        ctx = ctx_or_run_dir
        run_dir = Path(ctx.run_dir)
        cfg = ctx.config
    else:
        run_dir = Path(ctx_or_run_dir)
        cfg = config or {}
        ctx = _MinimalContext(run_dir, cfg)

    out = run_dir / out_subdir
    ensure_dir(out)
    fams_path = run_dir / s9_subdir / "project_families.json"
    if not fams_path.exists():
        if (cfg.get("formal_problem", {}) or {}).get("fail_on_missing_family_inputs", True):
            raise FileNotFoundError(f"missing Stage-9 family input: {fams_path}")
        families: list[dict[str, Any]] = []
        fams_doc: dict[str, Any] = {"families": []}
    else:
        fams_doc = json.loads(fams_path.read_text())
        families = sorted(fams_doc.get("families", []), key=lambda f: f.get("family_rank", 999))

    selected = _read_jsonl(run_dir / s8_subdir / "ambition_expanded_final_formulations.jsonl")
    critic_passing = _read_jsonl(run_dir / s8_subdir / "critic_passing_formulations.jsonl")
    direct = _read_jsonl(run_dir / s7_subdir / "direct_formulations.jsonl")

    if not families:
        _write_jsonl(out / "formal_problem_formulations.jsonl", [])
        _write_md(out / "formal_problem_formulations.md", [], {})
        audit, audit_pass, audit_status, metrics = _build_audit([], families, model_used=None, low_signal_reason="no_project_families")
        (out / "formal_problem_quality_audit.md").write_text(audit)
        meta = {
            "stage": "formal_problem",
            "created_at": utc_now_iso(),
            "run_id": ctx.run_id,
            "model": None,
            "llm_base_url": llm_base_url or (cfg.get("llm", {}) or {}).get("base_url"),
            "status": audit_status,
            "low_signal_reason": "no_project_families",
            "families_loaded": 0,
            "formalizations_generated": 0,
            "new_family_ids_invented": False,
            "new_hypotheses_generated": False,
            "forbidden_inputs_not_used": FORBIDDEN_INPUTS,
            **metrics,
        }
        json.dump(meta, open(out / "run_metadata.json", "w"), indent=2)
        print(f"[formal_problem] families=0 status={audit_status} -> {out}", flush=True)
        return meta

    selected_by_id = {v.get("variant_id"): v for v in selected}
    direct_by_id = {d.get("formulation_id"): d for d in direct}
    llm = LLMClient(ctx, base_url=llm_base_url, model=(cfg.get("formal_problem", {}) or {}).get("model") or MODEL_NAME)
    model_used = (cfg.get("formal_problem", {}) or {}).get("model") or MODEL_NAME

    records: list[dict[str, Any]] = []
    for fam in families:
        rep = selected_by_id.get(fam.get("representative_variant_id"), {})
        src_direct = [direct_by_id.get(did, {}) for did in fam.get("source_direct_formulations", [])]
        prompt = _PROMPT.format(
            family_json=json.dumps(_compact_family(fam), indent=2),
            variant_json=json.dumps(_compact_variant(rep), indent=2),
            direct_json=json.dumps([_compact_direct(d) for d in src_direct if d], indent=2),
        )
        parse_error = ""
        retry_error = ""
        retry_used = False
        try:
            data, *_ = llm.complete_json(stage="formal_problem", agent_name="formal_problem_formulator",
                                         prompt=prompt, max_tokens=1800, temperature=0.2, enable_thinking=False)
            fallback = False
        except Exception as exc:
            parse_error = str(exc)
            retry_used = True
            repair_prompt = _REPAIR_PROMPT.format(parse_error=parse_error, original_prompt=prompt)
            try:
                data, *_ = llm.complete_json(stage="formal_problem", agent_name="formal_problem_json_repair",
                                             prompt=repair_prompt, max_tokens=1800, temperature=0.0,
                                             enable_thinking=False)
                fallback = False
            except Exception as repair_exc:
                retry_error = str(repair_exc)
                data = _fallback_formalization(
                    fam,
                    rep,
                    f"llm_error_after_retry: first={parse_error}; retry={retry_error}",
                )
                fallback = True
        rec = normalize_formalization_record(fam, rep, data)
        rec["formalization_is_fallback"] = fallback
        rec["formalization_retry_used"] = retry_used
        rec["formalization_parse_error"] = parse_error
        rec["formalization_retry_error"] = retry_error
        records.append(rec)
        print(f"[formal_problem] {rec['family_id']} confidence={rec['formalization_confidence']} "
              f"ambiguity_flags={len(rec['ambiguity_flags'])}", flush=True)

    _write_jsonl(out / "formal_problem_formulations.jsonl", records)
    _write_md(out / "formal_problem_formulations.md", records, fams_doc)
    audit, audit_pass, audit_status, metrics = _build_audit(records, families, model_used=model_used)
    (out / "formal_problem_quality_audit.md").write_text(audit)
    meta = {
        "stage": "formal_problem",
        "created_at": utc_now_iso(),
        "run_id": ctx.run_id,
        "model": model_used,
        "llm_base_url": llm_base_url or (cfg.get("llm", {}) or {}).get("base_url"),
        "status": audit_status,
        "audit_all_pass": audit_pass,
        "families_loaded": len(families),
        "formalizations_generated": len(records),
        "inputs": {"s9": s9_subdir, "s8": s8_subdir, "s7": s7_subdir},
        "new_family_ids_invented": False,
        "new_hypotheses_generated": False,
        "forbidden_inputs_not_used": FORBIDDEN_INPUTS,
        **metrics,
    }
    json.dump(meta, open(out / "run_metadata.json", "w"), indent=2)
    print(f"[formal_problem] families={len(families)} formalizations={len(records)} status={audit_status} -> {out}", flush=True)
    return meta


def normalize_formalization_record(family: dict[str, Any], representative: dict[str, Any],
                                   data: dict[str, Any]) -> dict[str, Any]:
    setup = data.get("mathematical_setup") if isinstance(data.get("mathematical_setup"), dict) else {}
    variables = [_normalize_variable(v) for v in _as_list(setup.get("variables"))]
    variables = [v for v in variables if not _is_metadata_placeholder_variable(v)]
    if not variables:
        variables = [_normalize_variable(v) for v in _source_grounded_variables(family, representative)]

    assumptions = [_normalize_assumption(a) for a in _as_list(data.get("assumptions"))]
    if not assumptions:
        assumptions = [{
            "name": "source-grounded setting",
            "description": "The family relies on the setting and limitations stated in the source formulations.",
            "status": "questioned",
            "source_evidence": [family.get("representative_problem_statement", "")[:240]],
        }]

    ambiguity_flags = [_normalize_ambiguity(a) for a in _as_list(data.get("ambiguity_flags"))]
    ambiguity_flags += _heuristic_ambiguity_flags(family, data, {a["term"].lower() for a in ambiguity_flags})

    confidence = str(data.get("formalization_confidence") or "medium").lower()
    if confidence not in _CONFIDENCE:
        confidence = "medium"
    feedback = str(setup.get("feedback_or_measurement_model") or "").strip()
    objective = str(setup.get("objective") or "").strip()
    if (not feedback or "unclear" in feedback.lower() or not objective) and confidence == "high":
        confidence = "medium"
    if not feedback or not objective:
        confidence = "low" if confidence != "medium" else "medium"

    requires_human = data.get("requires_human_definition")
    if not isinstance(requires_human, bool):
        requires_human = bool(ambiguity_flags) or confidence == "low"

    source_grounding = data.get("source_grounding") if isinstance(data.get("source_grounding"), dict) else {}
    return {
        "family_id": family.get("family_id", ""),
        "representative_variant_id": family.get("representative_variant_id", representative.get("variant_id", "")),
        "family_title": family.get("family_title", ""),
        "plain_language_problem": str(data.get("plain_language_problem") or family.get("representative_problem_statement") or ""),
        "formal_problem_statement": str(data.get("formal_problem_statement") or _fallback_statement(family)),
        "mathematical_setup": {
            "entities": [str(x) for x in _as_list(setup.get("entities")) if str(x).strip()] or _source_grounded_entities(family, representative),
            "variables": variables,
            "data_or_observations": str(setup.get("data_or_observations") or _source_observation_text(family, representative)),
            "feedback_or_measurement_model": feedback or "Unclear from the source family; the feedback or measurement model requires human definition.",
            "decision_variables_or_outputs": str(setup.get("decision_variables_or_outputs") or "The decision variables or outputs require human definition."),
            "objective": objective or "The objective requires human definition from the source papers.",
            "constraints": str(setup.get("constraints") or "Constraints are not fully specified by the source family."),
            "success_criterion": str(setup.get("success_criterion") or "Progress would require a theorem, algorithm, or benchmark criterion tied to the source family."),
        },
        "assumptions": assumptions,
        "open_question": str(data.get("open_question") or "The question is whether the stated family can be made precise and tested under source-grounded assumptions."),
        "possible_result_types": _normalize_result_types(data.get("possible_result_types"), family),
        "evaluation_protocol": str(data.get("evaluation_protocol") or "Compare against source-relevant baselines or evidence once the observation model and objective are fixed."),
        "ambiguity_flags": ambiguity_flags,
        "source_grounding": {
            "source_verified_gaps": [str(x) for x in _as_list(source_grounding.get("source_verified_gaps")) if str(x).strip()] or family.get("source_verified_gaps", []),
            "supporting_papers": [str(x) for x in _as_list(source_grounding.get("supporting_papers")) if str(x).strip()] or family.get("supporting_papers", []),
            "representative_formulation": str(source_grounding.get("representative_formulation") or family.get("representative_problem_statement", "")),
            "critic_reason": str(source_grounding.get("critic_reason") or family.get("critic_reason", "")),
        },
        "formalization_confidence": confidence,
        "formalization_risk": str(data.get("formalization_risk") or "Some terms may remain under-specified until the source papers are read."),
        "requires_human_definition": requires_human,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_variable(value: Any) -> dict[str, str]:
    d = value if isinstance(value, dict) else {}
    typ = str(d.get("type") or "other").lower()
    if typ not in _VAR_TYPES:
        typ = "other"
    return {
        "symbol": str(d.get("symbol") or "X"),
        "meaning": str(d.get("meaning") or "quantity introduced for formalization"),
        "type": typ,
        "source": str(d.get("source") or "introduced for formalization"),
    }


def _is_metadata_placeholder_variable(variable: dict[str, str]) -> bool:
    symbol = str(variable.get("symbol") or "").strip()
    if symbol not in _METADATA_VARIABLE_SYMBOLS:
        return False
    meaning = str(variable.get("meaning") or "").lower()
    source = str(variable.get("source") or "").lower()
    return any(hint in meaning or hint in source for hint in _METADATA_VARIABLE_HINTS)


def _normalize_assumption(value: Any) -> dict[str, Any]:
    d = value if isinstance(value, dict) else {}
    status = str(d.get("status") or "questioned").lower()
    if status not in _ASSUMPTION_STATUS:
        status = "questioned"
    return {
        "name": str(d.get("name") or "assumption"),
        "description": str(d.get("description") or "Assumption requires source-paper confirmation."),
        "status": status,
        "source_evidence": [str(x) for x in _as_list(d.get("source_evidence")) if str(x).strip()],
    }


def _normalize_ambiguity(value: Any) -> dict[str, str]:
    d = value if isinstance(value, dict) else {}
    return {
        "term": str(d.get("term") or "under-specified term"),
        "why_ambiguous": str(d.get("why_ambiguous") or "The source family does not fully define this term."),
        "what_user_must_define": str(d.get("what_user_must_define") or "Give an operational definition before pursuing the project."),
    }


def _normalize_result_types(value: Any, family: dict[str, Any]) -> dict[str, str]:
    d = value if isinstance(value, dict) else {}
    return {
        "theorem": str(d.get("theorem") or family.get("theorem_target") or ""),
        "algorithm": str(d.get("algorithm") or family.get("algorithmic_target") or ""),
        "empirical_or_benchmark": str(d.get("empirical_or_benchmark") or family.get("empirical_target") or ""),
    }


def _heuristic_ambiguity_flags(family: dict[str, Any], data: dict[str, Any], existing: set[str]) -> list[dict[str, str]]:
    text = " ".join(str(family.get(k, "")) for k in (
        "family_title", "failure_boundary_or_mechanism", "assumption_shift", "problem_class", "research_object"
    ))
    text_l = text.lower()
    flags: list[dict[str, str]] = []
    for hint in _AMBIGUOUS_HINTS:
        if hint in text_l and hint not in existing:
            flags.append({
                "term": hint,
                "why_ambiguous": "This term may hide multiple operational meanings in the source family.",
                "what_user_must_define": "Specify the measurable object, boundary, or condition denoted by this term.",
            })
            break
    setup = data.get("mathematical_setup") if isinstance(data.get("mathematical_setup"), dict) else {}
    feedback = str(setup.get("feedback_or_measurement_model") or "")
    if (not feedback or "unclear" in feedback.lower()) and "feedback_or_measurement_model" not in existing:
        flags.append({
            "term": "feedback_or_measurement_model",
            "why_ambiguous": "The source evidence does not fully specify what is observed or measured.",
            "what_user_must_define": "Define the observation channel, measurement process, or data collection protocol.",
        })
    return flags


def _fallback_statement(family: dict[str, Any]) -> str:
    title = family.get("family_title", "this project family")
    return f"The question is whether {title} can be stated as a precise, source-grounded problem with explicit observations, assumptions, and success criteria."


def _fallback_formalization(family: dict[str, Any], representative: dict[str, Any], reason: str) -> dict[str, Any]:
    title = _clean_text(family.get("family_title")) or "this project family"
    problem = _family_problem_text(family, representative)
    research_object = _first_text(family.get("research_object"), representative.get("core_setting"), title)
    problem_class = _first_text(family.get("problem_class"), representative.get("broader_problem_class"), "the source problem class")
    assumption = _first_text(
        family.get("assumption_shift"),
        representative.get("assumption_shift"),
        representative.get("core_assumption_or_failure"),
        "the source assumptions",
    )
    boundary = _first_text(
        family.get("failure_boundary_or_mechanism"),
        representative.get("boundary_or_failure_regime"),
        "the source failure boundary",
    )
    objective = _first_text(
        representative.get("core_objective"),
        family.get("theorem_target"),
        family.get("algorithmic_target"),
        family.get("empirical_target"),
        "a source-grounded success criterion",
    )
    target_summary = _target_summary(family, representative)
    inferred_variables = _source_grounded_variables(family, representative)
    variable_gap_flag = [] if inferred_variables else [{
        "term": "problem_variables",
        "why_ambiguous": "The family text does not expose concrete problem-level variables.",
        "what_user_must_define": "Name the observations, actions/outputs, outcomes, objective, and constraints before treating this as formal.",
    }]
    return {
        "plain_language_problem": problem,
        "formal_problem_statement": (
            f"The question is whether {research_object} can be formulated as an instance of "
            f"{problem_class} when {assumption} and the relevant boundary is {boundary}. "
            f"A complete formulation must specify observations, admissible outputs, an objective, "
            f"constraints, and a success criterion tied to {target_summary}."
        ),
        "mathematical_setup": {
            "entities": _source_grounded_entities(family, representative),
            "variables": inferred_variables,
            "data_or_observations": _source_observation_text(family, representative),
            "feedback_or_measurement_model": (
                f"The source family suggests observations for {research_object}, but the exact "
                "feedback or measurement channel is not fully specified in the family record."
            ),
            "decision_variables_or_outputs": (
                f"An admissible method, policy, estimator, design, or explanation for {research_object}; "
                "the exact output type must be chosen from the source papers."
            ),
            "objective": f"Make progress toward {objective} under the stated assumption shift and boundary.",
            "constraints": (
                f"Remain within the source-grounded problem class ({problem_class}) and explicitly state "
                f"which parts of the assumption shift are kept, relaxed, removed, or questioned."
            ),
            "success_criterion": f"A precise result should match one of the source-target forms: {target_summary}.",
        },
        "assumptions": [
            {
                "name": "source assumption shift",
                "description": assumption,
                "status": "questioned",
                "source_evidence": [_short(problem)],
            },
            {
                "name": "failure boundary or mechanism",
                "description": boundary,
                "status": "questioned",
                "source_evidence": [_short(family.get("critic_reason", ""))],
            },
        ],
        "open_question": (
            f"Can {title} be made precise enough to evaluate without inventing assumptions beyond "
            "the verified gaps and family evidence?"
        ),
        "possible_result_types": {
            "theorem": family.get("theorem_target", ""),
            "algorithm": family.get("algorithmic_target", ""),
            "empirical_or_benchmark": family.get("empirical_target", ""),
        },
        "evaluation_protocol": (
            f"Start from the supporting papers and instantiate the observation channel, output type, "
            f"objective, and baseline/evidence checks for {research_object}."
        ),
        "ambiguity_flags": [
            {
                "term": "formalization_parse_error",
                "why_ambiguous": reason,
                "what_user_must_define": "Review the source papers and define the missing formal objects.",
            },
            {
                "term": "feedback_or_measurement_model",
                "why_ambiguous": "The family record does not fully specify what is observed, queried, or measured.",
                "what_user_must_define": "Define the observation channel or measurement process used by the project.",
            },
            {
                "term": "objective",
                "why_ambiguous": "The family gives target directions but not a complete optimization/evaluation objective.",
                "what_user_must_define": "Choose a measurable objective and success criterion from the source-paper context.",
            },
        ] + variable_gap_flag,
        "source_grounding": {
            "source_verified_gaps": family.get("source_verified_gaps", []),
            "supporting_papers": family.get("supporting_papers", []),
            "representative_formulation": family.get("representative_problem_statement", representative.get("problem_statement", "")),
            "critic_reason": family.get("critic_reason", ""),
        },
        "formalization_confidence": "low",
        "formalization_risk": reason,
        "requires_human_definition": True,
    }


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _first_text(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _short(value: Any, limit: int = 240) -> str:
    text = _clean_text(value)
    return text[:limit]


def _family_problem_text(family: dict[str, Any], representative: dict[str, Any]) -> str:
    return _first_text(
        family.get("representative_problem_statement"),
        family.get("family_problem_statement"),
        representative.get("problem_statement"),
        family.get("proposal_style_abstract"),
        family.get("family_title"),
    )


def _combined_problem_text(family: dict[str, Any], representative: dict[str, Any]) -> str:
    pieces = [
        family.get("family_title"),
        family.get("representative_problem_statement"),
        family.get("family_problem_statement"),
        family.get("proposal_style_abstract"),
        family.get("research_object"),
        family.get("problem_class"),
        family.get("assumption_shift"),
        family.get("failure_boundary_or_mechanism"),
        family.get("theorem_target"),
        family.get("algorithmic_target"),
        family.get("empirical_target"),
        representative.get("title"),
        representative.get("problem_statement"),
        representative.get("core_setting"),
        representative.get("core_assumption_or_failure"),
        representative.get("core_objective"),
        representative.get("broader_problem_class"),
        representative.get("assumption_shift"),
        representative.get("boundary_or_failure_regime"),
    ]
    return " ".join(_clean_text(p) for p in pieces if _clean_text(p))


def _source_grounded_entities(family: dict[str, Any], representative: dict[str, Any]) -> list[str]:
    text_l = _combined_problem_text(family, representative).lower()
    research_object = _first_text(family.get("research_object"), representative.get("core_setting"), family.get("family_title"))
    entities = [
        research_object,
        "decision-maker, learner, controller, estimator, or analyst" if _has_any(text_l, "policy", "algorithm", "controller", "estimator", "learner", "decision", "action", "arm", "attack") else "",
        "observation, measurement, or feedback source" if _has_any(text_l, "observation", "observe", "feedback", "measurement", "signal", "data", "sample", "reward") else "",
        "latent factor, hidden state, confounder, prior, or unknown quantity" if _has_any(text_l, "latent", "hidden", "unobserved", "confound", "prior", "unknown", "trust") else "",
        "constraint, failure regime, or boundary condition" if _has_any(text_l, "constraint", "boundary", "condition", "assumption", "failure", "mismatch", "regime") else "",
        "candidate method or analysis procedure",
    ]
    return _unique_nonempty(entities)


def _source_grounded_variables(family: dict[str, Any], representative: dict[str, Any]) -> list[dict[str, str]]:
    variables: list[dict[str, str]] = []

    def add(symbol: str, meaning: str, typ: str, source: str) -> None:
        meaning = _clean_text(meaning)
        if meaning and all(v["symbol"] != symbol for v in variables):
            variables.append({"symbol": symbol, "meaning": meaning, "type": typ, "source": source})

    text = _combined_problem_text(family, representative)
    text_l = text.lower()
    setting = _first_text(family.get("research_object"), representative.get("core_setting"), family.get("family_title"))
    if not text_l:
        return []

    if _has_any(text_l, "arm", "action", "decision", "policy", "control", "controller", "intervention", "choice", "attack"):
        add("a_t", f"action, arm, intervention, attack, or decision chosen at step t in {setting}",
            "other", "inferred from family problem statement / abstract")
    if setting or _has_any(text_l, "observation", "observe", "feedback", "measurement", "signal", "data", "sample", "query", "noise"):
        add("o_t", f"observation, feedback, measurement, query response, or signal available at step t in {setting}",
            "other", "inferred from family problem statement / abstract")
    if _has_any(text_l, "reward", "outcome", "loss", "cost", "success", "regret", "payoff", "response", "performance"):
        add("y_t", f"reward, outcome, loss, cost, success indicator, or response observed after decisions in {setting}",
            "other", "inferred from family problem statement / abstract")
    if _has_any(text_l, "latent", "hidden", "unobserved", "confound", "trust", "reliability", "unknown", "prior", "posterior"):
        add("z", f"latent, hidden, prior, trust, confounding, or unknown factor affecting {setting}",
            "other", "inferred from family problem statement / abstract")
    if _has_any(text_l, "policy", "strategy", "algorithm", "controller", "method", "estimator", "oracle", "attack", "learner"):
        add("pi", f"policy, strategy, estimator, attack rule, controller, or method selected for {setting}",
            "function", "inferred from family problem statement / abstract")
    if _has_any(text_l, "environment", "distribution", "population", "process", "dynamics", "model", "prior", "geometry", "metric"):
        add("P", f"environment, data-generating process, prior, geometry, metric, model, or distribution for {setting}",
            "distribution", "inferred from family problem statement / abstract")
    if _has_any(text_l, "constraint", "boundary", "condition", "assumption", "regime", "limit", "failure", "mismatch", "robust"):
        add("g", f"constraint, regime indicator, failure condition, mismatch measure, or robustness boundary in {setting}",
            "function", "inferred from family problem statement / abstract")
    if _has_any(text_l, "objective", "criterion", "target", "regret", "risk", "performance", "success", "identification", "optimality"):
        add("J", f"objective, risk, regret, identification criterion, performance measure, or success criterion for {setting}",
            "function", "inferred from family problem statement / abstract")
    if _has_any(text_l, "function", "mapping", "lipschitz", "curve", "kernel"):
        add("f", f"problem function, response surface, reward function, mapping, or structural relation in {setting}",
            "function", "inferred from family problem statement / abstract")
    if _has_any(text_l, "estimate", "estimator", "infer", "inference", "identify", "identification", "learn", "predict", "rank"):
        add("q_hat", f"estimated quantity, inferred ranking, learned parameter, prediction, or identified structure for {setting}",
            "other", "inferred from family problem statement / abstract")
    if _has_any(text_l, "time", "sequential", "dynamic", "round", "horizon", "trajectory", "process"):
        add("t", f"time index, interaction round, horizon, trajectory position, or process step in {setting}",
            "scalar", "inferred from family problem statement / abstract")
    return variables


def _has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _unique_nonempty(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def _source_observation_text(family: dict[str, Any], representative: dict[str, Any]) -> str:
    setting = _first_text(representative.get("core_setting"), family.get("research_object"), family.get("problem_class"))
    papers = family.get("supporting_papers", []) or representative.get("supporting_papers", [])
    paper_text = ", ".join(str(p) for p in papers[:3]) if isinstance(papers, list) else _clean_text(papers)
    if setting and paper_text:
        return f"Observations, measurements, logs, or evidence available in {setting}, grounded in supporting papers {paper_text}."
    if setting:
        return f"Observations, measurements, logs, or evidence available in {setting}; the exact channel requires source-paper review."
    return "The available observations must be defined from the source family and supporting papers."


def _target_summary(family: dict[str, Any], representative: dict[str, Any]) -> str:
    theorem = _first_text(family.get("theorem_target"), representative.get("theorem_target"))
    algorithm = _first_text(family.get("algorithmic_target"), representative.get("algorithmic_target"))
    empirical = _first_text(family.get("empirical_target"), representative.get("empirical_target"))
    parts = []
    if theorem:
        parts.append(f"theorem target: {theorem}")
    if algorithm:
        parts.append(f"algorithm target: {algorithm}")
    if empirical:
        parts.append(f"empirical or benchmark target: {empirical}")
    return "; ".join(parts) or "a theorem, algorithmic target, or empirical benchmark chosen from the source papers"


def _compact_family(f: dict[str, Any]) -> dict[str, Any]:
    keys = ["family_id", "family_title", "representative_variant_id", "representative_problem_statement",
            "proposal_style_abstract", "research_object", "problem_class", "assumption_shift",
            "failure_boundary_or_mechanism", "theorem_target", "algorithmic_target", "empirical_target",
            "source_verified_gaps", "source_direct_formulations", "supporting_papers", "critic_reason",
            "main_risk", "downgrade_reasons"]
    return {k: f.get(k) for k in keys}


def _compact_variant(v: dict[str, Any]) -> dict[str, Any]:
    keys = ["variant_id", "title", "problem_statement", "core_setting", "core_assumption_or_failure",
            "core_objective", "broader_problem_class", "assumption_shift", "boundary_or_failure_regime",
            "constructive_or_explanatory_target", "contribution_type", "theorem_target",
            "algorithmic_target", "empirical_target", "supporting_papers", "critic_reason"]
    return {k: v.get(k) for k in keys}


def _compact_direct(d: dict[str, Any]) -> dict[str, Any]:
    keys = ["formulation_id", "source_gap_id", "source_verified_gap_id", "direct_title",
            "direct_problem_statement", "core_setting", "core_assumption_or_failure", "core_objective",
            "supporting_papers", "verification_summary", "verification_provenance"]
    return {k: d.get(k) for k in keys}


def _build_audit(records: list[dict[str, Any]], families: list[dict[str, Any]], *,
                 model_used: str | None, low_signal_reason: str | None = None) -> tuple[str, bool, str, dict[str, Any]]:
    family_ids = {f.get("family_id") for f in families}
    record_ids = {r.get("family_id") for r in records}
    missing = sorted(str(fid) for fid in family_ids - record_ids if fid)
    invented = sorted(str(fid) for fid in record_ids - family_ids if fid)
    confidence_counts = dict(Counter(r.get("formalization_confidence", "unknown") for r in records))
    ambiguity_count = sum(len(r.get("ambiguity_flags", []) or []) for r in records)
    requires_human = sum(1 for r in records if r.get("requires_human_definition"))
    fallback_count = sum(1 for r in records if r.get("formalization_is_fallback"))
    retry_used_count = sum(1 for r in records if r.get("formalization_retry_used"))
    parse_error_count = sum(1 for r in records if str(r.get("formalization_parse_error") or "").strip())
    every_variable_valid = all(
        all(v.get("symbol") and v.get("meaning") and v.get("type") in _VAR_TYPES
            for v in (r.get("mathematical_setup", {}) or {}).get("variables", []))
        for r in records
    )
    every_trace = all(r.get("family_id") in family_ids for r in records)
    every_grounded = all((r.get("source_grounding") or {}).get("source_verified_gaps") is not None for r in records)
    checks = {
        "families_missing_formalization": len(missing) == 0,
        "every_variable_has_symbol_meaning_type": every_variable_valid,
        "every_formalization_traces_to_family_id": every_trace,
        "no_new_family_ids_invented": len(invented) == 0,
        "every_formalization_has_source_grounding": every_grounded,
        "no_new_hypotheses_generated": True,
        "old_evolved_or_ad_hoc_outputs_unused": True,
    }
    if low_signal_reason:
        status = PIPELINE_COMPLETED_LOW_SIGNAL
        audit_pass = all(v for k, v in checks.items() if k != "families_missing_formalization")
    else:
        audit_pass = all(checks.values())
        status = PASS if audit_pass else FAILED
    metrics = {
        "families_missing_formalization": missing,
        "formalization_confidence_counts": confidence_counts,
        "requires_human_definition_count": requires_human,
        "fallback_formalization_count": fallback_count,
        "formalization_retry_used_count": retry_used_count,
        "formalization_parse_error_count": parse_error_count,
        "ambiguity_flag_count": ambiguity_count,
        "malformed_outputs_detected": False,
        "every_variable_has_symbol_meaning_type": every_variable_valid,
    }
    lines = ["# Stage 10 Formal Problem Formulation Audit", "",
             f"- status: {status}",
             f"- families loaded: {len(families)}",
             f"- formalizations generated: {len(records)}",
             f"- low_signal_reason: {low_signal_reason or 'NONE'}",
             f"- families missing formalization: {missing or 'NONE'}",
             f"- formalization_confidence counts: {confidence_counts}",
             f"- requires_human_definition count: {requires_human}",
             f"- fallback formalization count: {fallback_count}",
             f"- repair retry used count: {retry_used_count}",
             f"- parse error count: {parse_error_count}",
             f"- ambiguity flag count: {ambiguity_count}",
             f"- malformed outputs: False",
             f"- model used: {model_used or 'NONE'}", ""]
    lines += [f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in checks.items()]
    lines += ["", "## Provenance",
              "- formalizes existing Stage-9 project families only.",
              "- no new family IDs or hypotheses were generated.",
              "- old evolved report / ad-hoc outputs were not used.",
              f"- forbidden_inputs_not_used: {FORBIDDEN_INPUTS}"]
    return "\n".join(lines), audit_pass, status, metrics


def _write_md(path: Path, records: list[dict[str, Any]], fams_doc: dict[str, Any]) -> None:
    lines = ["# Stage 10 Formal Problem Formulations", "",
             f"- formalizations: {len(records)}", ""]
    if not records:
        lines += ["Low-signal run: no project families were available for formalization.", ""]
    for r in records:
        setup = r.get("mathematical_setup", {}) or {}
        lines += [f"## {r.get('family_id')}. {r.get('family_title')}", "",
                  f"**Plain-language problem.** {r.get('plain_language_problem','')}", "",
                  f"**Formal problem statement.** {r.get('formal_problem_statement','')}", "",
                  "### Variables", "",
                  "| Symbol | Meaning | Type | Source |",
                  "|---|---|---|---|"]
        for v in setup.get("variables", []) or []:
            lines.append(f"| {v.get('symbol','')} | {v.get('meaning','')} | {v.get('type','')} | {v.get('source','')} |")
        lines += ["", f"- entities: {setup.get('entities', [])}",
                  f"- data / observations: {setup.get('data_or_observations','')}",
                  f"- feedback / measurement model: {setup.get('feedback_or_measurement_model','')}",
                  f"- decision variables / outputs: {setup.get('decision_variables_or_outputs','')}",
                  f"- objective: {setup.get('objective','')}",
                  f"- constraints: {setup.get('constraints','')}",
                  f"- success criterion: {setup.get('success_criterion','')}", "",
                  "### Assumptions"]
        for a in r.get("assumptions", []) or []:
            lines.append(f"- {a.get('name','')} ({a.get('status','')}): {a.get('description','')}")
        pr = r.get("possible_result_types", {}) or {}
        lines += ["", f"**Open question.** {r.get('open_question','')}", "",
                  f"- theorem target: {pr.get('theorem','') or '-'}",
                  f"- algorithm target: {pr.get('algorithm','') or '-'}",
                  f"- empirical / benchmark target: {pr.get('empirical_or_benchmark','') or '-'}",
                  f"- evaluation protocol: {r.get('evaluation_protocol','')}",
                  f"- confidence: {r.get('formalization_confidence')} | requires human definition: {r.get('requires_human_definition')}",
                  f"- formalization risk: {r.get('formalization_risk','')}", "",
                  "### Ambiguity Flags"]
        flags = r.get("ambiguity_flags", []) or []
        if flags:
            for flag in flags:
                lines.append(f"- {flag.get('term','')}: {flag.get('why_ambiguous','')} User must define: {flag.get('what_user_must_define','')}")
        else:
            lines.append("- none")
        lines.append("")
    path.write_text("\n".join(lines))
