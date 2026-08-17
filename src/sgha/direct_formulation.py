"""SGHA-native DIRECT formulation stage.

Generates exactly ONE coherent research problem formulation per verification-passed gap,
with no cross-gap synthesis. Branches from gated gaps + verification agent findings + supporting
papers + seed metadata only. Does NOT read evolved hypotheses, the native final report, or any
prior ad-hoc formulation outputs.
"""
from __future__ import annotations

import csv as _csv
import json
from pathlib import Path
from typing import Any

from .llm_client import LLMClient
from .utils import ensure_dir, utc_now_iso
from .verification_gate import (
    MODE_REVIEWED_ONLY,
    VerificationGateError,
    assess_verification_gate,
    write_verification_gate_artifacts,
)

MODEL_NAME = "Qwen/Qwen3.5-9B"
DEFAULT_OUT_SUBDIR = "stage7_direct_formulations_qwen"
_AGENTS = ["support_agent", "skeptic_agent", "feasibility_agent", "mechanism_agent", "critic"]
INPUT_VERIFICATION_PASSED_GAPS = "verification_passed_gaps"
INPUT_VERIFICATION_REVIEWED_GAPS = "verification_reviewed_gaps"
INPUT_VERIFIED_GAPS = "verified_gaps"  # legacy alias; normalized through the gate.
INPUT_NOVELTY_SURVIVORS = "novelty_survivors"
ALLOWED_INPUT_SOURCES = {
    INPUT_VERIFICATION_PASSED_GAPS,
    INPUT_VERIFICATION_REVIEWED_GAPS,
    INPUT_VERIFIED_GAPS,
    INPUT_NOVELTY_SURVIVORS,
}
NEEDS_VERIFICATION_OUTPUTS = "NEEDS_VERIFICATION_OUTPUTS"

# Inputs this stage is FORBIDDEN to read (asserted in run_metadata for provenance).
FORBIDDEN_INPUTS = [
    "final/ranked_hypotheses.json", "final/final_report.md",
    "pre_evolution_formulations_20260608", "ambition_expanded_formulations_20260608",
    "final_direct_formulations_20260608",
]

_PROMPT = """You are formulating ONE direct, coherent research problem from a single verification-passed structural gap. This is a PROPOSAL (no results yet).

DECLARED RUN CONTEXT
- domain_name: {domain_name}
- topic_description: {topic_description}
- keyphrases: {keyphrases}

STRICT COHERENCE RULES:
- exactly one core setting, one main assumption/failure/limitation, one core objective
- one plausible theorem OR algorithm OR benchmark/empirical target
- do NOT combine unrelated methods/assumptions/failures into a collage
- do NOT introduce domain-specific concepts unless they appear in the declared run context, source gap, supporting paper titles, extracted evidence, or verification findings
- use the domain's own entities, objectives, assumptions, feedback/measurement model, and evaluation targets
- if the evidence is thin, say so and lower the scores (do not invent specificity)

SOURCE VERIFICATION-PASSED GAP
- gap_id: {gap_id}
- motif_type: {motif}
- target: {target}
- gap statement: {gap}
- mechanism: {mechanism}
- scope: {scope}
- supporting paper titles: {papers}
- extracted evidence snippets: {extracted_evidence}
- seed-paper alignment score (to the author's seed papers): {seed_score}

VERIFICATION AGENT FINDINGS (already computed; ground your formulation in these):
- support: {support}
- skeptic: {skeptic}
- feasibility: {feasibility}
- mechanism: {mechanism_v}
- critic: {critic}

    Return ONLY a JSON object with EXACTLY these keys:
    {{
 "direct_title": "<= 18 words, specific",
 "direct_problem_statement": "2-4 sentences, one coherent problem",
 "proposal_style_abstract": "120-220 words. Proposal voice: use 'This project studies...', 'The central question is...', 'A successful outcome would...'. NEVER 'we prove', 'we show', 'our experiments demonstrate'.",
 "core_setting": "one setting",
 "core_assumption_or_failure": "the single assumption/failure/limitation",
 "core_objective": "one objective",
 "possible_theorem_target": "one concrete theorem target or '' ",
 "possible_algorithmic_target": "one concrete algorithm target or '' ",
 "possible_empirical_target": "one concrete empirical/benchmark target or '' ",
 "coherence_score": 0.0,
 "specificity_score": 0.0,
 "feasibility_score": 0.0,
 "term_soup_risk": 0.0,
 "main_risk": "the single biggest risk to this being a real, solvable problem",
     "falsification_condition": "what observation would show the problem is not real/important",
     "recommendation": "KEEP | MAYBE | DROP"
    }}
    All four scores are floats in [0,1]. term_soup_risk HIGH means incoherent/collage. Output JSON only."""


def quality_label(f: dict) -> str:
    rec = (f.get("recommendation") or "").upper()
    coh = float(f.get("coherence_score", 0)); spec = float(f.get("specificity_score", 0))
    ts = float(f.get("term_soup_risk", 1))
    if rec == "DROP" or coh < 0.4 or ts > 0.6:
        return "DROP_DIRECT_FORMULATION"
    if coh >= 0.7 and spec >= 0.6 and ts <= 0.3 and rec == "KEEP":
        return "STRONG_DIRECT_FORMULATION"
    if coh >= 0.5 and rec in ("KEEP", "MAYBE"):
        return "USABLE_DIRECT_FORMULATION"
    return "WEAK_DIRECT_FORMULATION"


class VerificationOutputsMissingError(VerificationGateError):
    """Raised when Stage 7 is asked for gated gaps but verification artifacts are absent."""


def _load_candidate_gaps(run_dir: Path) -> list[dict]:
    return json.load(open(run_dir / "gaps" / "candidate_gaps.json"))


def _load_verification(run_dir: Path) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {a: {} for a in _AGENTS}
    for a in _AGENTS:
        p = run_dir / "verification" / f"{a}_results.jsonl"
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip():
                    r = json.loads(line); out[a][r["gap_id"]] = r
    return out


def _agent_presence_from_results(run_dir: Path) -> dict[str, set[str]]:
    presence: dict[str, set[str]] = {}
    for agent, rows in _load_verification(run_dir).items():
        for gid in rows:
            presence.setdefault(gid, set()).add(agent)
    return presence


def _summary_gap_ids(path: Path) -> tuple[set[str], dict[str, set[str]]] | None:
    """Return gap IDs from verification_summary.json, or None when the file is absent.

    The current verifier writes a dict keyed by gap_id with one row per agent. Older/future summary
    shapes are accepted when they contain explicit gap_id fields.
    """
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    ids: set[str] = set()
    agents: dict[str, set[str]] = {}
    if isinstance(data, dict):
        for gid, rows in data.items():
            if not gid:
                continue
            sgid = str(gid)
            ids.add(sgid)
            agents.setdefault(sgid, set())
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and row.get("agent_name"):
                        agents[sgid].add(str(row["agent_name"]))
            elif isinstance(rows, dict):
                for key in ("agents_present", "agents", "agent_names"):
                    if isinstance(rows.get(key), list):
                        agents[sgid].update(str(a) for a in rows[key])
                if rows.get("agent_name"):
                    agents[sgid].add(str(rows["agent_name"]))
                for agent in _AGENTS:
                    if agent in rows:
                        agents[sgid].add(agent)
    elif isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            gid = row.get("gap_id") or row.get("id")
            if not gid:
                continue
            sgid = str(gid)
            ids.add(sgid)
            agents.setdefault(sgid, set())
            if row.get("agent_name"):
                agents[sgid].add(str(row["agent_name"]))
            for key in ("agents_present", "agents", "agent_names"):
                if isinstance(row.get(key), list):
                    agents[sgid].update(str(a) for a in row[key])
    return ids, agents


def _survival_gap_ids(path: Path) -> set[str] | None:
    if not path.exists():
        return None
    with path.open(newline="") as fh:
        return {str(row["gap_id"]) for row in _csv.DictReader(fh) if row.get("gap_id")}


def _complete_agent_gap_ids(run_dir: Path) -> tuple[set[str], dict[str, set[str]]] | None:
    files = [run_dir / "verification" / f"{agent}_results.jsonl" for agent in _AGENTS]
    if not all(p.exists() for p in files):
        return None
    presence = _agent_presence_from_results(run_dir)
    ids = {gid for gid, agents in presence.items() if set(_AGENTS) <= agents}
    return ids, presence


def _normalize_input_source(input_source: str, gate_cfg: dict[str, Any]) -> str:
    if input_source == INPUT_VERIFIED_GAPS:
        if gate_cfg.get("enabled") is False or gate_cfg.get("mode") == MODE_REVIEWED_ONLY:
            return INPUT_VERIFICATION_REVIEWED_GAPS
        return INPUT_VERIFICATION_PASSED_GAPS
    return input_source


def load_verified_gap_ids(run_dir: Path, *, require_outputs: bool = True,
                          gate_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compatibility loader returning verification-passed IDs under the configured gate."""
    try:
        assessment = assess_verification_gate(run_dir, gate_config, require_outputs=require_outputs)
    except VerificationGateError as exc:
        if require_outputs:
            raise VerificationOutputsMissingError(
                f"{NEEDS_VERIFICATION_OUTPUTS}: Stage 7 direct formulations require usable verification artifacts. {exc}"
            ) from exc
        return {"gap_ids": set(), "source": "missing", "agent_presence": {}}
    return {
        "gap_ids": set(assessment.passed_ids),
        "source": assessment.source,
        "agent_presence": assessment.agent_presence,
        "verification_gate": assessment.summary(),
    }


def _select_direct_input_gaps(run_dir: Path, input_source: str, config: dict[str, Any]) -> tuple[list[dict], dict[str, Any]]:
    candidates = _load_candidate_gaps(run_dir)
    if input_source not in ALLOWED_INPUT_SOURCES:
        raise ValueError(f"direct_formulations.input_source must be one of {sorted(ALLOWED_INPUT_SOURCES)}; got {input_source!r}")

    gate_cfg = dict(config.get("verification_gate", {}) or {})
    direct_input_source = _normalize_input_source(input_source, gate_cfg)
    require_outputs = bool(candidates) and direct_input_source in {INPUT_VERIFICATION_PASSED_GAPS, INPUT_VERIFICATION_REVIEWED_GAPS}
    try:
        assessment = assess_verification_gate(run_dir, gate_cfg, require_outputs=require_outputs)
    except VerificationGateError as exc:
        if require_outputs:
            raise VerificationOutputsMissingError(
                f"{NEEDS_VERIFICATION_OUTPUTS}: Stage 7 direct formulations require usable verification artifacts. {exc}"
            ) from exc
        assessment = assess_verification_gate(run_dir, gate_cfg, require_outputs=False)
    artifact_paths = write_verification_gate_artifacts(run_dir, assessment) if assessment.source != "missing" else {}

    reviewed_ids = set(assessment.reviewed_ids)
    passed_ids = set(assessment.passed_ids)
    if direct_input_source == INPUT_VERIFICATION_PASSED_GAPS:
        selected_ids = passed_ids
        gaps = [g for g in candidates if str(g.get("gap_id")) in selected_ids]
    elif direct_input_source == INPUT_VERIFICATION_REVIEWED_GAPS:
        selected_ids = reviewed_ids
        gaps = [g for g in candidates if str(g.get("gap_id")) in selected_ids]
    else:
        selected_ids = reviewed_ids | passed_ids
        gaps = candidates

    meta = {
        "candidate_gaps_available": len(candidates),
        "configured_direct_formulation_input_source": input_source,
        "direct_formulation_input_source": direct_input_source,
        "verification_gap_ids_loaded": len(selected_ids),
        "verification_gap_id_source": assessment.source,
        "verification_agent_presence": {
            gid: sorted(a for a in agents if a in _AGENTS)
            for gid, agents in (assessment.agent_presence or {}).items()
        },
        "verification_reviewed_gap_ids": sorted(reviewed_ids),
        "verification_passed_gap_ids": sorted(passed_ids),
        "verification_failed_gap_ids": sorted(assessment.failed_ids),
        "verification_selected_gap_ids": sorted(str(g.get("gap_id")) for g in gaps),
        "verification_gate_decisions": assessment.decisions,
        **assessment.summary(),
        **artifact_paths,
    }
    return gaps, meta


def _load_seed_relationships(run_dir: Path) -> tuple[set[str], dict[str, Any]]:
    rel_path = run_dir / "corpus" / "paper_relationships.jsonl"
    if not rel_path.exists():
        return set(), {
            "seed_relationships_file_present": False,
            "seed_relationships_loaded": 0,
            "seed_relationships_mode": "none_general_run",
            "seed_relationships_path": str(rel_path),
        }

    seed_paper_ids: set[str] = set()
    loaded = 0
    for lineno, line in enumerate(rel_path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON in {rel_path} line {lineno}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Malformed relationship record in {rel_path} line {lineno}: expected object")
        loaded += 1
        if record.get("is_manual_seed_paper"):
            paper_id = record.get("paper_id")
            if not paper_id:
                raise ValueError(f"Malformed relationship record in {rel_path} line {lineno}: missing paper_id")
            seed_paper_ids.add(str(paper_id))
    return seed_paper_ids, {
        "seed_relationships_file_present": True,
        "seed_relationships_loaded": loaded,
        "seed_relationships_mode": "loaded",
        "seed_relationships_path": str(rel_path),
    }


def _load_domain_context(ctx: Any) -> dict[str, Any]:
    cfg = ctx.config or {}
    pers = (cfg.get("personalization", {}) or {})
    query = cfg.get("query", "")
    query_text = query.get("text", "") if isinstance(query, dict) else str(query or "")
    topic = pers.get("topic") if pers.get("topic") and pers.get("topic") != "auto" else ""
    profile_path = ctx.run_dir / "profile" / "seed_topic_profile.json"
    profile: dict[str, Any] = {}
    if profile_path.exists():
        try:
            loaded = json.loads(profile_path.read_text())
            profile = loaded if isinstance(loaded, dict) else {}
        except Exception:
            profile = {}
    keyphrases = []
    for source in (pers.get("keyphrases"), profile.get("keyphrases"), cfg.get("anchor_terms")):
        if isinstance(source, list):
            keyphrases.extend(str(x) for x in source if str(x).strip())
    topic_description = topic or str(profile.get("topic") or query_text or ctx.run_id)
    domain_name = str(pers.get("seed_label") or cfg.get("domain_name") or topic_description or ctx.run_id)
    return {
        "domain_name": domain_name,
        "topic_description": topic_description,
        "keyphrases": sorted(dict.fromkeys(keyphrases))[:24],
    }


def _compact_gap_evidence(gap: dict, *, limit: int = 900) -> str:
    snippets: list[str] = []
    for ev in gap.get("supporting_evidence", []) or []:
        if not isinstance(ev, dict):
            continue
        paper = str(ev.get("paper_id") or ev.get("source") or "").strip()
        text = str(ev.get("evidence_text") or ev.get("text") or ev.get("snippet") or "").strip()
        if text:
            snippets.append((f"{paper}: " if paper else "") + text)
    if not snippets:
        path = gap.get("traceability_path") or []
        snippets = [str(x) for x in path[:5] if str(x).strip()]
    text = " | ".join(snippets)
    return text[:limit] if text else "(none)"


def build_direct_formulation_prompt(gap: dict, verification: dict[str, dict[str, dict]],
                                    titles: dict[str, str], seed_score: float,
                                    domain_context: dict[str, Any]) -> str:
    gid = str(gap["gap_id"])
    papers = list(gap.get("paper_ids") or [])
    ptitles = "; ".join(titles.get(p, p)[:70] for p in papers[:6]) or "(none)"
    vs = lambda a: (verification.get(a, {}).get(gid, {}).get("summary", "") or "")[:300]
    return _PROMPT.format(
        domain_name=domain_context.get("domain_name") or "(not declared)",
        topic_description=domain_context.get("topic_description") or "(not declared)",
        keyphrases=", ".join(domain_context.get("keyphrases") or []) or "(none)",
        gap_id=gid,
        motif=gap.get("motif_type", ""),
        target=gap.get("target", ""),
        gap=str(gap.get("gap", ""))[:600],
        mechanism=str(gap.get("mechanism", ""))[:300],
        scope=str(gap.get("scope", ""))[:200],
        papers=ptitles,
        extracted_evidence=_compact_gap_evidence(gap),
        seed_score=seed_score,
        support=vs("support_agent"),
        skeptic=vs("skeptic_agent"),
        feasibility=vs("feasibility_agent"),
        mechanism_v=vs("mechanism_agent"),
        critic=vs("critic"),
    )


def run_direct_formulations(ctx: Any, *, llm_base_url: str | None = None,
                            out_subdir: str = DEFAULT_OUT_SUBDIR,
                            input_source: str | None = None) -> dict:
    """One direct formulation per selected gated gap. Returns a summary dict."""
    run_dir = ctx.run_dir
    out = run_dir / out_subdir; ensure_dir(out)
    df_cfg = (ctx.config.get("direct_formulations", {}) or {})
    direct_input_source = input_source or df_cfg.get("input_source", INPUT_VERIFIED_GAPS)
    gaps, input_meta = _select_direct_input_gaps(run_dir, direct_input_source, ctx.config)
    direct_input_source = input_meta["direct_formulation_input_source"]
    reviewed_ids = set(input_meta.get("verification_reviewed_gap_ids", []))
    passed_ids = set(input_meta.get("verification_passed_gap_ids", []))
    titles = {p["arxiv_id"]: p.get("title", "") for p in json.load(open(run_dir / "arxiv" / "papers_manifest.json"))}
    seed, seed_relationship_meta = _load_seed_relationships(run_dir)
    verif = _load_verification(run_dir)
    domain_context = _load_domain_context(ctx)
    llm = LLMClient(ctx, base_url=llm_base_url)

    formulations = []
    for i, g in enumerate(gaps, 1):
        gid = g["gap_id"]
        sp = list(g.get("paper_ids") or [])
        sa_score = round(sum(1 for p in sp if p in seed) / max(1, len(sp)), 3) if sp else 0.0
        related_seed = [p for p in sp if p in seed]
        vs = lambda a: (verif[a].get(gid, {}).get("summary", "") or "")[:300]
        agents_present = [a for a in _AGENTS if gid in verif.get(a, {})]
        if len(agents_present) < len(_AGENTS):
            agents_present = [a for a in input_meta.get("verification_agent_presence", {}).get(gid, []) if a in _AGENTS]
        if gid in passed_ids:
            verification_provenance = "VERIFICATION_PASSED"
        elif gid in reviewed_ids:
            verification_provenance = "VERIFICATION_REVIEWED"
        else:
            verification_provenance = "NOVELTY_ONLY"
        prompt = build_direct_formulation_prompt(g, verif, titles, sa_score, domain_context)
        try:
            data, *_ = llm.complete_json(stage="direct_formulation", agent_name="direct_formulation",
                                         prompt=prompt, max_tokens=1200, temperature=0.3, enable_thinking=False)
            fallback = False
        except Exception as e:
            data = {"recommendation": "DROP", "coherence_score": 0.0, "term_soup_risk": 1.0, "main_risk": f"llm_error: {e}"}
            fallback = True
        f = {
            "formulation_id": f"direct:{i:02d}", "source_gap_id": gid, "source_verified_gap_id": gid,
            "source_gap_summary": str(g.get("gap", ""))[:300], "source_motif_type": g.get("motif_type", ""),
            "verification_provenance": verification_provenance,
            "verification_agent_count": len(agents_present),
            "verification_agents_present": agents_present,
            "direct_title": data.get("direct_title", ""), "direct_problem_statement": data.get("direct_problem_statement", ""),
            "proposal_style_abstract": data.get("proposal_style_abstract", ""),
            "core_setting": data.get("core_setting", ""), "core_assumption_or_failure": data.get("core_assumption_or_failure", ""),
            "core_objective": data.get("core_objective", ""),
            "possible_theorem_target": data.get("possible_theorem_target", ""),
            "possible_algorithmic_target": data.get("possible_algorithmic_target", ""),
            "possible_empirical_target": data.get("possible_empirical_target", ""),
            "supporting_papers": sp, "related_seed_papers": related_seed, "author_seed_alignment_score": sa_score,
            "author_seed_alignment_reason": (f"Builds on uploaded seed paper(s): {related_seed}" if related_seed
                                             else ("No direct overlap with uploaded seed papers."
                                                   if seed_relationship_meta["seed_relationships_file_present"]
                                                   else "General run: no seed-paper relationship metadata was provided.")),
            "verification_summary": {a.replace("_agent", ""): vs(a) for a in _AGENTS},
            "traceability_path": g.get("traceability_path", []),
            "coherence_score": float(data.get("coherence_score", 0) or 0), "specificity_score": float(data.get("specificity_score", 0) or 0),
            "feasibility_score": float(data.get("feasibility_score", 0) or 0), "term_soup_risk": float(data.get("term_soup_risk", 0) or 0),
            "main_risk": data.get("main_risk", ""), "falsification_condition": data.get("falsification_condition", ""),
            "recommendation": (data.get("recommendation") or "DROP").upper(), "abstract_is_fallback": fallback,
            "verification_gate_decision": input_meta.get("verification_gate_decisions", {}).get(gid, {}),
            "verification_gate_passed": gid in passed_ids,
            "domain_context": domain_context,
        }
        f["quality_label"] = quality_label(f)
        formulations.append(f)
        print(f"[direct] {f['formulation_id']} gap={gid[:24]} label={f['quality_label']} coh={f['coherence_score']}", flush=True)

    with open(out / "direct_formulations.jsonl", "w") as fh:
        for f in formulations:
            fh.write(json.dumps(f) + "\n")
    verification_passed = sum(1 for f in formulations if f.get("verification_provenance") == "VERIFICATION_PASSED")
    verification_reviewed = sum(1 for f in formulations if f.get("verification_provenance") == "VERIFICATION_REVIEWED")
    novelty_only = sum(1 for f in formulations if f.get("verification_provenance") == "NOVELTY_ONLY")
    stage_model = getattr(llm, "model", (ctx.config.get("llm", {}) or {}).get("model", MODEL_NAME))
    meta = {"stage": "direct_formulation", "model": stage_model, "llm_base_url": llm_base_url or ctx.config.get("llm", {}).get("base_url"),
            "created_at": utc_now_iso(), "run_id": ctx.run_id,
            "direct_formulation_input_source": direct_input_source,
            "verification_backed_only": direct_input_source in {INPUT_VERIFICATION_PASSED_GAPS, INPUT_VERIFICATION_REVIEWED_GAPS},
            "verification_passed_only": direct_input_source == INPUT_VERIFICATION_PASSED_GAPS,
            "direct_formulations": len(formulations),
            "verification_passed_direct_formulations": verification_passed,
            "verification_reviewed_direct_formulations": verification_reviewed,
            "novelty_only_direct_formulations": novelty_only,
            "one_per_input_gap": len(formulations) == len(gaps),
            "input_source": direct_input_source,
            "domain_context": domain_context,
            "forbidden_inputs_not_used": FORBIDDEN_INPUTS}
    if direct_input_source == INPUT_VERIFICATION_PASSED_GAPS:
        meta["verification_passed_gaps_used"] = len(gaps)
        meta["one_per_verification_passed_gap"] = len(formulations) == len(gaps)
        meta["verified_gaps_used"] = len(gaps)  # legacy compatibility; means passed under the gate.
        meta["one_per_verified_gap"] = len(formulations) == len(gaps)
    elif direct_input_source == INPUT_VERIFICATION_REVIEWED_GAPS:
        meta["verification_reviewed_gaps_used"] = len(gaps)
        meta["one_per_verification_reviewed_gap"] = len(formulations) == len(gaps)
        meta["reviewed_only_warning"] = "Outputs are verification-reviewed, not verification-passed."
    else:
        meta["novelty_survivors_used"] = len(gaps)
        meta["one_per_novelty_survivor"] = len(formulations) == len(gaps)
    meta.update(input_meta)
    meta.update(seed_relationship_meta)
    json.dump(meta, open(out / "run_metadata.json", "w"), indent=2)
    _write_md(out / "direct_formulations.md", formulations, meta)
    print(f"[direct] DONE source={direct_input_source} gaps={len(gaps)} formulations={len(formulations)} "
          f"passed={verification_passed} reviewed={verification_reviewed} novelty_only={novelty_only}", flush=True)
    return meta


def _write_md(path: Path, F: list[dict], meta: dict | None = None) -> None:
    from collections import Counter
    meta = meta or {}
    lab = Counter(f["quality_label"] for f in F)
    prov = Counter(f.get("verification_provenance", "UNKNOWN") for f in F)
    input_source = meta.get("direct_formulation_input_source", "?")
    model_name = meta.get("model", MODEL_NAME)
    if input_source == INPUT_NOVELTY_SURVIVORS:
        title = "# Direct Formulations From Novelty Survivors (SGHA Stage 7)"
        unit = "novelty survivor"
    elif input_source == INPUT_VERIFICATION_REVIEWED_GAPS:
        title = "# Direct Verification-Reviewed Gap Formulations (SGHA Stage 7)"
        unit = "verification-reviewed gap"
    else:
        title = "# Direct Verification-Passed Gap Formulations (SGHA Stage 7)"
        unit = "verification-passed gap"
    lines = [title, "",
             f"- model: {model_name}", f"- formulations: {len(F)} (one per {unit})",
             f"- direct_formulation_input_source: {meta.get('direct_formulation_input_source', '?')}",
             f"- verification_backed_only: {meta.get('verification_backed_only', '?')}",
             f"- verification_passed_only: {meta.get('verification_passed_only', '?')}",
             f"- verification gate: enabled={meta.get('verification_gate_enabled')} mode={meta.get('verification_gate_mode')} threshold={meta.get('verification_gate_threshold')}",
             f"- verification counts: reviewed={meta.get('verification_reviewed_count')} passed={meta.get('verification_passed_count')} failed={meta.get('verification_failed_count')}",
             f"- provenance: {dict(prov)}",
             f"- labels: {dict(lab)}", f"- seed-aligned: {sum(1 for f in F if f['author_seed_alignment_score']>0)}", ""]
    if meta.get("reviewed_only_warning"):
        lines += [f"> Warning: {meta['reviewed_only_warning']}", ""]
    for f in F:
        lines += [f"## {f['formulation_id']}. {f['direct_title']}  ({f['quality_label']})",
                  f"- source gap: `{f.get('source_gap_id', f.get('source_verified_gap_id'))}` [{f['source_motif_type']}]",
                  f"- verification provenance: {f.get('verification_provenance')} ({f.get('verification_agent_count', 0)} agents)",
                  f"- scores: coherence {f['coherence_score']} | specificity {f['specificity_score']} | term-soup {f['term_soup_risk']} | seed {f['author_seed_alignment_score']}",
                  f"- problem: {f['direct_problem_statement']}",
                  f"- core setting: {f['core_setting']} | assumption/failure: {f['core_assumption_or_failure']} | objective: {f['core_objective']}",
                  f"- supporting papers: {f['supporting_papers'][:6]} | related seed: {f['related_seed_papers'] or '—'}",
                  "", f"**Abstract.** {f['proposal_style_abstract']}", ""]
    path.write_text("\n".join(lines))
