#!/usr/bin/env python3
"""OpenRouter LLM-as-judge runner for blinded SGHA comparison packets.

The default workflow is deliberately conservative:
- dry-run validates packets and planned candidates/pairs without network calls;
- mock-response mode exercises parsing/output code without network calls;
- live mode is available for later and requires OPENROUTER_API_KEY;
- unblinding is an explicit postprocess mode that runs after scoring exists.
"""
from __future__ import annotations

import argparse
import collections
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import signal
import sys
import time
from typing import Any

import requests
import yaml


REQUIRED_PACKET_FILES = (
    "blinded_review_packet.md",
    "blinded_candidates.jsonl",
    "comparison_audit.md",
)
BLINDING_KEY_FILE = "blinding_key.json"
INDEPENDENT_BLINDING_KEY_GLOB = "*_blinding_key.json"
FORBIDDEN_PROMPT_LABELS = (
    "SGHA",
    "SGHA_FULL",
    "SIMPLE_QWEN",
    "Simple Qwen",
    "QWEN_RAG",
    "Qwen+RAG",
    "Qwen RAG",
    "AI_SCIENTIST",
    "NATIVE_AI_SCIENTIST_V2",
    "AI-Scientist",
    "Native AI-Scientist",
    "baseline method",
)
NOVELTY_CAVEAT = "Novelty potential judged only from provided text; no external novelty check performed."
PERSONALIZATION_CAVEAT = "Profile alignment judged only from provided profile context; no external profile knowledge used."
NOT_PROVIDED = "not provided"
CALIBRATED_PACKET_FIELDS = (
    "candidate_id",
    "domain",
    "title",
    "problem_statement",
    "motivation_or_abstract",
    "proposed_direction",
    "expected_contribution",
    "evaluation_plan",
    "risks_or_caveats",
    "source_context_or_grounding",
    "formal_problem_statement",
    "assumptions_or_problem_setup",
    "ambiguity_or_missing_definitions",
)
PAIRWISE_PREFERENCE_CRITERIA = (
    "clarity_specificity",
    "significance",
    "novelty_potential",
    "feasibility",
    "evidence_grounding",
    "formalizability",
    "non_incrementality",
    "actionability",
    "low_term_soup",
    "auditability_overall",
    "pursuit_priority",
)
PAIRWISE_WINNERS = {"A", "B", "TIE", "CANNOT_JUDGE"}
PAIRWISE_CRITERION_WINNERS = {"A", "B", "TIE"}
PAIRWISE_SOURCE_POOLS = (
    "SGHA_FINAL_FAMILY",
    "SGHA_DIRECT",
    "SGHA_AMBITION_FINAL",
    "SIMPLE_QWEN",
    "QWEN_RAG",
    "NATIVE_AI_SCIENTIST_V2",
    "SGHA_LEGACY_EVOLUTION",
)
PAIRWISE_COMMON_FIELDS = ("source_pool",) + CALIBRATED_PACKET_FIELDS
FOUR_WAY_DOMAINS = (
    "bandits",
    "in_context_learning",
    "reasoning_models_test_time_compute",
    "offline_reinforcement_learning_arxiv",
    "uncertainty_calibration_conformal_prediction_arxiv",
)
FOUR_WAY_METHODS = ("SGHA_FULL", "SIMPLE_QWEN", "QWEN_RAG", "NATIVE_AI_SCIENTIST_V2")
OUTPUT_MATCHED_COUNTS_BY_DOMAIN = {
    "bandits": 3,
    "in_context_learning": 4,
    "reasoning_models_test_time_compute": 1,
    "offline_reinforcement_learning_arxiv": 1,
    "uncertainty_calibration_conformal_prediction_arxiv": 6,
}
FOUR_WAY_RANK_CRITERIA = (
    "clarity_specificity",
    "significance",
    "novelty_potential",
    "feasibility",
    "evidence_grounding",
    "formalizability",
    "non_incrementality",
    "actionability",
    "low_term_soup",
    "auditability_overall",
    "pursuit_priority",
)
FOUR_WAY_SPECIAL_WINNERS = (
    "best_overall_candidate",
    "most_auditable_candidate",
    "most_actionable_candidate",
    "most_novel_potential_candidate",
)
ROLE_BASED_MODE = "role_based_10pt"
FORMULATION_QUALITY_MODE = "formulation_quality_10pt"
FORMULATION_ONLY_MODE = "formulation_only_10pt"
PERSONALIZED_FORMULATION_MODE = "personalized_formulation_10pt"
PRISM_IDEA_QUALITY_MODE = "prism_idea_quality_10pt"
ROLE_BASED_CONFIDENCE_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
FORMULATION_QUALITY_CRITERIA = (
    "well_posedness_0_to_10",
    "technical_sharpness_0_to_10",
    "meaningful_assumption_shift_0_to_10",
    "nontriviality_0_to_10",
    "domain_fit_0_to_10",
    "source_grounded_specificity_0_to_10",
    "feasibility_0_to_10",
    "scope_control_0_to_10",
    "ambiguity_hygiene_0_to_10",
    "overall_formulation_quality_0_to_10",
)
FORMULATION_ONLY_CRITERIA = (
    "problem_definition_clarity_10",
    "technical_specificity_10",
    "well_posedness_10",
    "assumption_boundary_clarity_10",
    "formalizability_10",
    "nontriviality_10",
    "scope_control_10",
    "source_grounded_specificity_10",
    "ambiguity_hygiene_10",
    "overall_formulation_quality_10",
)
PERSONALIZED_FORMULATION_CRITERIA = FORMULATION_ONLY_CRITERIA + (
    "profile_alignment_10",
    "profile_specificity_10",
    "intellectual_style_match_10",
    "profile_novelty_fit_10",
    "personalization_overall_10",
)
FORMULATION_QUALITY_ACTIONS = {
    "READ_FIRST",
    "PROMISING_NEEDS_REFINEMENT",
    "NEEDS_REFRAMING",
    "DROP_OR_DEPRIORITIZE",
}
PRISM_IDEA_QUALITY_CRITERIA = (
    "novelty_originality_10",
    "feasibility_10",
    "potential_impact_10",
    "clarity_coherence_10",
    "actionability_10",
    "groundedness_10",
    "traceability_auditability_10",
    "non_redundancy_scope_control_10",
)
PRISM_IDEA_QUALITY_ACTIONS = FORMULATION_QUALITY_ACTIONS
PRISM_NOVELTY_CAVEAT = "Novelty/originality judged only from provided text; no external novelty check performed."


class JudgeError(RuntimeError):
    """Raised when judge inputs or outputs are invalid."""


@dataclass
class CandidatePair:
    comparison_id: str
    domain: str
    baseline: str
    comparison_dir: Path
    candidate_a: dict[str, Any]
    candidate_b: dict[str, Any]

    @property
    def candidate_a_id(self) -> str:
        return str(self.candidate_a.get("candidate_id", "Candidate A"))

    @property
    def candidate_b_id(self) -> str:
        return str(self.candidate_b.get("candidate_id", "Candidate B"))


@dataclass
class IndependentCandidate:
    candidate_id: str
    domain: str
    candidate: dict[str, Any]
    candidate_file: Path


@dataclass
class PairwisePreferencePair:
    pair_id: str
    domain: str
    candidate_a: dict[str, Any]
    candidate_b: dict[str, Any]
    pair_file: Path

    @property
    def candidate_a_id(self) -> str:
        return str(self.candidate_a.get("candidate_id", "Candidate A"))

    @property
    def candidate_b_id(self) -> str:
        return str(self.candidate_b.get("candidate_id", "Candidate B"))


@dataclass
class FourWayPacket:
    domain: str
    candidates: list[dict[str, Any]]
    packet_file: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise JudgeError(f"Config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise JudgeError(f"Config must be a mapping: {path}")
    required = ["judge", "evaluation", "rubric", "pairwise", "outputs"]
    missing = [key for key in required if key not in data]
    if missing:
        raise JudgeError(f"Config missing sections: {missing}")
    if data["judge"].get("provider") != "openrouter":
        raise JudgeError("Only provider=openrouter is supported")
    scoring_mode = data.get("evaluation", {}).get("scoring_mode", "pairwise")
    if scoring_mode not in {"independent", "pairwise", "pairwise_preference", "four_way_ranked", ROLE_BASED_MODE, FORMULATION_QUALITY_MODE, FORMULATION_ONLY_MODE, PERSONALIZED_FORMULATION_MODE, PRISM_IDEA_QUALITY_MODE}:
        raise JudgeError("evaluation.scoring_mode must be independent, pairwise, pairwise_preference, four_way_ranked, role_based_10pt, formulation_quality_10pt, formulation_only_10pt, personalized_formulation_10pt, or prism_idea_quality_10pt")
    if not data["judge"].get("model"):
        raise JudgeError("judge.model is required")
    if not data["judge"].get("base_url"):
        raise JudgeError("judge.base_url is required")
    if not data["evaluation"].get("no_weighted_composite", False):
        raise JudgeError("evaluation.no_weighted_composite must be true")
    if scoring_mode == ROLE_BASED_MODE:
        if data.get("pairwise", {}).get("enabled"):
            raise JudgeError("pairwise.enabled must be false for role_based_10pt")
        roles = data.get("roles")
        if not isinstance(roles, list) or len(roles) != 3:
            raise JudgeError("role_based_10pt requires exactly three roles")
        for role in roles:
            if not isinstance(role, dict) or not role.get("id") or not isinstance(role.get("scores"), list) or not role.get("scores"):
                raise JudgeError("each role must have id and nonempty scores")
        if not data["evaluation"].get("use_calibration_sentinels", False):
            raise JudgeError("role_based_10pt requires evaluation.use_calibration_sentinels=true")
        if not data["evaluation"].get("enforce_cap_rules", False):
            raise JudgeError("role_based_10pt requires evaluation.enforce_cap_rules=true")
    return data


def rubric_ids(config: dict[str, Any]) -> list[str]:
    criteria = config.get("rubric", {}).get("criteria", [])
    ids = [str(item.get("id")) for item in criteria if isinstance(item, dict) and item.get("id")]
    if not ids:
        raise JudgeError("Rubric has no criteria IDs")
    return ids


def role_definitions(config: dict[str, Any]) -> list[dict[str, Any]]:
    roles = config.get("roles", [])
    if not isinstance(roles, list) or not roles:
        raise JudgeError("No role definitions configured")
    return roles


def role_by_id(config: dict[str, Any], role_id: str) -> dict[str, Any]:
    for role in role_definitions(config):
        if str(role.get("id")) == role_id:
            return role
    raise JudgeError(f"Unknown role_id: {role_id}")


def role_score_ids(config: dict[str, Any], role_id: str | None = None) -> list[str]:
    if role_id is not None:
        role = role_by_id(config, role_id)
        return [str(item) for item in role.get("scores", [])]
    ids: list[str] = []
    for role in role_definitions(config):
        ids.extend(str(item) for item in role.get("scores", []))
    if not ids:
        raise JudgeError("No role score IDs configured")
    return ids


def preference_options(config: dict[str, Any]) -> set[str]:
    return {str(x) for x in config.get("pairwise", {}).get("preference_options", [])}


def confidence_options(config: dict[str, Any]) -> set[str]:
    return {str(x) for x in config.get("pairwise", {}).get("confidence_options", [])}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise JudgeError(f"Invalid JSONL in {path}:{lineno}: {exc}") from exc
            if not isinstance(value, dict):
                raise JudgeError(f"Expected object in {path}:{lineno}")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")


def discover_comparison_dirs(comparison_root: Path, domains: list[str] | None = None) -> list[Path]:
    if not comparison_root.exists():
        raise JudgeError(f"Comparison root not found: {comparison_root}")
    domain_filter = set(domains or [])
    dirs = []
    for candidate in comparison_root.rglob("blinded_candidates.jsonl"):
        comp_dir = candidate.parent
        if all((comp_dir / name).exists() for name in REQUIRED_PACKET_FILES):
            domain = infer_domain(comp_dir, comparison_root)
            if domain_filter and domain not in domain_filter:
                continue
            dirs.append(comp_dir)
    return sorted(set(dirs), key=lambda p: str(p))


def infer_domain(comparison_dir: Path, comparison_root: Path) -> str:
    try:
        rel = comparison_dir.relative_to(comparison_root)
        if rel.parts:
            return rel.parts[0]
    except ValueError:
        pass
    return comparison_dir.parent.name


def infer_baseline(comparison_dir: Path, comparison_root: Path, baseline_name: str | None) -> str:
    if baseline_name:
        return baseline_name
    name = comparison_dir.name
    root_name = comparison_root.name
    if "simple_qwen" in name or "simple_qwen" in root_name:
        return "simple_qwen"
    if "qwen_rag" in name or "qwen_rag" in root_name:
        return "qwen_rag"
    if "native_ai_scientist" in name or "native_ai_scientist" in str(comparison_root):
        return "native_ai_scientist_v2"
    return "comparison"


def load_blinded_candidates(comparison_dir: Path) -> list[dict[str, Any]]:
    return read_jsonl(comparison_dir / "blinded_candidates.jsonl")


def load_independent_candidates(candidate_file: Path, domain: str | None = None) -> list[IndependentCandidate]:
    rows = read_jsonl(candidate_file)
    candidates: list[IndependentCandidate] = []
    for index, row in enumerate(rows, start=1):
        cid = str(row.get("candidate_id") or f"Candidate {index}")
        cdomain = str(row.get("domain") or domain or "unknown")
        candidates.append(IndependentCandidate(candidate_id=cid, domain=cdomain, candidate=row, candidate_file=candidate_file))
    return candidates


def load_pairwise_preference_pairs(pair_file: Path) -> list[PairwisePreferencePair]:
    rows = read_jsonl(pair_file)
    pairs: list[PairwisePreferencePair] = []
    for index, row in enumerate(rows, start=1):
        candidate_a = row.get("candidate_a")
        candidate_b = row.get("candidate_b")
        if not isinstance(candidate_a, dict) or not isinstance(candidate_b, dict):
            raise JudgeError(f"Pairwise packet row {index} must contain candidate_a and candidate_b objects")
        pair_id = str(row.get("pair_id") or f"pair_{index:03d}")
        pairs.append(
            PairwisePreferencePair(
                pair_id=pair_id,
                domain=str(row.get("domain") or "unknown"),
                candidate_a=candidate_a,
                candidate_b=candidate_b,
                pair_file=pair_file,
            )
        )
    return pairs


def load_four_way_packets(packet_dir: Path) -> list[FourWayPacket]:
    if packet_dir.is_file():
        files = [packet_dir]
    else:
        files = sorted(packet_dir.glob("*_4way_blinded.json"))
    packets: list[FourWayPacket] = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise JudgeError(f"Four-way packet must be a JSON object: {path}")
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or len(candidates) != 4:
            raise JudgeError(f"Four-way packet must contain exactly 4 candidates: {path}")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise JudgeError(f"Four-way candidate must be an object: {path}")
        packets.append(FourWayPacket(domain=str(data.get("domain") or path.name.split("_4way_blinded")[0]), candidates=candidates, packet_file=path))
    return packets


def build_pairs(
    comparison_root: Path,
    comparison_dir: Path,
    baseline: str,
    max_pairs: int | None = None,
) -> tuple[list[CandidatePair], list[dict[str, Any]]]:
    candidates = load_blinded_candidates(comparison_dir)
    domain = infer_domain(comparison_dir, comparison_root)
    pairs: list[CandidatePair] = []
    incomplete: list[dict[str, Any]] = []
    for index in range(0, len(candidates), 2):
        if index + 1 >= len(candidates):
            incomplete.append(
                {
                    "comparison_dir": str(comparison_dir),
                    "domain": domain,
                    "candidate_id": candidates[index].get("candidate_id"),
                    "reason": "odd_candidate_without_pair",
                }
            )
            break
        pair_no = (index // 2) + 1
        pairs.append(
            CandidatePair(
                comparison_id=f"{domain}::pair_{pair_no:03d}",
                domain=domain,
                baseline=baseline,
                comparison_dir=comparison_dir,
                candidate_a=candidates[index],
                candidate_b=candidates[index + 1],
            )
        )
    if max_pairs is not None:
        pairs = pairs[:max_pairs]
    return pairs, incomplete


def candidate_for_prompt(label: str, candidate: dict[str, Any]) -> str:
    fields = [
        ("candidate_id", candidate.get("candidate_id")),
        ("title", candidate.get("title")),
        ("problem_statement", candidate.get("problem_statement")),
        ("abstract_or_motivation", candidate.get("abstract_or_motivation")),
        ("proposed_contribution", candidate.get("proposed_contribution")),
        ("evaluation_plan", candidate.get("evaluation_plan")),
        ("risks_or_caveats", candidate.get("risks_or_caveats")),
    ]
    lines = [f"{label}:"]
    for key, value in fields:
        if value is None:
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def independent_candidate_for_prompt(candidate: dict[str, Any]) -> str:
    fields = [
        ("candidate_id", candidate.get("candidate_id")),
        ("title", candidate.get("title")),
        ("problem_statement", candidate.get("problem_statement")),
        ("motivation_or_abstract", candidate.get("motivation_or_abstract") or candidate.get("abstract_or_motivation")),
        ("proposed_direction", candidate.get("proposed_direction") or candidate.get("proposed_contribution")),
        ("expected_contribution", candidate.get("expected_contribution")),
        ("evaluation_plan", candidate.get("evaluation_plan")),
        ("risks_or_caveats", candidate.get("risks_or_caveats")),
        ("source_context_or_grounding", candidate.get("source_context_or_grounding")),
        ("formal_problem_statement", candidate.get("formal_problem_statement")),
        ("assumptions_or_problem_setup", candidate.get("assumptions_or_problem_setup")),
        ("ambiguity_or_missing_definitions", candidate.get("ambiguity_or_missing_definitions")),
    ]
    lines = ["CANDIDATE:"]
    for key, value in fields:
        if value is None:
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def build_judge_prompt(config: dict[str, Any], pair: CandidatePair) -> str:
    criteria = config["rubric"]["criteria"]
    criteria_text = []
    for item in criteria:
        criteria_text.append(
            "\n".join(
                [
                    f"- {item['id']}: {item.get('name', item['id'])}",
                    f"  question: {item.get('question', '')}",
                    f"  score_1: {item.get('score_1', '')}",
                    f"  score_3: {item.get('score_3', '')}",
                    f"  score_5: {item.get('score_5', '')}",
                    *([f"  warning: {item['warning']}"] if item.get("warning") else []),
                ]
            )
        )
    score_ids = rubric_ids(config)
    score_keys = ", ".join(score_ids)
    score_template = ",\n    ".join(f'"{key}": 1' for key in score_ids)
    prompt = f"""You are evaluating candidate research ideas/problems.
You are not determining proven external novelty.
Judge only from the provided candidate text.
Do not reward grand language such as "fundamental," "phase transition," or "impossibility" unless the problem is specific and grounded.
Penalize vague ideas.
Penalize term-soup or excessive combination of unrelated concepts.
Reward clear setting, assumptions, objective, evidence grounding, feasibility, formalizability, and actionability.
Score each criterion from 1 to 5.
Return valid JSON only.

Rubric criteria:
{chr(10).join(criteria_text)}

Return exactly this JSON shape:
{{
  "comparison_id": "{pair.comparison_id}",
  "domain": "{pair.domain}",
  "baseline": "BLINDED_COMPARISON",
  "candidate_a_id": "{pair.candidate_a_id}",
  "candidate_b_id": "{pair.candidate_b_id}",
  "candidate_a_scores": {{
    {score_template}
  }},
  "candidate_b_scores": {{
    {score_template}
  }},
  "pairwise_preference": "CANDIDATE_A | CANDIDATE_B | TIE | CANNOT_JUDGE",
  "confidence": "LOW | MEDIUM | HIGH",
  "rationale": "...",
  "novelty_caveat": "{NOVELTY_CAVEAT}"
}}

The score objects must contain all and only these score keys: {score_keys}.

{candidate_for_prompt("CANDIDATE_A", pair.candidate_a)}

{candidate_for_prompt("CANDIDATE_B", pair.candidate_b)}
"""
    labels = labels_found_in_prompt(prompt)
    if labels:
        raise JudgeError(f"Judge prompt contains method labels: {labels}")
    return prompt


def pairwise_preference_candidate_for_prompt(label: str, candidate: dict[str, Any]) -> str:
    fields = [
        ("title", candidate.get("title")),
        ("problem_statement", candidate.get("problem_statement")),
        ("motivation_or_abstract", candidate.get("motivation_or_abstract") or candidate.get("abstract_or_motivation")),
        ("proposed_direction", candidate.get("proposed_direction") or candidate.get("proposed_contribution")),
        ("expected_contribution", candidate.get("expected_contribution")),
        ("evaluation_plan", candidate.get("evaluation_plan")),
        ("risks_or_caveats", candidate.get("risks_or_caveats")),
        ("source_context_or_grounding", candidate.get("source_context_or_grounding")),
        ("formal_problem_statement", candidate.get("formal_problem_statement")),
        ("assumptions_or_problem_setup", candidate.get("assumptions_or_problem_setup")),
        ("ambiguity_or_missing_definitions", candidate.get("ambiguity_or_missing_definitions")),
    ]
    lines = [f"{label}:"]
    for key, value in fields:
        text = _json_text(value)
        if text != NOT_PROVIDED:
            lines.append(f"- {key}: {text}")
        else:
            lines.append(f"- {key}: {NOT_PROVIDED}")
    return "\n".join(lines)


def build_pairwise_preference_prompt(config: dict[str, Any], pair: PairwisePreferencePair) -> str:
    criteria = ", ".join(PAIRWISE_PREFERENCE_CRITERIA)
    criterion_template = ",\n    ".join(f'"{key}": "A | B | TIE"' for key in PAIRWISE_PREFERENCE_CRITERIA)
    prompt = f"""You are a strict, skeptical senior research reviewer.
Do not be encouraging.
Pick the candidate that a researcher should prioritize for serious follow-up.
Do not infer missing evidence or formalization.
Do not reward polished prose alone.
Do not use external knowledge.
Do not infer method identity.
If both are weak or incomparable, choose TIE or CANNOT_JUDGE.

This is pairwise preference, not numeric scoring.
Do not assign 1-5 scores.
Do not compute a weighted composite score.
Judge novelty potential only from the provided text; do not claim proven external novelty.

Consider these criteria qualitatively:
{criteria}

Return valid JSON only in exactly this shape:
{{
  "pair_id": "{pair.pair_id}",
  "domain": "{pair.domain}",
  "winner": "A | B | TIE | CANNOT_JUDGE",
  "confidence": "LOW | MEDIUM | HIGH",
  "criterion_winners": {{
    {criterion_template}
  }},
  "why_winner": "...",
  "candidate_a_weakness": "...",
  "candidate_b_weakness": "...",
  "novelty_caveat": "{NOVELTY_CAVEAT}"
}}

Candidate A and Candidate B are blinded. Do not mention any method identity.

{pairwise_preference_candidate_for_prompt("Candidate A", pair.candidate_a)}

{pairwise_preference_candidate_for_prompt("Candidate B", pair.candidate_b)}
"""
    labels = labels_found_in_prompt(prompt)
    for label in ("baseline", "baselines"):
        pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){re.escape(label)}(?![A-Za-z0-9_\-])", re.IGNORECASE)
        if pattern.search(prompt):
            labels.append(label)
    if labels:
        raise JudgeError(f"Pairwise preference prompt contains method labels: {labels}")
    if re.search(r"\bscore each criterion from 1 to 5\b", prompt, re.IGNORECASE):
        raise JudgeError("Pairwise preference prompt must not ask for 1-5 scores")
    if "candidate_a_scores" in prompt or "candidate_b_scores" in prompt:
        raise JudgeError("Pairwise preference prompt must not include score objects")
    if "weighted composite" not in prompt:
        raise JudgeError("Pairwise preference prompt must explicitly prohibit weighted composite scores")
    return prompt


def four_way_candidate_for_prompt(candidate: dict[str, Any]) -> str:
    fields = [
        ("candidate_id", candidate.get("candidate_id")),
        ("title", candidate.get("title")),
        ("problem_statement", candidate.get("problem_statement")),
        ("motivation_or_abstract", candidate.get("motivation_or_abstract")),
        ("proposed_direction", candidate.get("proposed_direction")),
        ("expected_contribution", candidate.get("expected_contribution")),
        ("evaluation_plan", candidate.get("evaluation_plan")),
        ("risks_or_caveats", candidate.get("risks_or_caveats")),
        ("source_context_or_grounding", candidate.get("source_context_or_grounding")),
        ("formal_problem_statement", candidate.get("formal_problem_statement")),
        ("assumptions_or_problem_setup", candidate.get("assumptions_or_problem_setup")),
        ("ambiguity_or_missing_definitions", candidate.get("ambiguity_or_missing_definitions")),
    ]
    lines = ["CANDIDATE:"]
    for key, value in fields:
        lines.append(f"- {key}: {_json_text(value)}")
    return "\n".join(lines)


def build_four_way_ranked_prompt(config: dict[str, Any], packet: FourWayPacket) -> str:
    candidate_ids = [str(candidate.get("candidate_id")) for candidate in packet.candidates]
    criteria = "\n".join(f"- {criterion}" for criterion in FOUR_WAY_RANK_CRITERIA)
    criterion_template = ",\n    ".join(
        f'"{criterion}": [{{"candidate_id": "{candidate_ids[0]}", "rank": 1, "reason": "..."}}]'
        for criterion in FOUR_WAY_RANK_CRITERIA
    )
    candidate_blocks = "\n\n".join(four_way_candidate_for_prompt(candidate) for candidate in packet.candidates)
    prompt = f"""You are a strict senior research reviewer.
Compare four blinded research-problem candidates in the same domain.
Do not infer method identity.
Do not use external knowledge.
Novelty means novelty potential from provided text only.
Penalize term-soup.
Penalize missing formalization.
Penalize missing source grounding.
Reward clear problem setup, assumptions, objective, evidence trail, and evaluation path.
Do not produce numeric 1-5 scores.
Do not compute a weighted composite score.
Use ranks only.

Rank candidates for each criterion from 1 to 4:
- rank 1 = best
- rank 4 = worst
- ties are allowed only if genuinely indistinguishable

Criteria:
{criteria}

Candidate IDs: {json.dumps(candidate_ids)}

Return valid JSON only in exactly this shape:
{{
  "domain": "{packet.domain}",
  "candidate_ids": {json.dumps(candidate_ids)},
  "criterion_rankings": {{
    {criterion_template}
  }},
  "best_overall_candidate": {{"candidate_id": "{candidate_ids[0]}", "reason": "..."}},
  "most_auditable_candidate": {{"candidate_id": "{candidate_ids[0]}", "reason": "..."}},
  "most_actionable_candidate": {{"candidate_id": "{candidate_ids[0]}", "reason": "..."}},
  "most_novel_potential_candidate": {{"candidate_id": "{candidate_ids[0]}", "reason": "..."}},
  "confidence": "LOW | MEDIUM | HIGH",
  "domain_level_notes": "...",
  "novelty_caveat": "{NOVELTY_CAVEAT}"
}}

Each criterion ranking must include all four candidate IDs exactly once.
Do not include method labels.
Do not include pairwise preference fields.

BLINDED CANDIDATES:

{candidate_blocks}
"""
    labels = labels_found_in_prompt(prompt)
    for label in ("baseline", "baselines"):
        pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){re.escape(label)}(?![A-Za-z0-9_\-])", re.IGNORECASE)
        if pattern.search(prompt):
            labels.append(label)
    if labels:
        raise JudgeError(f"Four-way ranked prompt contains method labels: {labels}")
    forbidden_bits = ("candidate_a_scores", "candidate_b_scores", "pairwise_preference")
    if any(bit in prompt for bit in forbidden_bits):
        raise JudgeError("Four-way ranked prompt must not include score or pairwise fields")
    return prompt


def build_independent_judge_prompt(config: dict[str, Any], candidate: IndependentCandidate) -> str:
    criteria = config["rubric"]["criteria"]
    criteria_text = []
    for item in criteria:
        criteria_text.append(
            "\n".join(
                [
                    f"- {item['id']}: {item.get('name', item['id'])}",
                    f"  question: {item.get('question', '')}",
                    f"  score_1: {item.get('score_1', '')}",
                    f"  score_3: {item.get('score_3', '')}",
                    f"  score_5: {item.get('score_5', '')}",
                    *([f"  warning: {item['warning']}"] if item.get("warning") else []),
                ]
            )
        )
    score_ids = rubric_ids(config)
    score_keys = ", ".join(score_ids)
    score_template = ",\n    ".join(f'"{key}": 1' for key in score_ids)
    calibration_rules = config.get("calibration_rules", [])
    calibration_text = "\n".join(f"- {rule}" for rule in calibration_rules)
    prompt = f"""You are evaluating one candidate research idea/problem independently.
Do not compare it to another candidate.
Do not infer method identity.
Judge only from the provided candidate text.
Novelty is novelty potential only, not proven external novelty.
Penalize vague ideas.
Penalize term-soup or over-composed ideas.
Reward clear setting, assumptions, objective, feasibility, grounding, formalizability, and actionability.
Score 3 as "reasonable / acceptable."
Score 4 as "strong."
Score 5 is exceptional and rare.
Do not give 5 unless the candidate is unusually clear, grounded, feasible, and specific.
Most plausible ideas should receive 3 or 4, not 5.
Use overall_worth_reading as a broad interest score.
Use pursuit_priority as the stricter headline follow-up score: 3 means worth a quick source check, 4 means worth serious reading, and 5 means top-tier priority.
Score each criterion from 1 to 5.
Return valid JSON only.

Rubric criteria:
{chr(10).join(criteria_text)}

Calibration and penalty rules:
{calibration_text}

Formalizability is not "could maybe be formalized someday." It requires visible formal structure:
- entities/variables,
- assumptions,
- objective or success criterion,
- observations/feedback/evaluation model.

Evidence grounding requires specific source support or provenance in the candidate text.
Generic statements like "based on recent work" are not enough.

For every candidate, identify at least one weakness or uncertainty.

Return exactly this JSON shape:
{{
  "candidate_id": "{candidate.candidate_id}",
  "domain": "{candidate.domain}",
  "scores": {{
    {score_template}
  }},
  "confidence": "LOW | MEDIUM | HIGH",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "score_justification": {{
    "evidence_grounding": "...",
    "formalizability": "...",
    "actionability": "...",
    "pursuit_priority": "...",
    "auditability_overall": "...",
    "overall_worth_reading": "..."
  }},
  "rationale": "...",
  "novelty_caveat": "{NOVELTY_CAVEAT}"
}}

The scores object must contain all and only these score keys: {score_keys}.

{independent_candidate_for_prompt(candidate.candidate)}
"""
    labels = labels_found_in_prompt(prompt)
    for label in ("baseline", "baselines"):
        pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){re.escape(label)}(?![A-Za-z0-9_\-])", re.IGNORECASE)
        if pattern.search(prompt):
            labels.append(label)
    if labels:
        raise JudgeError(f"Judge prompt contains method labels: {labels}")
    if "pairwise_preference" in prompt:
        raise JudgeError("Independent judge prompt must not include pairwise_preference")
    return prompt


def build_batch_calibrated_judge_prompt(config: dict[str, Any], candidates: list[IndependentCandidate]) -> str:
    if not candidates:
        raise JudgeError("No candidates supplied for batch-calibrated scoring")
    domains = sorted({candidate.domain for candidate in candidates})
    domain = domains[0] if len(domains) == 1 else "mixed"
    score_ids = rubric_ids(config)
    score_keys = ", ".join(score_ids)
    score_template = ",\n        ".join(f'"{key}": 1' for key in score_ids)
    candidate_blocks = "\n\n".join(independent_candidate_for_prompt(candidate.candidate) for candidate in candidates)
    prompt = f"""You are a strict, skeptical senior research reviewer evaluating candidate research problems for a machine-learning conference.

Your job is NOT to be encouraging. Your job is to separate genuinely strong research problems from plausible-sounding but generic, vague, over-composed, or weakly grounded ideas.

You will receive multiple blinded candidate ideas. The method that produced each candidate is hidden. Do not try to infer the method. Judge only the candidate text.

Do not use external knowledge or assume external novelty. Do not infer missing evidence, missing formalization, or missing evaluation plans. If a field is absent or says "not provided," treat it as absent.

The candidates are blinded. Method names are hidden. Do not try to infer which method produced a candidate. Do not mention any method identity in your reasoning.

You are evaluating a batch of candidates from the same scientific domain. Read all candidates first. Then score each candidate independently, but calibrate scores across the whole batch. Do not let input order affect scores or rankings. Candidate order is arbitrary.

Important principles:
- You are judging novelty potential only from the provided text. You are not performing an external novelty check.
- Do not reward grand language such as "fundamental," "phase transition," "impossibility," or "boundary" unless the candidate is specific, grounded, and formalizable.
- Penalize vague ideas.
- Penalize ideas that combine many unrelated terms or methods.
- Penalize ideas that lack a clear evaluation path.
- Penalize missing evidence or missing formal structure.
- Reward clear problem setting, assumptions, objective, feasibility, source grounding, and actionability.
- A polished proposal is not automatically a strong research problem.
- A candidate with missing formal problem structure can still be interesting, but should not receive a high formalizability or auditability score.
- Grand words such as "robust" or "causal" should not increase scores unless the candidate is specific, grounded, and actionable.

Use the full 1-5 scale.

Score anchors:
1 = poor / not useful
2 = weak / probably skip
3 = reasonable / worth a quick source check
4 = strong / worth serious reading
5 = exceptional / top-tier candidate worth prioritizing immediately

Calibration rules:
- Score 3 is the default for a plausible but ordinary idea.
- Score 4 means clearly above average in this batch.
- Score 5 must be rare. It should be used only for the strongest candidate(s) in the batch.
- If many candidates seem good, distinguish them using specificity, grounding, formalizability, and actionability.
- For pursuit_priority, do not give every candidate 4 or 5. Rank the candidates by how strongly a researcher should prioritize them.
- Do not give all or most candidates 4s or 5s.
- It is normal for many plausible ideas to receive 2s or 3s.

You must enforce the cap rules below. These are not suggestions.

Hard cap rules:
- If no concrete source papers, context items, or evidence trail are provided, evidence_grounding must be <= 2.
- If evidence is generic but not tied to specific papers/context, evidence_grounding must be <= 3.
- Do not treat a fluent motivation paragraph as evidence.
- If variables/entities, assumptions, objective, or observation/evaluation model are not explicit, formalizability must be <= 3.
- If the candidate only gives a broad direction without a formal skeleton, formalizability must be <= 2.
- Do not infer formal structure that is not written.
- If no theorem, algorithm, benchmark, dataset, experiment, or source-reading path is clear, actionability must be <= 3.
- If the problem is too broad to investigate in a single project or lacks a realistic evaluation path, feasibility must be <= 3.
- If the proposal depends on undefined or unobservable quantities, feasibility must be <= 3 unless it explains how they are measured or estimated.
- If the idea is mainly "apply known method X to setting Y," "test X under condition Y," or "combine two known techniques," non_incrementality must be <= 3.
- If the idea combines many unrelated motifs, methods, assumptions, and application areas without one crisp research question, low_term_soup must be <= 2.
- If the idea contains multiple independent research agendas in one proposal, low_term_soup must be <= 2.
- If evidence_grounding <= 2 and formalizability <= 3, pursuit_priority should usually be <= 3 unless you explicitly justify an exception.
- If feasibility <= 2, pursuit_priority should usually be <= 3.
- If actionability <= 2, pursuit_priority should usually be <= 3.
- pursuit_priority = 5 is reserved for the strongest one or two candidates in the batch, and only if they are exceptional.
- If both evidence grounding and formalizability are weak, auditability_overall must be <= 3.
- Do not reward a candidate as auditable merely because it is well written.

Novelty:
- Judge novelty_potential only from the provided text.
- Do not claim the idea is externally novel.
- If the idea sounds like a common direction in the field, novelty_potential should usually be 2 or 3.
- If novelty depends on a specific assumption shift, boundary, impossibility, or underexplored regime, that shift must be explicit.

Criteria to score, each 1-5:
1. clarity_specificity
2. significance
3. novelty_potential
4. feasibility
5. evidence_grounding
6. formalizability
7. non_incrementality
8. actionability
9. low_term_soup
10. overall_worth_reading
11. pursuit_priority
12. auditability_overall

Definitions:
- overall_worth_reading: Would this be worth reading source papers for?
- pursuit_priority: How strongly should a researcher prioritize this idea for serious follow-up?
- auditability_overall: How easy is it to audit the idea's evidence trail and problem structure from the provided text?

Before scoring, perform this checklist for each candidate:
- Does it provide concrete source grounding?
- Does it provide a formal problem skeleton?
- Does it state assumptions or an assumption shift?
- Does it state an objective or success criterion?
- Does it state an evaluation or validation path?
- Does it contain too many loosely connected concepts?
- What is the strongest reason to pursue it?
- What is the strongest reason to doubt it?

Every candidate must have at least one weakness. If you cannot identify a weakness, you are being too generous.

Return valid JSON only.

Output schema:

{{
  "domain": "{domain}",
  "batch_size": {len(candidates)},
  "calibration_notes": "...",
  "candidates": [
    {{
      "candidate_id": "...",
      "pre_score_checklist": {{
        "concrete_source_grounding": "YES | PARTIAL | NO",
        "formal_problem_skeleton": "YES | PARTIAL | NO",
        "clear_assumptions_or_shift": "YES | PARTIAL | NO",
        "clear_objective_or_success_criterion": "YES | PARTIAL | NO",
        "clear_evaluation_path": "YES | PARTIAL | NO",
        "term_soup_or_overcomposed": "YES | PARTIAL | NO"
      }},
      "scores": {{
        {score_template}
      }},
      "rank_in_batch": 1,
      "confidence": "LOW | MEDIUM | HIGH",
      "strengths": ["..."],
      "weaknesses": ["..."],
      "cap_rules_triggered": ["..."],
      "cap_exceptions": ["Only include if you intentionally exceeded a usual cap; otherwise empty list."],
      "rationale": "...",
      "novelty_caveat": "{NOVELTY_CAVEAT}"
    }}
  ]
}}

Requirements:
- The scores object must contain all and only these score keys: {score_keys}.
- Every candidate must have at least one weakness.
- rank_in_batch must rank candidates from best to worst by pursuit_priority and overall quality.
- rank_in_batch must not simply mirror input order.
- Do not assign the same rank to all candidates.
- Do not compute a weighted composite score.
- Do not include method labels.
- Return exactly {len(candidates)} candidate score objects, one for each provided candidate_id.

BLINDED CANDIDATES:

{candidate_blocks}
"""
    labels = labels_found_in_prompt(prompt)
    for label in ("baseline", "baselines"):
        pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){re.escape(label)}(?![A-Za-z0-9_\-])", re.IGNORECASE)
        if pattern.search(prompt):
            labels.append(label)
    if labels:
        raise JudgeError(f"Batch-calibrated judge prompt contains method labels: {labels}")
    if "pairwise_preference" in prompt:
        raise JudgeError("Batch-calibrated judge prompt must not include pairwise_preference")
    return prompt


def role_based_candidate_for_prompt(candidate: dict[str, Any]) -> str:
    fields = [
        ("candidate_id", candidate.get("candidate_id")),
        ("domain", candidate.get("domain")),
        ("title", candidate.get("title")),
        ("problem_statement", candidate.get("problem_statement")),
        ("motivation_or_abstract", candidate.get("motivation_or_abstract") or candidate.get("abstract_or_motivation")),
        ("proposed_direction", candidate.get("proposed_direction") or candidate.get("proposed_contribution")),
        ("expected_contribution", candidate.get("expected_contribution")),
        ("evaluation_plan", candidate.get("evaluation_plan")),
        ("risks_or_caveats", candidate.get("risks_or_caveats")),
        ("source_context_or_grounding", candidate.get("source_context_or_grounding")),
        ("formal_problem_statement", candidate.get("formal_problem_statement")),
        ("assumptions_or_problem_setup", candidate.get("assumptions_or_problem_setup")),
        ("ambiguity_or_missing_definitions", candidate.get("ambiguity_or_missing_definitions")),
        ("term_soup_flag", candidate.get("term_soup_flag")),
    ]
    lines = ["BLINDED CANDIDATE:"]
    for key, value in fields:
        lines.append(f"- {key}: {_json_text(value)}")
    return "\n".join(lines)


def role_prompt_specifics(role_id: str) -> tuple[str, str]:
    if role_id == "scientific_merit_reviewer":
        return (
            "Judge scientific merit and priority.",
            """Scores:
- clarity_specificity_10: Is the problem clear and specific?
- significance_10: Would solving it matter scientifically?
- novelty_potential_10: Does it look underexplored from the provided text only?
- feasibility_10: Can it plausibly be studied with current theory or experiments?
- actionability_10: Is there a clear theorem, algorithm, benchmark, dataset, experiment, or source-reading path?
- research_priority_10: How strongly should a researcher prioritize serious follow-up?

Score anchors:
- 0-2 poor
- 3-4 weak
- 5-6 plausible / average
- 7 strong
- 8 very strong
- 9-10 exceptional

Caps:
- If no clear evaluation or next-step path, actionability_10 <= 5.
- If feasibility is weak, research_priority_10 <= 6.
- If the idea is mostly generic/common direction, novelty_potential_10 <= 5.""",
        )
    if role_id == "formalization_reviewer":
        return (
            "Judge formal problem structure only.",
            """Scores:
- formalizability_10: Can the provided text already be cast as a formal problem?
- assumption_clarity_10: Are assumptions or the assumption shift explicit?
- objective_clarity_10: Is the objective or success criterion explicit?
- evaluation_model_clarity_10: Is the observation, feedback, evaluation, or measurement model explicit?

Score anchors:
- 0-2 poor
- 3-4 weak
- 5-6 plausible / average
- 7 strong
- 8 very strong
- 9-10 exceptional

Caps:
- If no formal_problem_statement or it says "not provided," formalizability_10 <= 5.
- If variables/entities are not explicit, formalizability_10 <= 6.
- If assumptions/objective/evaluation model are missing, corresponding scores <= 5.
- Do not infer a formalization that is not written.""",
        )
    if role_id == "evidence_auditability_reviewer":
        return (
            "Judge evidence grounding, traceability, auditability, and scope control.",
            """Scores:
- evidence_grounding_10: Is there concrete source/context evidence in the candidate text?
- source_traceability_10: Can the evidence trail be followed to specific papers, source IDs, or context items?
- auditability_10: Can a reader audit both the source trail and problem structure?
- low_term_soup_10: Is the idea focused rather than over-composed? Higher means lower term-soup risk.

Score anchors:
- 0-2 poor
- 3-4 weak
- 5-6 plausible / average
- 7 strong
- 8 very strong
- 9-10 exceptional

Caps:
- If no concrete source papers, evidence trail, or context items are provided, evidence_grounding_10 <= 4.
- If source evidence is generic, evidence_grounding_10 <= 6.
- If no traceable support/context, source_traceability_10 <= 4.
- If formal structure and evidence trail are both weak, auditability_10 <= 5.
- If candidate combines many unrelated concepts, low_term_soup_10 <= 4.""",
        )
    raise JudgeError(f"Unknown role_id: {role_id}")


def build_role_based_judge_prompt(
    config: dict[str, Any],
    candidate: IndependentCandidate,
    role_id: str,
    *,
    retry_feedback: list[str] | None = None,
) -> str:
    score_ids = role_score_ids(config, role_id)
    score_template = ",\n    ".join(f'"{key}": 0' for key in score_ids)
    role_title, role_specific = role_prompt_specifics(role_id)
    retry_text = ""
    if retry_feedback:
        retry_text = (
            "\n\nYour previous response violated these hard cap or schema rules. "
            "Return a corrected JSON object; do not explain outside JSON.\n"
            + "\n".join(f"- {item}" for item in retry_feedback)
        )
    prompt = f"""You are a strict, skeptical senior ML conference reviewer.
You are not being encouraging.
Judge only the provided candidate text.
Do not use external knowledge.
Do not claim proven novelty.
Do not infer missing evidence, missing variables, missing assumptions, or missing evaluation plans.
If a field says "not provided," treat it as absent.
A polished idea is not automatically strong.
Score 5/10 as average-plausible.
Score 7/10 as strong.
Score 8/10 as very strong.
Score 9-10/10 as exceptional and rare.
It is normal to give 3-6 scores.
Do not give all candidates high scores.
Every candidate must have at least one weakness.
Novelty is novelty potential from provided text only.
Do not compute a weighted composite score.
Do not include method labels.
Do not make pairwise comparisons.

Role: {role_id}
Role task: {role_title}

{role_specific}

Return valid JSON only in exactly this shape:
{{
  "candidate_id": "{candidate.candidate_id}",
  "domain": "{candidate.domain}",
  "role_id": "{role_id}",
  "scores": {{
    {score_template}
  }},
  "confidence": "LOW | MEDIUM | HIGH",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "rationale": "...",
  "novelty_caveat": "{NOVELTY_CAVEAT}"
}}

The scores object must contain all and only these score keys: {", ".join(score_ids)}.
All scores must be integers from 0 to 10.
{retry_text}

{role_based_candidate_for_prompt(candidate.candidate)}
"""
    labels = labels_found_in_prompt(prompt)
    for label in ("baseline", "baselines"):
        pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){re.escape(label)}(?![A-Za-z0-9_\-])", re.IGNORECASE)
        if pattern.search(prompt):
            labels.append(label)
    if labels:
        raise JudgeError(f"Role-based judge prompt contains method labels: {labels}")
    if "pairwise_preference" in prompt:
        raise JudgeError("Role-based judge prompt must not include pairwise_preference")
    return prompt


def formulation_quality_candidate_for_prompt(candidate: dict[str, Any]) -> str:
    fields = [
        ("candidate_id", candidate.get("candidate_id")),
        ("domain", candidate.get("domain")),
        ("title", candidate.get("title")),
        ("problem_statement", candidate.get("problem_statement")),
        ("motivation_or_abstract", candidate.get("motivation_or_abstract")),
        ("proposed_direction", candidate.get("proposed_direction")),
        ("expected_contribution", candidate.get("expected_contribution")),
        ("evaluation_plan", candidate.get("evaluation_plan")),
        ("risks_or_caveats", candidate.get("risks_or_caveats")),
        ("source_context_or_grounding", candidate.get("source_context_or_grounding")),
        ("formal_problem_statement", candidate.get("formal_problem_statement")),
        ("assumptions_or_problem_setup", candidate.get("assumptions_or_problem_setup")),
        ("ambiguity_or_missing_definitions", candidate.get("ambiguity_or_missing_definitions")),
    ]
    lines = ["BLINDED CANDIDATE:"]
    for key, value in fields:
        lines.append(f"- {key}: {_json_text(value)}")
    return "\n".join(lines)


def build_formulation_quality_judge_prompt(
    config: dict[str, Any],
    candidate: IndependentCandidate,
    *,
    retry_feedback: list[str] | None = None,
) -> str:
    score_template = ",\n    ".join(f'"{key}": 0' for key in FORMULATION_QUALITY_CRITERIA)
    retry_text = ""
    if retry_feedback:
        retry_text = (
            "\n\nYour previous response violated these hard cap or schema rules. "
            "Return a corrected JSON object; do not explain outside JSON.\n"
            + "\n".join(f"- {item}" for item in retry_feedback)
        )
    prompt = f"""You are a strict, skeptical senior ML reviewer evaluating the quality of research-problem formulations.

Your task is not to judge whether the prose sounds polished. Your task is to judge whether the candidate is a well-posed, technically sharp, source-grounded, feasible research problem formulation.

Judge only the provided text. Do not use external knowledge. Do not claim proven novelty. If a field says "not provided," treat it as missing.

A fluent idea without formal structure should not receive a high formulation-quality score.

Score anchors:
0-2 = poor / not a usable research-problem formulation
3-4 = weak / vague / major missing pieces
5-6 = plausible but needs substantial refinement
7-8 = strong formulation, worth serious source-paper reading
9-10 = exceptional, unusually precise and compelling

Criteria:
- well_posedness: Does it define entities, variables, assumptions, objective, and observation/evaluation setting?
- technical_sharpness: Is the research question precise enough to support a theorem, algorithm, benchmark, or experiment?
- meaningful_assumption_shift: Does it identify a substantive assumption change, failure boundary, or mechanism?
- nontriviality: Is it more than a small variant or "apply X to Y"?
- domain_fit: Does it fit the target domain?
- source_grounded_specificity: Is it motivated by concrete papers, gaps, or context?
- feasibility: Can it realistically be studied?
- scope_control: Is it focused rather than term-soup?
- ambiguity_hygiene: Are vague terms or missing definitions acknowledged honestly?
- overall_formulation_quality: Overall quality of the research-problem formulation.

Hard caps:
- If formal_problem_statement is "not provided," well_posedness <= 6 and overall_formulation_quality <= 7.
- If assumptions_or_problem_setup is "not provided," well_posedness <= 6.
- If source_context_or_grounding is "not provided," source_grounded_specificity <= 4.
- If ambiguity_or_missing_definitions is "not provided," ambiguity_hygiene <= 6.
- If evaluation_plan is "not provided," feasibility <= 6.
- If the candidate is mostly a broad direction without formal skeleton, technical_sharpness <= 5.
- If the candidate combines many loosely related concepts, scope_control <= 4.
- If source grounding and formal structure are both weak, overall_formulation_quality <= 6.

Do not infer missing formalization or missing evidence.
Do not reward grand terms like "fundamental," "phase transition," "impossibility," or "boundary" unless the formulation is actually precise and grounded.
Do not run pairwise comparison.
Do not compute a weighted composite score.
Do not include method labels.
Every candidate must have at least one weakness.

Return valid JSON only in exactly this shape:
{{
  "candidate_id": "{candidate.candidate_id}",
  "domain": "{candidate.domain}",
  "scores": {{
    {score_template}
  }},
  "recommended_action": "READ_FIRST | PROMISING_NEEDS_REFINEMENT | NEEDS_REFRAMING | DROP_OR_DEPRIORITIZE",
  "confidence": "LOW | MEDIUM | HIGH",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "rationale": "...",
  "novelty_caveat": "{NOVELTY_CAVEAT}"
}}

The scores object must contain all and only these score keys: {", ".join(FORMULATION_QUALITY_CRITERIA)}.
All scores must be integers from 0 to 10.
{retry_text}

{formulation_quality_candidate_for_prompt(candidate.candidate)}
"""
    labels = labels_found_in_prompt(prompt)
    for label in ("baseline", "baselines"):
        pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){re.escape(label)}(?![A-Za-z0-9_\-])", re.IGNORECASE)
        if pattern.search(prompt):
            labels.append(label)
    if labels:
        raise JudgeError(f"Formulation-quality judge prompt contains method labels: {labels}")
    if "pairwise_preference" in prompt:
        raise JudgeError("Formulation-quality judge prompt must not include pairwise_preference")
    return prompt


def formulation_only_candidate_for_prompt(candidate: dict[str, Any]) -> str:
    fields = [
        ("candidate_id", candidate.get("candidate_id")),
        ("domain", candidate.get("domain")),
        ("title", candidate.get("title")),
        ("problem_statement", candidate.get("problem_statement")),
        ("motivation_or_abstract", candidate.get("motivation_or_abstract")),
        ("formal_problem_statement", candidate.get("formal_problem_statement")),
        ("assumptions_or_problem_setup", candidate.get("assumptions_or_problem_setup")),
        ("ambiguity_or_missing_definitions", candidate.get("ambiguity_or_missing_definitions")),
        ("source_context_or_grounding", candidate.get("source_context_or_grounding")),
    ]
    lines = ["BLINDED CANDIDATE:"]
    for key, value in fields:
        lines.append(f"- {key}: {_json_text(value)}")
    return "\n".join(lines)


def build_formulation_only_judge_prompt(
    config: dict[str, Any],
    candidate: IndependentCandidate,
    *,
    retry_feedback: list[str] | None = None,
) -> str:
    score_template = ",\n    ".join(f'"{key}": 0' for key in FORMULATION_ONLY_CRITERIA)
    retry_text = ""
    if retry_feedback:
        retry_text = (
            "\n\nYour previous response violated these hard cap or schema rules. "
            "Return a corrected JSON object; do not explain outside JSON.\n"
            + "\n".join(f"- {item}" for item in retry_feedback)
        )
    prompt = f"""You are a strict, skeptical senior research reviewer evaluating research-problem formulation quality only.

Your task is to judge the formulation as a problem statement, not as a project plan.
Do not evaluate implementation plans, experiments, software engineering details, or actionability except where they clarify the formulation itself.
Do not reward a candidate for having a polished plan if the underlying research problem is vague or poorly posed.
Judge only the provided blinded candidate text. Do not use external knowledge. Do not claim proven novelty.
Novelty means novelty potential from the provided text only.
If a field says "not provided," treat it as missing. Do not infer missing variables, assumptions, evidence, or definitions.

Score anchors:
0-2 = poor / not a usable research-problem formulation
3-4 = weak / vague / major missing pieces
5-6 = plausible but needs substantial refinement
7-8 = strong research-problem formulation
9-10 = exceptional, unusually precise and compelling

Criteria:
- problem_definition_clarity_10: Is the core research problem clear, bounded, and stated as a problem rather than a broad topic?
- technical_specificity_10: Are the technical objects, setting, and question specific enough to support rigorous follow-up?
- well_posedness_10: Does the text define entities or variables, assumptions, objective, and observation or evidence setting?
- assumption_boundary_clarity_10: Is the assumption shift, failure boundary, or regime distinction explicit?
- formalizability_10: Can the provided text already be cast as a formal problem without inventing major missing details?
- nontriviality_10: Is the formulation more than a minor variant, "apply X to Y," or routine stress test?
- scope_control_10: Is it focused rather than a loose bundle of many concepts?
- source_grounded_specificity_10: Is it motivated by concrete source papers, source IDs, gaps, or context items?
- ambiguity_hygiene_10: Does it acknowledge missing definitions or ambiguous terms honestly?
- overall_formulation_quality_10: Overall strength of the research-problem formulation.

Hard caps:
- If the problem is vague, overall_formulation_quality_10 must be <= 6.
- If formal_problem_statement is "not provided," well_posedness_10 <= 6 and formalizability_10 <= 6.
- If assumptions_or_problem_setup is "not provided," well_posedness_10 <= 6 and assumption_boundary_clarity_10 <= 6.
- If ambiguity_or_missing_definitions is "not provided," ambiguity_hygiene_10 <= 6.
- If source_context_or_grounding is "not provided," source_grounded_specificity_10 <= 4.
- If the candidate combines many loosely related concepts, scope_control_10 <= 4.
- If the idea is mainly "apply X to Y," "test X under condition Y," or "combine known technique X with setting Y," nontriviality_10 <= 6.
- If there is no clear formal skeleton, overall_formulation_quality_10 <= 7.

Do not run pairwise comparison.
Do not compute a weighted composite score.
Do not include hidden method labels.
Every candidate must have at least one weakness.

Return valid JSON only in exactly this shape:
{{
  "candidate_id": "{candidate.candidate_id}",
  "domain": "{candidate.domain}",
  "scores": {{
    {score_template}
  }},
  "recommended_action": "READ_FIRST | PROMISING_NEEDS_REFINEMENT | NEEDS_REFRAMING | DROP_OR_DEPRIORITIZE",
  "confidence": "LOW | MEDIUM | HIGH",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "rationale": "...",
  "novelty_caveat": "{NOVELTY_CAVEAT}"
}}

The scores object must contain all and only these score keys: {", ".join(FORMULATION_ONLY_CRITERIA)}.
All scores must be integers from 0 to 10.
{retry_text}

{formulation_only_candidate_for_prompt(candidate.candidate)}
"""
    labels = labels_found_in_prompt(prompt)
    for label in ("baseline", "baselines"):
        pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){re.escape(label)}(?![A-Za-z0-9_\-])", re.IGNORECASE)
        if pattern.search(prompt):
            labels.append(label)
    if labels:
        raise JudgeError(f"Formulation-only judge prompt contains method labels: {labels}")
    if "pairwise_preference" in prompt:
        raise JudgeError("Formulation-only judge prompt must not include pairwise_preference")
    return prompt


def personalized_formulation_candidate_for_prompt(candidate: dict[str, Any]) -> str:
    fields = [
        ("candidate_id", candidate.get("candidate_id")),
        ("profile", candidate.get("profile")),
        ("profile_context", candidate.get("profile_context")),
        ("title", candidate.get("title")),
        ("problem_statement", candidate.get("problem_statement")),
        ("motivation_or_abstract", candidate.get("motivation_or_abstract")),
        ("formal_problem_statement", candidate.get("formal_problem_statement")),
        ("assumptions_or_problem_setup", candidate.get("assumptions_or_problem_setup")),
        ("ambiguity_or_missing_definitions", candidate.get("ambiguity_or_missing_definitions")),
        ("source_context_or_grounding", candidate.get("source_context_or_grounding")),
        ("supporting_papers", candidate.get("supporting_papers")),
    ]
    lines = ["BLINDED PERSONALIZED CANDIDATE:"]
    for key, value in fields:
        lines.append(f"- {key}: {_json_text(value)}")
    return "\n".join(lines)


def build_personalized_formulation_judge_prompt(
    config: dict[str, Any],
    candidate: IndependentCandidate,
    *,
    retry_feedback: list[str] | None = None,
) -> str:
    score_template = ",\n    ".join(f'"{key}": 0' for key in PERSONALIZED_FORMULATION_CRITERIA)
    retry_text = ""
    if retry_feedback:
        retry_text = (
            "\n\nYour previous response violated these hard cap or schema rules. "
            "Return a corrected JSON object; do not explain outside JSON.\n"
            + "\n".join(f"- {item}" for item in retry_feedback)
        )
    profile = _json_text(candidate.candidate.get("profile"))
    prompt = f"""You are a strict, skeptical senior research reviewer evaluating personalized research-problem formulations.

Your task is to judge both formulation quality and personalization quality.
Judge profile alignment only from the provided profile context and the candidate text. Do not use external knowledge about the researcher.
If a field says "not provided," treat it as missing. Do not infer missing source evidence, variables, assumptions, or profile context.
Do not reward name-dropping. Do not require explicit fields such as profile_fit_claim, why_not_generic, profile_alignment_evidence, or a Profile Fit section, because older personalized outputs may not contain those fields.
A good personalized problem connects to artifact-supported profile themes, source/corpus evidence, and profile-relevant technical style while formulating a meaningful next problem.
Penalize generic problems that could apply to many researchers in the area.
Penalize off-profile problems even if they are technically coherent.
If profile context is thin, lower confidence rather than automatically assigning a low score.
Do not claim proven external novelty.

Score anchors:
0-2 = poor
3-4 = weak
5-6 = plausible but needs substantial refinement
7-8 = strong
9-10 = exceptional

Formulation criteria:
- problem_definition_clarity_10: Is the core research problem clear, bounded, and stated as a problem rather than a broad topic?
- technical_specificity_10: Are the technical objects, setting, and question specific enough to support rigorous follow-up?
- well_posedness_10: Does the text define entities or variables, assumptions, objective, and observation or evidence setting?
- assumption_boundary_clarity_10: Is the assumption shift, failure boundary, or regime distinction explicit?
- formalizability_10: Can the provided text already be cast as a formal problem without inventing major missing details?
- nontriviality_10: Is the formulation more than a minor variant, "apply X to Y," or routine stress test?
- scope_control_10: Is it focused rather than a loose bundle of many concepts?
- source_grounded_specificity_10: Is it motivated by concrete source papers, source IDs, gaps, or context items?
- ambiguity_hygiene_10: Does it acknowledge missing definitions or ambiguous terms honestly?
- overall_formulation_quality_10: Overall strength of the research-problem formulation.

Personalization criteria:
- profile_alignment_10: Does the problem align with the target profile's artifact-supported research themes?
- profile_specificity_10: Is the problem specifically tailored to the profile context, source/corpus themes, or seed evidence, rather than a generic ML problem?
- intellectual_style_match_10: Does the formulation match the apparent research style in the provided context, such as theory, systems, representation learning, optimization, neural computation, cognitive framing, or statistical ML?
- profile_novelty_fit_10: Does the problem extend the provided profile context in a plausible new direction rather than merely repeating known themes or drifting off-profile?
- personalization_overall_10: Overall quality of personalization.

Personalization interpretation:
- 5-6: broadly plausible fit to the provided profile context.
- 7-8: strong profile-context alignment with specific thematic/style/source evidence.
- 9-10: exceptional personalization, highly profile-specific and well grounded.
- Infer profile alignment from whether the technical area matches provided themes, whether source papers or selected-corpus themes support the profile connection, whether the style matches the provided context, whether the problem is motivated by profile-associated evidence, and whether it would be less fitting for a generic ML researcher.

Hard caps:
- If no profile context is provided, personalization_overall_10 <= 5.
- If the problem could apply equally to many researchers and has no profile-specific signal, profile_specificity_10 <= 5.
- If the candidate only name-drops the profile, profile_alignment_10 <= 4.
- If the candidate is off-theme relative to the provided profile context, personalization_overall_10 <= 5.
- If source_context_or_grounding is "not provided," source_grounded_specificity_10 <= 4.
- If formal_problem_statement is "not provided," well_posedness_10 <= 6 and formalizability_10 <= 6.
- If assumptions_or_problem_setup is "not provided," well_posedness_10 <= 6.
- If ambiguity_or_missing_definitions is "not provided," ambiguity_hygiene_10 <= 6.

Do not run pairwise comparison.
Do not compute a weighted composite score.
Do not include hidden method labels.
Every candidate must have at least one weakness.

Return valid JSON only in exactly this shape:
{{
  "candidate_id": "{candidate.candidate_id}",
  "profile": "{profile}",
  "scores": {{
    {score_template}
  }},
  "recommended_action": "READ_FIRST | PROMISING_NEEDS_REFINEMENT | NEEDS_REFRAMING | DROP_OR_DEPRIORITIZE",
  "confidence": "LOW | MEDIUM | HIGH",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "rationale": "...",
  "personalization_caveat": "{PERSONALIZATION_CAVEAT}",
  "novelty_caveat": "{NOVELTY_CAVEAT}"
}}

The scores object must contain all and only these score keys: {", ".join(PERSONALIZED_FORMULATION_CRITERIA)}.
All scores must be integers from 0 to 10.
{retry_text}

{personalized_formulation_candidate_for_prompt(candidate.candidate)}
"""
    labels = labels_found_in_prompt(prompt)
    for label in ("baseline", "baselines"):
        pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){re.escape(label)}(?![A-Za-z0-9_\-])", re.IGNORECASE)
        if pattern.search(prompt):
            labels.append(label)
    if labels:
        raise JudgeError(f"Personalized formulation judge prompt contains method labels: {labels}")
    if "pairwise_preference" in prompt:
        raise JudgeError("Personalized formulation judge prompt must not include pairwise_preference")
    return prompt


def prism_idea_quality_candidate_for_prompt(candidate: dict[str, Any]) -> str:
    fields = [
        ("candidate_id", candidate.get("candidate_id")),
        ("domain", candidate.get("domain")),
        ("title", candidate.get("title")),
        ("problem_statement", candidate.get("problem_statement")),
        ("motivation_or_abstract", candidate.get("motivation_or_abstract")),
        ("proposed_direction", candidate.get("proposed_direction")),
        ("expected_contribution", candidate.get("expected_contribution")),
        ("evaluation_plan", candidate.get("evaluation_plan")),
        ("risks_or_caveats", candidate.get("risks_or_caveats")),
        ("source_context_or_grounding", candidate.get("source_context_or_grounding")),
        ("formal_problem_statement", candidate.get("formal_problem_statement")),
        ("assumptions_or_problem_setup", candidate.get("assumptions_or_problem_setup")),
        ("ambiguity_or_missing_definitions", candidate.get("ambiguity_or_missing_definitions")),
    ]
    lines = ["BLINDED CANDIDATE:"]
    for key, value in fields:
        lines.append(f"- {key}: {_json_text(value)}")
    return "\n".join(lines)


def build_prism_idea_quality_judge_prompt(
    config: dict[str, Any],
    candidate: IndependentCandidate,
    *,
    retry_feedback: list[str] | None = None,
) -> str:
    score_template = ",\n    ".join(f'"{key}": 1' for key in PRISM_IDEA_QUALITY_CRITERIA)
    retry_text = ""
    if retry_feedback:
        retry_text = (
            "\n\nYour previous response violated these schema rules. "
            "Return a corrected JSON object; do not explain outside JSON.\n"
            + "\n".join(f"- {item}" for item in retry_feedback)
        )
    prompt = f"""You are a strict, skeptical senior ML reviewer evaluating generated research problems with a PRISM/LiveIdeaBench-style idea-quality rubric.

Judge only the provided blinded candidate text. Do not use external knowledge. Do not claim proven novelty.
Novelty/originality means novelty potential from the provided text only.
A polished proposal is not automatically strong.
Penalize vague ideas, term-soup, missing feasibility, missing evaluation paths, weak source grounding, and weak traceability.
Do not force any hidden method to win.
Keep method labels hidden during scoring.
Do not run pairwise comparison.
Do not compute a weighted composite score.

Score anchors:
1-2 = poor
3-4 = weak
5-6 = plausible / average
7-8 = strong
9-10 = exceptional and rare

Rubric axes:
- novelty_originality: Does the problem appear non-obvious or underexplored from the provided text?
- feasibility: Can the problem realistically be investigated with current methods/resources?
- potential_impact: If solved, would it meaningfully advance the field?
- clarity_coherence: Is the problem understandable, focused, and coherent?
- actionability: Is there a clear next theorem, experiment, benchmark, implementation, or source-reading path?
- groundedness: Is the problem motivated by concrete papers, gaps, evidence, or provided context?
- traceability_auditability: Can a reader reconstruct why this problem was proposed from the provided evidence/context?
- non_redundancy_scope_control: Is the problem distinct, focused, and not term-soup or duplicative?

Return valid JSON only in exactly this shape:
{{
  "candidate_id": "{candidate.candidate_id}",
  "domain": "{candidate.domain}",
  "scores": {{
    {score_template}
  }},
  "recommended_action": "READ_FIRST | PROMISING_NEEDS_REFINEMENT | NEEDS_REFRAMING | DROP_OR_DEPRIORITIZE",
  "confidence": "LOW | MEDIUM | HIGH",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "rationale": "...",
  "novelty_caveat": "{PRISM_NOVELTY_CAVEAT}"
}}

The scores object must contain all and only these score keys: {", ".join(PRISM_IDEA_QUALITY_CRITERIA)}.
All scores must be integers from 1 to 10.
Every candidate must have at least one weakness.
Do not include method labels in strengths, weaknesses, or rationale.
{retry_text}

{prism_idea_quality_candidate_for_prompt(candidate.candidate)}
"""
    labels = labels_found_in_prompt(prompt)
    for label in ("baseline", "baselines"):
        pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){re.escape(label)}(?![A-Za-z0-9_\-])", re.IGNORECASE)
        if pattern.search(prompt):
            labels.append(label)
    if labels:
        raise JudgeError(f"PRISM idea-quality judge prompt contains method labels: {labels}")
    if "pairwise_preference" in prompt:
        raise JudgeError("PRISM idea-quality judge prompt must not include pairwise_preference")
    return prompt


def labels_found_in_prompt(prompt: str) -> list[str]:
    found = []
    for label in FORBIDDEN_PROMPT_LABELS:
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(label)}(?![A-Za-z0-9_])", re.IGNORECASE)
        if pattern.search(prompt):
            found.append(label)
    return found


def validate_score_object(
    value: dict[str, Any],
    *,
    pair: CandidatePair,
    config: dict[str, Any],
) -> dict[str, Any]:
    ids = rubric_ids(config)
    min_score = int(config["evaluation"].get("score_scale_min", 1))
    max_score = int(config["evaluation"].get("score_scale_max", 5))
    for side in ("candidate_a_scores", "candidate_b_scores"):
        scores = value.get(side)
        if not isinstance(scores, dict):
            raise JudgeError(f"{side} must be an object")
        missing = [key for key in ids if key not in scores]
        extra = [key for key in scores if key not in ids]
        if missing or extra:
            raise JudgeError(f"{side} score keys mismatch; missing={missing}, extra={extra}")
        for key in ids:
            score = scores[key]
            if not isinstance(score, int) or isinstance(score, bool):
                raise JudgeError(f"{side}.{key} must be an integer")
            if not min_score <= score <= max_score:
                raise JudgeError(f"{side}.{key}={score} outside {min_score}-{max_score}")
    pref = value.get("pairwise_preference")
    if pref not in preference_options(config):
        raise JudgeError(f"Invalid pairwise_preference: {pref}")
    conf = value.get("confidence")
    if conf not in confidence_options(config):
        raise JudgeError(f"Invalid confidence: {conf}")
    if config["evaluation"].get("require_rationale", True) and not value.get("rationale"):
        raise JudgeError("rationale is required")
    if config["evaluation"].get("require_confidence", True) and not value.get("confidence"):
        raise JudgeError("confidence is required")
    value["comparison_id"] = pair.comparison_id
    value["domain"] = pair.domain
    value["baseline"] = pair.baseline
    value["candidate_a_id"] = pair.candidate_a_id
    value["candidate_b_id"] = pair.candidate_b_id
    value["comparison_dir"] = str(pair.comparison_dir)
    value.setdefault("novelty_caveat", NOVELTY_CAVEAT)
    if "weighted_composite" in json.dumps(value).lower():
        raise JudgeError("Weighted composite score is not allowed")
    return value


def validate_pairwise_preference_object(
    value: dict[str, Any],
    *,
    pair: PairwisePreferencePair,
    config: dict[str, Any],
) -> dict[str, Any]:
    if "scores" in value or "candidate_a_scores" in value or "candidate_b_scores" in value:
        raise JudgeError("Pairwise preference output must not include numeric score objects")
    if "weighted_composite" in json.dumps(value).lower():
        raise JudgeError("Weighted composite score is not allowed")
    pair_id = str(value.get("pair_id") or "")
    if pair_id != pair.pair_id:
        raise JudgeError(f"pair_id mismatch; expected={pair.pair_id}, got={pair_id}")
    winner = value.get("winner")
    if winner not in PAIRWISE_WINNERS:
        raise JudgeError(f"Invalid winner: {winner}")
    conf = value.get("confidence")
    if conf not in confidence_options(config):
        raise JudgeError(f"Invalid confidence: {conf}")
    criterion_winners = value.get("criterion_winners")
    if not isinstance(criterion_winners, dict):
        raise JudgeError("criterion_winners must be an object")
    missing = [key for key in PAIRWISE_PREFERENCE_CRITERIA if key not in criterion_winners]
    extra = [key for key in criterion_winners if key not in PAIRWISE_PREFERENCE_CRITERIA]
    if missing or extra:
        raise JudgeError(f"criterion_winners keys mismatch; missing={missing}, extra={extra}")
    invalid = {key: val for key, val in criterion_winners.items() if val not in PAIRWISE_CRITERION_WINNERS}
    if invalid:
        raise JudgeError(f"Invalid criterion_winners values: {invalid}")
    for key in ("why_winner", "candidate_a_weakness", "candidate_b_weakness"):
        if not str(value.get(key, "")).strip():
            raise JudgeError(f"{key} is required")
    normalized = {
        "pair_id": pair.pair_id,
        "domain": pair.domain,
        "candidate_a_id": pair.candidate_a_id,
        "candidate_b_id": pair.candidate_b_id,
        "winner": winner,
        "confidence": conf,
        "criterion_winners": criterion_winners,
        "why_winner": value.get("why_winner"),
        "candidate_a_weakness": value.get("candidate_a_weakness"),
        "candidate_b_weakness": value.get("candidate_b_weakness"),
        "novelty_caveat": value.get("novelty_caveat", NOVELTY_CAVEAT),
    }
    judge_authored_text = "\n".join(
        str(normalized.get(key, ""))
        for key in ("why_winner", "candidate_a_weakness", "candidate_b_weakness")
    )
    if labels_found_in_prompt(judge_authored_text):
        raise JudgeError("Pairwise preference output contains forbidden method labels")
    return normalized


def validate_four_way_ranked_object(
    value: dict[str, Any],
    *,
    packet: FourWayPacket,
    config: dict[str, Any],
) -> dict[str, Any]:
    if "scores" in value or "pairwise_preference" in value:
        raise JudgeError("Four-way ranked output must not include scores or pairwise_preference")
    if "weighted_composite" in json.dumps(value).lower():
        raise JudgeError("Weighted composite score is not allowed")
    candidate_ids = [str(candidate.get("candidate_id")) for candidate in packet.candidates]
    expected_ids = set(candidate_ids)
    returned_ids = value.get("candidate_ids")
    if not isinstance(returned_ids, list) or set(str(item) for item in returned_ids) != expected_ids:
        raise JudgeError("candidate_ids must list all four candidate IDs")
    rankings = value.get("criterion_rankings")
    if not isinstance(rankings, dict):
        raise JudgeError("criterion_rankings must be an object")
    missing = [key for key in FOUR_WAY_RANK_CRITERIA if key not in rankings]
    extra = [key for key in rankings if key not in FOUR_WAY_RANK_CRITERIA]
    if missing or extra:
        raise JudgeError(f"criterion_rankings keys mismatch; missing={missing}, extra={extra}")
    normalized_rankings: dict[str, list[dict[str, Any]]] = {}
    for criterion in FOUR_WAY_RANK_CRITERIA:
        rows = rankings.get(criterion)
        if not isinstance(rows, list) or len(rows) != 4:
            raise JudgeError(f"{criterion} ranking must contain exactly 4 rows")
        seen = []
        normalized_rows = []
        for row in rows:
            if not isinstance(row, dict):
                raise JudgeError(f"{criterion} ranking rows must be objects")
            cid = str(row.get("candidate_id"))
            rank = row.get("rank")
            if cid not in expected_ids:
                raise JudgeError(f"{criterion} ranking contains unknown candidate_id: {cid}")
            if not isinstance(rank, int) or isinstance(rank, bool) or not 1 <= rank <= 4:
                raise JudgeError(f"{criterion} rank must be an integer 1-4 for {cid}")
            reason = str(row.get("reason", "")).strip()
            if not reason:
                raise JudgeError(f"{criterion} ranking reason is required for {cid}")
            seen.append(cid)
            normalized_rows.append({"candidate_id": cid, "rank": rank, "reason": reason})
        if set(seen) != expected_ids or len(seen) != len(set(seen)):
            raise JudgeError(f"{criterion} ranking must include every candidate exactly once")
        normalized_rankings[criterion] = normalized_rows
    special: dict[str, dict[str, str]] = {}
    for key in FOUR_WAY_SPECIAL_WINNERS:
        row = value.get(key)
        if not isinstance(row, dict):
            raise JudgeError(f"{key} must be an object")
        cid = str(row.get("candidate_id"))
        if cid not in expected_ids:
            raise JudgeError(f"{key}.candidate_id is unknown: {cid}")
        reason = str(row.get("reason", "")).strip()
        if not reason:
            raise JudgeError(f"{key}.reason is required")
        special[key] = {"candidate_id": cid, "reason": reason}
    conf = value.get("confidence")
    if conf not in confidence_options(config):
        raise JudgeError(f"Invalid confidence: {conf}")
    judge_authored_text = "\n".join(
        [str(value.get("domain_level_notes", ""))]
        + [special[key]["reason"] for key in FOUR_WAY_SPECIAL_WINNERS]
        + [row["reason"] for rows in normalized_rankings.values() for row in rows]
    )
    if labels_found_in_prompt(judge_authored_text):
        raise JudgeError("Four-way ranked output contains forbidden method labels")
    return {
        "domain": packet.domain,
        "candidate_ids": candidate_ids,
        "criterion_rankings": normalized_rankings,
        **special,
        "confidence": conf,
        "domain_level_notes": str(value.get("domain_level_notes", "")),
        "novelty_caveat": value.get("novelty_caveat", NOVELTY_CAVEAT),
    }


def validate_independent_score_object(
    value: dict[str, Any],
    *,
    candidate: IndependentCandidate,
    config: dict[str, Any],
) -> dict[str, Any]:
    ids = rubric_ids(config)
    min_score = int(config["evaluation"].get("score_scale_min", 1))
    max_score = int(config["evaluation"].get("score_scale_max", 5))
    if "pairwise_preference" in value:
        raise JudgeError("Independent scoring output must not include pairwise_preference")
    scores = value.get("scores")
    if not isinstance(scores, dict):
        raise JudgeError("scores must be an object")
    missing = [key for key in ids if key not in scores]
    extra = [key for key in scores if key not in ids]
    if missing or extra:
        raise JudgeError(f"score keys mismatch; missing={missing}, extra={extra}")
    for key in ids:
        score = scores[key]
        if not isinstance(score, int) or isinstance(score, bool):
            raise JudgeError(f"scores.{key} must be an integer")
        if not min_score <= score <= max_score:
            raise JudgeError(f"scores.{key}={score} outside {min_score}-{max_score}")
    conf = value.get("confidence")
    if conf not in confidence_options(config):
        raise JudgeError(f"Invalid confidence: {conf}")
    strengths = value.get("strengths")
    if config["evaluation"].get("require_strengths", True):
        if not isinstance(strengths, list) or not any(str(item).strip() for item in strengths):
            raise JudgeError("strengths must be a nonempty list")
    weaknesses = value.get("weaknesses")
    if config["evaluation"].get("require_weaknesses", True):
        if not isinstance(weaknesses, list) or not any(str(item).strip() for item in weaknesses):
            raise JudgeError("weaknesses must be a nonempty list")
    if config["evaluation"].get("require_score_justification", True):
        just = value.get("score_justification")
        if not isinstance(just, dict):
            raise JudgeError("score_justification must be an object")
        required_justifications = [
            "evidence_grounding",
            "formalizability",
            "overall_worth_reading",
        ]
        for optional_key in ("actionability", "pursuit_priority", "auditability_overall"):
            if optional_key in ids:
                required_justifications.append(optional_key)
        for key in required_justifications:
            if not str(just.get(key, "")).strip():
                raise JudgeError(f"score_justification.{key} is required")
    if config["evaluation"].get("require_rationale", True) and not value.get("rationale"):
        raise JudgeError("rationale is required")
    value["candidate_id"] = candidate.candidate_id
    value["domain"] = candidate.domain
    value["candidate_file"] = str(candidate.candidate_file)
    value.setdefault("novelty_caveat", NOVELTY_CAVEAT)
    value["calibration_flags"] = audit_independent_calibration(value, candidate)
    if "weighted_composite" in json.dumps(value).lower():
        raise JudgeError("Weighted composite score is not allowed")
    return value


def validate_formulation_quality_score_object(
    value: dict[str, Any],
    *,
    candidate: IndependentCandidate,
) -> dict[str, Any]:
    if "pairwise_preference" in value:
        raise JudgeError("Formulation-quality output must not include pairwise_preference")
    if "weighted_composite" in json.dumps(value).lower():
        raise JudgeError("Weighted composite score is not allowed")
    if str(value.get("candidate_id")) != candidate.candidate_id:
        raise JudgeError(f"candidate_id mismatch; expected={candidate.candidate_id}, got={value.get('candidate_id')}")
    if str(value.get("domain")) != candidate.domain:
        raise JudgeError(f"domain mismatch; expected={candidate.domain}, got={value.get('domain')}")
    scores = value.get("scores")
    if not isinstance(scores, dict):
        raise JudgeError("scores must be an object")
    missing = [key for key in FORMULATION_QUALITY_CRITERIA if key not in scores]
    extra = [key for key in scores if key not in FORMULATION_QUALITY_CRITERIA]
    if missing or extra:
        raise JudgeError(f"formulation-quality score keys mismatch; missing={missing}, extra={extra}")
    normalized_scores: dict[str, int] = {}
    for key in FORMULATION_QUALITY_CRITERIA:
        score = scores[key]
        if not isinstance(score, int) or isinstance(score, bool):
            raise JudgeError(f"scores.{key} must be an integer")
        if not 0 <= score <= 10:
            raise JudgeError(f"scores.{key}={score} outside 0-10")
        normalized_scores[key] = score
    action = str(value.get("recommended_action", ""))
    if action not in FORMULATION_QUALITY_ACTIONS:
        raise JudgeError(f"Invalid recommended_action: {action}")
    conf = value.get("confidence")
    if conf not in {"LOW", "MEDIUM", "HIGH"}:
        raise JudgeError(f"Invalid confidence: {conf}")
    strengths = value.get("strengths")
    if not isinstance(strengths, list) or not any(str(item).strip() for item in strengths):
        raise JudgeError("strengths must be a nonempty list")
    weaknesses = value.get("weaknesses")
    if not isinstance(weaknesses, list) or not any(str(item).strip() for item in weaknesses):
        raise JudgeError("weaknesses must be a nonempty list")
    if not str(value.get("rationale", "")).strip():
        raise JudgeError("rationale is required")
    judge_authored_text = "\n".join(
        [str(value.get("rationale", ""))]
        + [str(item) for item in strengths]
        + [str(item) for item in weaknesses]
    )
    if labels_found_in_prompt(judge_authored_text):
        raise JudgeError("Formulation-quality output contains forbidden method labels")
    out = {
        "candidate_id": candidate.candidate_id,
        "domain": candidate.domain,
        "candidate_file": str(candidate.candidate_file),
        "scores": normalized_scores,
        "recommended_action": action,
        "confidence": str(conf),
        "strengths": [str(item) for item in strengths],
        "weaknesses": [str(item) for item in weaknesses],
        "rationale": str(value.get("rationale")),
        "novelty_caveat": str(value.get("novelty_caveat") or NOVELTY_CAVEAT),
    }
    out["cap_violations"] = formulation_quality_cap_violations(candidate, out)
    return out


def formulation_quality_cap_violations(candidate: IndependentCandidate, row: dict[str, Any]) -> list[str]:
    scores = row.get("scores", {})
    violations: list[str] = []
    missing_formal = _missing_or_not_provided(candidate, "formal_problem_statement")
    missing_setup = _missing_or_not_provided(candidate, "assumptions_or_problem_setup")
    missing_source = _missing_or_not_provided(candidate, "source_context_or_grounding")
    missing_ambiguity = _missing_or_not_provided(candidate, "ambiguity_or_missing_definitions")
    missing_eval = _missing_or_not_provided(candidate, "evaluation_plan")
    has_formal = candidate_has_visible_formal_structure(candidate)
    text = _candidate_text(candidate).lower()
    overcomposed_terms = len(
        re.findall(
            r"\b(causal|quantum|federated|diffusion|graph|multimodal|fair|robust|adversarial|bayesian|conformal|world model|foundation|neural|symbolic)\b",
            text,
        )
    )
    if missing_formal and scores.get("well_posedness_0_to_10", 0) > 6:
        violations.append("formal_problem_statement_missing_but_well_posedness_above_6")
    if missing_formal and scores.get("overall_formulation_quality_0_to_10", 0) > 7:
        violations.append("formal_problem_statement_missing_but_overall_above_7")
    if missing_setup and scores.get("well_posedness_0_to_10", 0) > 6:
        violations.append("assumptions_or_problem_setup_missing_but_well_posedness_above_6")
    if missing_source and scores.get("source_grounded_specificity_0_to_10", 0) > 4:
        violations.append("source_context_or_grounding_missing_but_source_specificity_above_4")
    if missing_ambiguity and scores.get("ambiguity_hygiene_0_to_10", 0) > 6:
        violations.append("ambiguity_missing_definitions_missing_but_ambiguity_hygiene_above_6")
    if missing_eval and scores.get("feasibility_0_to_10", 0) > 6:
        violations.append("evaluation_plan_missing_but_feasibility_above_6")
    if not has_formal and scores.get("technical_sharpness_0_to_10", 0) > 5:
        violations.append("broad_or_underformalized_candidate_but_technical_sharpness_above_5")
    if overcomposed_terms >= 8 and scores.get("scope_control_0_to_10", 0) > 4:
        violations.append("many_loose_concepts_but_scope_control_above_4")
    source_weak = missing_source or not candidate_has_concrete_evidence(candidate)
    formal_weak = missing_formal or not has_formal
    if source_weak and formal_weak and scores.get("overall_formulation_quality_0_to_10", 0) > 6:
        violations.append("source_grounding_and_formal_structure_weak_but_overall_above_6")
    return violations


def validate_formulation_only_score_object(
    value: dict[str, Any],
    *,
    candidate: IndependentCandidate,
) -> dict[str, Any]:
    if "pairwise_preference" in value:
        raise JudgeError("Formulation-only output must not include pairwise_preference")
    if "weighted_composite" in json.dumps(value).lower():
        raise JudgeError("Weighted composite score is not allowed")
    if str(value.get("candidate_id")) != candidate.candidate_id:
        raise JudgeError(f"candidate_id mismatch; expected={candidate.candidate_id}, got={value.get('candidate_id')}")
    if str(value.get("domain")) != candidate.domain:
        raise JudgeError(f"domain mismatch; expected={candidate.domain}, got={value.get('domain')}")
    scores = value.get("scores")
    if not isinstance(scores, dict):
        raise JudgeError("scores must be an object")
    missing = [key for key in FORMULATION_ONLY_CRITERIA if key not in scores]
    extra = [key for key in scores if key not in FORMULATION_ONLY_CRITERIA]
    if missing or extra:
        raise JudgeError(f"formulation-only score keys mismatch; missing={missing}, extra={extra}")
    normalized_scores: dict[str, int] = {}
    for key in FORMULATION_ONLY_CRITERIA:
        score = scores[key]
        if not isinstance(score, int) or isinstance(score, bool):
            raise JudgeError(f"scores.{key} must be an integer")
        if not 0 <= score <= 10:
            raise JudgeError(f"scores.{key}={score} outside 0-10")
        normalized_scores[key] = score
    action = str(value.get("recommended_action", ""))
    if action not in FORMULATION_QUALITY_ACTIONS:
        raise JudgeError(f"Invalid recommended_action: {action}")
    conf = value.get("confidence")
    if conf not in {"LOW", "MEDIUM", "HIGH"}:
        raise JudgeError(f"Invalid confidence: {conf}")
    strengths = value.get("strengths")
    if not isinstance(strengths, list) or not any(str(item).strip() for item in strengths):
        raise JudgeError("strengths must be a nonempty list")
    weaknesses = value.get("weaknesses")
    if not isinstance(weaknesses, list) or not any(str(item).strip() for item in weaknesses):
        raise JudgeError("weaknesses must be a nonempty list")
    if not str(value.get("rationale", "")).strip():
        raise JudgeError("rationale is required")
    judge_authored_text = "\n".join(
        [str(value.get("rationale", ""))]
        + [str(item) for item in strengths]
        + [str(item) for item in weaknesses]
    )
    if labels_found_in_prompt(judge_authored_text):
        raise JudgeError("Formulation-only output contains forbidden method labels")
    out = {
        "candidate_id": candidate.candidate_id,
        "domain": candidate.domain,
        "candidate_file": str(candidate.candidate_file),
        "scores": normalized_scores,
        "recommended_action": action,
        "confidence": str(conf),
        "strengths": [str(item) for item in strengths],
        "weaknesses": [str(item) for item in weaknesses],
        "rationale": str(value.get("rationale")),
        "novelty_caveat": str(value.get("novelty_caveat") or NOVELTY_CAVEAT),
    }
    out["cap_violations"] = formulation_only_cap_violations(candidate, out)
    return out


def formulation_only_problem_looks_vague(candidate: IndependentCandidate) -> bool:
    problem = str(candidate.candidate.get("problem_statement") or "").strip().lower()
    formal = str(candidate.candidate.get("formal_problem_statement") or "").strip().lower()
    setup = str(candidate.candidate.get("assumptions_or_problem_setup") or "").strip().lower()
    if not problem or problem == NOT_PROVIDED:
        return True
    if len(problem) < 120 and (formal == NOT_PROVIDED or setup == NOT_PROVIDED):
        return True
    specificity_markers = (
        "given",
        "let ",
        "under ",
        "assume",
        "objective",
        "identify",
        "bound",
        "regret",
        "policy",
        "distribution",
        "estimator",
        "samples",
        "observations",
        "reward",
        "theorem",
        "condition",
        "constraint",
    )
    if not any(marker in problem or marker in formal or marker in setup for marker in specificity_markers):
        return True
    generic_phrases = (
        "improve machine learning",
        "better machine learning",
        "general framework",
        "future benchmarks",
        "many datasets",
        "scientific discovery",
    )
    return any(phrase in problem for phrase in generic_phrases)


def formulation_only_cap_violations(candidate: IndependentCandidate, row: dict[str, Any]) -> list[str]:
    scores = row.get("scores", {})
    violations: list[str] = []
    missing_formal = _missing_or_not_provided(candidate, "formal_problem_statement")
    missing_setup = _missing_or_not_provided(candidate, "assumptions_or_problem_setup")
    missing_source = _missing_or_not_provided(candidate, "source_context_or_grounding")
    missing_ambiguity = _missing_or_not_provided(candidate, "ambiguity_or_missing_definitions")
    has_formal = candidate_has_visible_formal_structure(candidate)
    text = _candidate_text(candidate).lower()
    overcomposed_terms = len(
        re.findall(
            r"\b(causal|quantum|federated|diffusion|graph|multimodal|fair|robust|adversarial|bayesian|conformal|world model|foundation|neural|symbolic)\b",
            text,
        )
    )
    apply_x_to_y = bool(
        re.search(r"\b(apply|test|combine|benchmark|evaluate)\b.{0,80}\b(to|under|with|against)\b", text)
    )
    if formulation_only_problem_looks_vague(candidate) and scores.get("overall_formulation_quality_10", 0) > 6:
        violations.append("vague_problem_but_overall_above_6")
    if missing_formal and scores.get("well_posedness_10", 0) > 6:
        violations.append("formal_problem_statement_missing_but_well_posedness_above_6")
    if missing_formal and scores.get("formalizability_10", 0) > 6:
        violations.append("formal_problem_statement_missing_but_formalizability_above_6")
    if missing_setup and scores.get("well_posedness_10", 0) > 6:
        violations.append("assumptions_or_problem_setup_missing_but_well_posedness_above_6")
    if missing_setup and scores.get("assumption_boundary_clarity_10", 0) > 6:
        violations.append("assumptions_or_problem_setup_missing_but_assumption_boundary_above_6")
    if missing_ambiguity and scores.get("ambiguity_hygiene_10", 0) > 6:
        violations.append("ambiguity_missing_definitions_missing_but_ambiguity_hygiene_above_6")
    if missing_source and scores.get("source_grounded_specificity_10", 0) > 4:
        violations.append("source_context_or_grounding_missing_but_source_specificity_above_4")
    if overcomposed_terms >= 8 and scores.get("scope_control_10", 0) > 4:
        violations.append("many_loose_concepts_but_scope_control_above_4")
    if apply_x_to_y and scores.get("nontriviality_10", 0) > 6:
        violations.append("apply_or_test_x_to_y_but_nontriviality_above_6")
    if not has_formal and scores.get("overall_formulation_quality_10", 0) > 7:
        violations.append("no_clear_formal_skeleton_but_overall_above_7")
    return violations


def personalized_profile_context_too_thin(candidate: IndependentCandidate) -> bool:
    context = str(candidate.candidate.get("profile_context") or "").strip().lower()
    if not context or context == NOT_PROVIDED:
        return True
    thin_markers = (
        "no final family to score",
        "no usable verification artifacts",
        "context unavailable",
        "profile context is missing",
        "too thin",
    )
    return any(marker in context for marker in thin_markers)


def personalized_profile_context_missing(candidate: IndependentCandidate) -> bool:
    context = str(candidate.candidate.get("profile_context") or "").strip().lower()
    return not context or context == NOT_PROVIDED


def personalized_profile_signal_missing(candidate: IndependentCandidate) -> bool:
    profile_context = str(candidate.candidate.get("profile_context") or "").strip().lower()
    source = str(candidate.candidate.get("source_context_or_grounding") or "").strip().lower()
    supporting = str(candidate.candidate.get("supporting_papers") or "").strip().lower()
    text = " ".join([
        str(candidate.candidate.get("title") or ""),
        str(candidate.candidate.get("problem_statement") or ""),
        str(candidate.candidate.get("motivation_or_abstract") or ""),
        str(candidate.candidate.get("formal_problem_statement") or ""),
        source,
        supporting,
    ]).lower()
    if not profile_context or profile_context == NOT_PROVIDED:
        return True
    weak_markers = (
        "generic",
        "could apply to many",
        "not profile-specific",
        "name-dropping",
        "off-profile",
    )
    if any(marker in text for marker in weak_markers):
        return True
    tokens = [
        tok for tok in re.findall(r"[a-z][a-z0-9\-]{4,}", profile_context)
        if tok not in {
            "profile", "researcher", "artifact", "supported", "themes", "papers", "paper",
            "context", "include", "includes", "including", "source", "sources", "title",
            "titles", "research", "problem", "method", "methods", "learning", "machine",
        }
    ]
    unique_tokens = list(dict.fromkeys(tokens))[:80]
    overlap = sum(1 for tok in unique_tokens if tok in text)
    has_source = bool(source and source != NOT_PROVIDED) or bool(supporting and supporting != NOT_PROVIDED)
    return overlap < 2 and not has_source


def personalized_name_dropping_or_off_profile(candidate: IndependentCandidate) -> bool:
    text = _candidate_text(candidate).lower()
    return any(marker in text for marker in ("name-dropping", "name dropping", "off-profile", "off profile"))


def personalized_formulation_cap_violations(candidate: IndependentCandidate, row: dict[str, Any]) -> list[str]:
    scores = row.get("scores", {})
    violations = formulation_only_cap_violations(candidate, row)
    if personalized_profile_context_missing(candidate) and scores.get("personalization_overall_10", 0) > 5:
        violations.append("profile_context_missing_but_personalization_overall_above_5")
    if personalized_profile_signal_missing(candidate) and scores.get("profile_specificity_10", 0) > 5:
        violations.append("generic_or_weak_profile_signal_but_profile_specificity_above_5")
    if personalized_name_dropping_or_off_profile(candidate) and scores.get("profile_alignment_10", 0) > 4:
        violations.append("name_dropping_or_off_profile_but_profile_alignment_above_4")
    if scores.get("profile_alignment_10", 0) <= 5 and scores.get("personalization_overall_10", 0) > 7:
        violations.append("weak_profile_alignment_but_personalization_overall_above_7")
    return violations


def validate_personalized_formulation_score_object(
    value: dict[str, Any],
    *,
    candidate: IndependentCandidate,
) -> dict[str, Any]:
    if "pairwise_preference" in value:
        raise JudgeError("Personalized formulation output must not include pairwise_preference")
    if "weighted_composite" in json.dumps(value).lower():
        raise JudgeError("Weighted composite score is not allowed")
    if str(value.get("candidate_id")) != candidate.candidate_id:
        raise JudgeError(f"candidate_id mismatch; expected={candidate.candidate_id}, got={value.get('candidate_id')}")
    expected_profile = _json_text(candidate.candidate.get("profile"))
    if str(value.get("profile")) != expected_profile:
        raise JudgeError(f"profile mismatch; expected={expected_profile}, got={value.get('profile')}")
    scores = value.get("scores")
    if not isinstance(scores, dict):
        raise JudgeError("scores must be an object")
    missing = [key for key in PERSONALIZED_FORMULATION_CRITERIA if key not in scores]
    extra = [key for key in scores if key not in PERSONALIZED_FORMULATION_CRITERIA]
    if missing or extra:
        raise JudgeError(f"personalized formulation score keys mismatch; missing={missing}, extra={extra}")
    normalized_scores: dict[str, int] = {}
    for key in PERSONALIZED_FORMULATION_CRITERIA:
        score = scores[key]
        if not isinstance(score, int) or isinstance(score, bool):
            raise JudgeError(f"scores.{key} must be an integer")
        if not 0 <= score <= 10:
            raise JudgeError(f"scores.{key}={score} outside 0-10")
        normalized_scores[key] = score
    action = str(value.get("recommended_action", ""))
    if action not in FORMULATION_QUALITY_ACTIONS:
        raise JudgeError(f"Invalid recommended_action: {action}")
    conf = value.get("confidence")
    if conf not in {"LOW", "MEDIUM", "HIGH"}:
        raise JudgeError(f"Invalid confidence: {conf}")
    strengths = value.get("strengths")
    if not isinstance(strengths, list) or not any(str(item).strip() for item in strengths):
        raise JudgeError("strengths must be a nonempty list")
    weaknesses = value.get("weaknesses")
    if not isinstance(weaknesses, list) or not any(str(item).strip() for item in weaknesses):
        raise JudgeError("weaknesses must be a nonempty list")
    if not str(value.get("rationale", "")).strip():
        raise JudgeError("rationale is required")
    judge_authored_text = "\n".join(
        [str(value.get("rationale", ""))]
        + [str(item) for item in strengths]
        + [str(item) for item in weaknesses]
    )
    if labels_found_in_prompt(judge_authored_text):
        raise JudgeError("Personalized formulation output contains forbidden method labels")
    out = {
        "candidate_id": candidate.candidate_id,
        "profile": expected_profile,
        "domain": candidate.domain,
        "candidate_file": str(candidate.candidate_file),
        "scores": normalized_scores,
        "recommended_action": action,
        "confidence": str(conf),
        "strengths": [str(item) for item in strengths],
        "weaknesses": [str(item) for item in weaknesses],
        "rationale": str(value.get("rationale")),
        "personalization_caveat": str(value.get("personalization_caveat") or PERSONALIZATION_CAVEAT),
        "novelty_caveat": str(value.get("novelty_caveat") or NOVELTY_CAVEAT),
    }
    out["cap_violations"] = personalized_formulation_cap_violations(candidate, out)
    return out


def validate_prism_idea_quality_score_object(
    value: dict[str, Any],
    *,
    candidate: IndependentCandidate,
) -> dict[str, Any]:
    if "pairwise_preference" in value:
        raise JudgeError("PRISM idea-quality output must not include pairwise_preference")
    if "weighted_composite" in json.dumps(value).lower():
        raise JudgeError("Weighted composite score is not allowed")
    if str(value.get("candidate_id")) != candidate.candidate_id:
        raise JudgeError(f"candidate_id mismatch; expected={candidate.candidate_id}, got={value.get('candidate_id')}")
    if str(value.get("domain")) != candidate.domain:
        raise JudgeError(f"domain mismatch; expected={candidate.domain}, got={value.get('domain')}")
    scores = value.get("scores")
    if not isinstance(scores, dict):
        raise JudgeError("scores must be an object")
    missing = [key for key in PRISM_IDEA_QUALITY_CRITERIA if key not in scores]
    extra = [key for key in scores if key not in PRISM_IDEA_QUALITY_CRITERIA]
    if missing or extra:
        raise JudgeError(f"PRISM idea-quality score keys mismatch; missing={missing}, extra={extra}")
    normalized_scores: dict[str, int] = {}
    for key in PRISM_IDEA_QUALITY_CRITERIA:
        score = scores[key]
        if not isinstance(score, int) or isinstance(score, bool):
            raise JudgeError(f"scores.{key} must be an integer")
        if not 1 <= score <= 10:
            raise JudgeError(f"scores.{key}={score} outside 1-10")
        normalized_scores[key] = score
    action = str(value.get("recommended_action", ""))
    if action not in PRISM_IDEA_QUALITY_ACTIONS:
        raise JudgeError(f"Invalid recommended_action: {action}")
    conf = value.get("confidence")
    if conf not in {"LOW", "MEDIUM", "HIGH"}:
        raise JudgeError(f"Invalid confidence: {conf}")
    strengths = value.get("strengths")
    if not isinstance(strengths, list) or not any(str(item).strip() for item in strengths):
        raise JudgeError("strengths must be a nonempty list")
    weaknesses = value.get("weaknesses")
    if not isinstance(weaknesses, list) or not any(str(item).strip() for item in weaknesses):
        raise JudgeError("weaknesses must be a nonempty list")
    if not str(value.get("rationale", "")).strip():
        raise JudgeError("rationale is required")
    judge_authored_text = "\n".join(
        [str(value.get("rationale", ""))]
        + [str(item) for item in strengths]
        + [str(item) for item in weaknesses]
    )
    if labels_found_in_prompt(judge_authored_text):
        raise JudgeError("PRISM idea-quality output contains forbidden method labels")
    out = {
        "candidate_id": candidate.candidate_id,
        "domain": candidate.domain,
        "candidate_file": str(candidate.candidate_file),
        "scores": normalized_scores,
        "recommended_action": action,
        "confidence": str(conf),
        "strengths": [str(item) for item in strengths],
        "weaknesses": [str(item) for item in weaknesses],
        "rationale": str(value.get("rationale")),
        "novelty_caveat": str(value.get("novelty_caveat") or PRISM_NOVELTY_CAVEAT),
    }
    return out


def validate_role_score_response(
    value: dict[str, Any],
    *,
    candidate: IndependentCandidate,
    config: dict[str, Any],
    role_id: str,
) -> dict[str, Any]:
    if "pairwise_preference" in value:
        raise JudgeError("Role-based scoring output must not include pairwise_preference")
    if "weighted_composite" in json.dumps(value).lower():
        raise JudgeError("Weighted composite score is not allowed")
    if str(value.get("candidate_id")) != candidate.candidate_id:
        raise JudgeError(f"candidate_id mismatch for {role_id}; expected={candidate.candidate_id}, got={value.get('candidate_id')}")
    if str(value.get("role_id")) != role_id:
        raise JudgeError(f"role_id mismatch; expected={role_id}, got={value.get('role_id')}")
    scores = value.get("scores")
    if not isinstance(scores, dict):
        raise JudgeError("role scores must be an object")
    ids = role_score_ids(config, role_id)
    missing = [key for key in ids if key not in scores]
    extra = [key for key in scores if key not in ids]
    if missing or extra:
        raise JudgeError(f"{role_id} score keys mismatch; missing={missing}, extra={extra}")
    for key in ids:
        score = scores[key]
        if not isinstance(score, int) or isinstance(score, bool):
            raise JudgeError(f"{role_id}.{key} must be an integer")
        if not 0 <= score <= 10:
            raise JudgeError(f"{role_id}.{key}={score} outside 0-10")
    conf = value.get("confidence")
    if conf not in confidence_options(config):
        raise JudgeError(f"Invalid confidence for {role_id}: {conf}")
    strengths = value.get("strengths")
    if not isinstance(strengths, list) or not any(str(item).strip() for item in strengths):
        raise JudgeError(f"{role_id}.strengths must be a nonempty list")
    weaknesses = value.get("weaknesses")
    if not isinstance(weaknesses, list) or not any(str(item).strip() for item in weaknesses):
        raise JudgeError(f"{role_id}.weaknesses must be a nonempty list")
    if not str(value.get("rationale", "")).strip():
        raise JudgeError(f"{role_id}.rationale is required")
    judge_authored_text = "\n".join(
        [str(value.get("rationale", ""))]
        + [str(item) for item in strengths]
        + [str(item) for item in weaknesses]
    )
    if labels_found_in_prompt(judge_authored_text):
        raise JudgeError(f"{role_id} output contains forbidden method labels")
    role_record = {key: scores[key] for key in ids}
    role_record.update(
        {
            "strengths": [str(item) for item in strengths],
            "weaknesses": [str(item) for item in weaknesses],
            "rationale": str(value.get("rationale")),
            "confidence": str(conf),
        }
    )
    return role_record


def _missing_or_not_provided(candidate: IndependentCandidate, key: str) -> bool:
    return not _field_is_provided(candidate.candidate.get(key))


def candidate_has_explicit_variables_or_entities(candidate: IndependentCandidate) -> bool:
    text = "\n".join(
        str(candidate.candidate.get(key, ""))
        for key in ("formal_problem_statement", "assumptions_or_problem_setup", "problem_statement")
    ).lower()
    if not text.strip():
        return False
    return bool(
        re.search(
            r"\b(variables?|entities|arms?|actions?|states?|observations?|feedback|rewards?|polic(?:y|ies)|constraints?|objectives?|estimators?|environments?|distributions?)\b",
            text,
        )
    )


def candidate_has_assumptions(candidate: IndependentCandidate) -> bool:
    text = "\n".join(
        str(candidate.candidate.get(key, ""))
        for key in ("assumptions_or_problem_setup", "formal_problem_statement", "problem_statement")
    ).lower()
    return bool(re.search(r"\b(assumption|assume|under|condition|constraint|setting|given)\b", text))


def candidate_has_objective(candidate: IndependentCandidate) -> bool:
    text = "\n".join(
        str(candidate.candidate.get(key, ""))
        for key in ("formal_problem_statement", "assumptions_or_problem_setup", "evaluation_plan", "expected_contribution", "problem_statement")
    ).lower()
    return bool(re.search(r"\b(objective|success criterion|minimi[sz]e|maximi[sz]e|optimi[sz]e|bound|identify|estimate|guarantee|regret|loss|error|risk|accuracy|coverage)\b", text))


def candidate_has_evaluation_model(candidate: IndependentCandidate) -> bool:
    text = "\n".join(
        str(candidate.candidate.get(key, ""))
        for key in ("evaluation_plan", "formal_problem_statement", "assumptions_or_problem_setup", "expected_contribution")
    ).lower()
    return bool(re.search(r"\b(observation|feedback|measurement|evaluation|benchmark|experiment|dataset|simulation|compare|validate|metric|protocol|theorem|proof)\b", text))


def candidate_source_is_generic(candidate: IndependentCandidate) -> bool:
    source = str(candidate.candidate.get("source_context_or_grounding", "")).strip().lower()
    if not source or source == NOT_PROVIDED:
        return False
    concrete = candidate_has_concrete_evidence(candidate)
    generic_markers = ("provided corpus", "recent work", "literature", "source context", "papers in the corpus", "not provided")
    return not concrete or any(marker in source for marker in generic_markers) and not re.search(r"\b(paper\s+\d+|openreview|arxiv|doi:|source_verified_gaps|supporting_papers)\b", source)


def candidate_term_soup_flag(candidate: IndependentCandidate) -> bool:
    explicit = str(candidate.candidate.get("term_soup_flag", "")).strip().lower()
    if explicit in {"true", "yes", "1", "term_soup", "overcomposed", "over-composed"}:
        return True
    text = _candidate_text(candidate).lower()
    motifs = re.findall(
        r"\b(causal|robust|federated|bayesian|quantum|diffusion|transformer|graph|multimodal|privacy|fairness|meta-learning|neurosymbolic|hierarchical|reinforcement|contrastive|conformal|foundation model|world model|active learning)\b",
        text,
    )
    return len(set(motifs)) >= 6


def candidate_mostly_generic_or_incremental(candidate: IndependentCandidate) -> bool:
    text = _candidate_text(candidate).lower()
    return bool(
        re.search(r"\b(apply|application|use|extend|adapt|combine|test|evaluate)\b", text)
        and re.search(r"\b(known|existing|standard|method|algorithm|approach|framework)\b", text)
    )


def validate_role_cap_rules(
    candidate: IndependentCandidate,
    *,
    role_id: str,
    role_record: dict[str, Any],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    triggered: list[str] = []
    def score(key: str) -> int:
        value = role_record.get(key)
        return int(value) if isinstance(value, int) else -1

    if role_id == "scientific_merit_reviewer":
        if not candidate_has_action_path(candidate):
            triggered.append("no_clear_evaluation_or_next_step_path")
            if score("actionability_10") > 5:
                errors.append("actionability_10 exceeds 5 without a clear evaluation or next-step path")
        if score("feasibility_10") <= 4:
            triggered.append("weak_feasibility")
            if score("research_priority_10") > 6:
                errors.append("research_priority_10 exceeds 6 despite weak feasibility")
        if candidate_mostly_generic_or_incremental(candidate):
            triggered.append("mostly_generic_or_known_method_application")
            if score("novelty_potential_10") > 5:
                errors.append("novelty_potential_10 exceeds 5 for a mostly generic/common direction")
    elif role_id == "formalization_reviewer":
        if _missing_or_not_provided(candidate, "formal_problem_statement"):
            triggered.append("formal_problem_statement_missing")
            if score("formalizability_10") > 5:
                errors.append("formalizability_10 exceeds 5 when formal_problem_statement is missing or not provided")
        if not candidate_has_explicit_variables_or_entities(candidate):
            triggered.append("variables_or_entities_missing")
            if score("formalizability_10") > 6:
                errors.append("formalizability_10 exceeds 6 without explicit variables/entities")
        if not candidate_has_assumptions(candidate):
            triggered.append("assumptions_missing")
            if score("assumption_clarity_10") > 5:
                errors.append("assumption_clarity_10 exceeds 5 without explicit assumptions")
        if not candidate_has_objective(candidate):
            triggered.append("objective_missing")
            if score("objective_clarity_10") > 5:
                errors.append("objective_clarity_10 exceeds 5 without explicit objective/success criterion")
        if not candidate_has_evaluation_model(candidate):
            triggered.append("evaluation_model_missing")
            if score("evaluation_model_clarity_10") > 5:
                errors.append("evaluation_model_clarity_10 exceeds 5 without explicit observation/evaluation model")
    elif role_id == "evidence_auditability_reviewer":
        has_evidence = candidate_has_concrete_evidence(candidate)
        has_formal = candidate_has_visible_formal_structure(candidate)
        if not has_evidence:
            triggered.append("no_concrete_source_evidence")
            if score("evidence_grounding_10") > 4:
                errors.append("evidence_grounding_10 exceeds 4 without concrete source papers/evidence trail/context items")
            if score("source_traceability_10") > 4:
                errors.append("source_traceability_10 exceeds 4 without traceable support/context")
        if candidate_source_is_generic(candidate):
            triggered.append("generic_source_evidence")
            if score("evidence_grounding_10") > 6:
                errors.append("evidence_grounding_10 exceeds 6 with generic source evidence")
        if not has_evidence and not has_formal:
            triggered.append("weak_evidence_and_formal_structure")
            if score("auditability_10") > 5:
                errors.append("auditability_10 exceeds 5 when formal structure and evidence trail are weak")
        if candidate_term_soup_flag(candidate):
            triggered.append("term_soup_or_overcomposed")
            if score("low_term_soup_10") > 4:
                errors.append("low_term_soup_10 exceeds 4 for a term-soup/over-composed candidate")
    else:
        raise JudgeError(f"Unknown role_id for cap validation: {role_id}")
    return triggered, errors


def aggregate_role_scores(
    *,
    candidate: IndependentCandidate,
    role_scores: dict[str, dict[str, Any]],
    cap_rules_triggered: list[str],
    cap_violations: list[str],
    invalid_roles: list[str],
) -> dict[str, Any]:
    confidences = [
        str(role.get("confidence"))
        for role in role_scores.values()
        if str(role.get("confidence")) in ROLE_BASED_CONFIDENCE_ORDER
    ]
    confidence = "LOW"
    if confidences:
        confidence = min(confidences, key=lambda item: ROLE_BASED_CONFIDENCE_ORDER[item])
    return {
        "candidate_id": candidate.candidate_id,
        "domain": candidate.domain,
        "role_scores": role_scores,
        "cap_rules_triggered": sorted(set(cap_rules_triggered)),
        "cap_violations": cap_violations,
        "invalid_roles": invalid_roles,
        "valid_for_run": not cap_violations and not invalid_roles,
        "confidence": confidence,
        "novelty_caveat": NOVELTY_CAVEAT,
    }


def validate_batch_calibrated_score_object(
    value: dict[str, Any],
    *,
    candidates: list[IndependentCandidate],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    if "pairwise_preference" in json.dumps(value):
        raise JudgeError("Batch-calibrated scoring output must not include pairwise_preference")
    if "weighted_composite" in json.dumps(value).lower():
        raise JudgeError("Weighted composite score is not allowed")
    expected_ids = [candidate.candidate_id for candidate in candidates]
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    rows = value.get("candidates")
    if not isinstance(rows, list):
        raise JudgeError("batch response candidates must be a list")
    if len(rows) != len(candidates):
        raise JudgeError(f"batch response candidate count mismatch; expected={len(candidates)}, got={len(rows)}")
    seen_ids = [str(row.get("candidate_id")) for row in rows if isinstance(row, dict)]
    missing = [cid for cid in expected_ids if cid not in seen_ids]
    extra = [cid for cid in seen_ids if cid not in expected_ids]
    if missing or extra:
        raise JudgeError(f"batch response candidate IDs mismatch; missing={missing}, extra={extra}")
    ranks: list[int] = []
    normalized: list[dict[str, Any]] = []
    notes = str(value.get("calibration_notes", ""))
    batch_size = value.get("batch_size")
    if isinstance(batch_size, int) and batch_size != len(candidates):
        raise JudgeError(f"batch_size mismatch; expected={len(candidates)}, got={batch_size}")
    checklist_keys = {
        "concrete_source_grounding",
        "formal_problem_skeleton",
        "clear_assumptions_or_shift",
        "clear_objective_or_success_criterion",
        "clear_evaluation_path",
        "term_soup_or_overcomposed",
    }
    checklist_values = {"YES", "PARTIAL", "NO"}
    for row in rows:
        if not isinstance(row, dict):
            raise JudgeError("each batch candidate score must be an object")
        rank = row.get("rank_in_batch")
        if not isinstance(rank, int) or isinstance(rank, bool) or not 1 <= rank <= len(candidates):
            raise JudgeError(f"rank_in_batch must be an integer 1-{len(candidates)} for {row.get('candidate_id')}")
        ranks.append(rank)
        checklist = row.get("pre_score_checklist")
        if not isinstance(checklist, dict):
            raise JudgeError(f"pre_score_checklist must be an object for {row.get('candidate_id')}")
        missing_checklist = [key for key in checklist_keys if key not in checklist]
        extra_checklist = [key for key in checklist if key not in checklist_keys]
        if missing_checklist or extra_checklist:
            raise JudgeError(
                f"pre_score_checklist keys mismatch for {row.get('candidate_id')}; "
                f"missing={missing_checklist}, extra={extra_checklist}"
            )
        invalid_checklist = {
            key: value
            for key, value in checklist.items()
            if str(value) not in checklist_values
        }
        if invalid_checklist:
            raise JudgeError(f"pre_score_checklist values must be YES, PARTIAL, or NO for {row.get('candidate_id')}: {invalid_checklist}")
        cap_rules = row.get("cap_rules_triggered", [])
        if not isinstance(cap_rules, list):
            raise JudgeError(f"cap_rules_triggered must be a list for {row.get('candidate_id')}")
        cap_exceptions = row.get("cap_exceptions", [])
        if not isinstance(cap_exceptions, list):
            raise JudgeError(f"cap_exceptions must be a list for {row.get('candidate_id')}")
        candidate = candidate_by_id[str(row.get("candidate_id"))]
        single = {
            "candidate_id": row.get("candidate_id"),
            "domain": row.get("domain") or candidate.domain,
            "scores": row.get("scores"),
            "confidence": row.get("confidence"),
            "strengths": row.get("strengths"),
            "weaknesses": row.get("weaknesses"),
            "score_justification": {
                "evidence_grounding": row.get("rationale", ""),
                "formalizability": row.get("rationale", ""),
                "actionability": row.get("rationale", ""),
                "pursuit_priority": row.get("rationale", ""),
                "auditability_overall": row.get("rationale", ""),
                "overall_worth_reading": row.get("rationale", ""),
            },
            "rationale": row.get("rationale"),
            "novelty_caveat": row.get("novelty_caveat", NOVELTY_CAVEAT),
        }
        parsed = validate_independent_score_object(single, candidate=candidate, config=config)
        parsed["rank_in_batch"] = rank
        parsed["pre_score_checklist"] = checklist
        parsed["cap_rules_triggered"] = cap_rules
        parsed["cap_exceptions"] = cap_exceptions
        parsed["batch_calibration_notes"] = notes
        _validate_batch_hard_caps(parsed, candidate)
        normalized.append(parsed)
    if len(set(ranks)) == 1 and len(ranks) > 1:
        raise JudgeError("rank_in_batch must not assign the same rank to all candidates")
    if sorted(ranks) != list(range(1, len(candidates) + 1)):
        raise JudgeError(f"rank_in_batch must be a complete 1-{len(candidates)} ranking; got={sorted(ranks)}")
    input_order_rank = {candidate.candidate_id: index for index, candidate in enumerate(candidates, start=1)}
    if all(row.get("rank_in_batch") == input_order_rank.get(str(row.get("candidate_id"))) for row in normalized) and len(normalized) > 1:
        raise JudgeError("rank_in_batch must not simply mirror input order")
    return normalized, notes


def _has_cap_exception(row: dict[str, Any], keyword: str) -> bool:
    exceptions = row.get("cap_exceptions") or []
    return any(keyword.lower() in str(item).lower() for item in exceptions)


def _field_missing_in_candidate(candidate: IndependentCandidate, field: str) -> bool:
    return not _field_is_provided(candidate.candidate.get(field))


def _validate_batch_hard_caps(row: dict[str, Any], candidate: IndependentCandidate) -> None:
    scores = row.get("scores", {})
    checklist = row.get("pre_score_checklist", {})
    errors: list[str] = []
    has_evidence = candidate_has_concrete_evidence(candidate)
    has_formal = candidate_has_visible_formal_structure(candidate)
    has_action = candidate_has_action_path(candidate)
    formal_field_missing = _field_missing_in_candidate(candidate, "formal_problem_statement")
    setup_field_missing = _field_missing_in_candidate(candidate, "assumptions_or_problem_setup")
    ambiguity_field_missing = _field_missing_in_candidate(candidate, "ambiguity_or_missing_definitions")

    if not has_evidence and scores.get("evidence_grounding", 0) > 2 and not _has_cap_exception(row, "evidence"):
        errors.append("evidence_grounding exceeds hard cap without concrete evidence")
    if str(checklist.get("concrete_source_grounding")) == "NO" and scores.get("evidence_grounding", 0) > 2 and not _has_cap_exception(row, "evidence"):
        errors.append("evidence_grounding exceeds checklist NO cap")
    if str(checklist.get("concrete_source_grounding")) == "PARTIAL" and scores.get("evidence_grounding", 0) > 3 and not _has_cap_exception(row, "evidence"):
        errors.append("evidence_grounding exceeds checklist PARTIAL cap")

    if not has_formal and scores.get("formalizability", 0) > 3 and not _has_cap_exception(row, "formal"):
        errors.append("formalizability exceeds hard cap without visible formal structure")
    if formal_field_missing and setup_field_missing and scores.get("formalizability", 0) > 3 and not _has_cap_exception(row, "formal"):
        errors.append("formalizability exceeds cap while formal_problem_statement and setup are not provided")
    if str(checklist.get("formal_problem_skeleton")) == "NO" and scores.get("formalizability", 0) > 2 and not _has_cap_exception(row, "formal"):
        errors.append("formalizability exceeds checklist NO skeleton cap")
    if str(checklist.get("formal_problem_skeleton")) == "PARTIAL" and scores.get("formalizability", 0) > 3 and not _has_cap_exception(row, "formal"):
        errors.append("formalizability exceeds checklist PARTIAL skeleton cap")

    if not has_action and scores.get("actionability", 0) > 3 and not _has_cap_exception(row, "action"):
        errors.append("actionability exceeds hard cap without clear evaluation/action path")
    if str(checklist.get("clear_evaluation_path")) == "NO" and scores.get("actionability", 0) > 3 and not _has_cap_exception(row, "action"):
        errors.append("actionability exceeds checklist NO evaluation path cap")

    if scores.get("evidence_grounding", 0) <= 2 and scores.get("formalizability", 0) <= 3 and scores.get("pursuit_priority", 0) > 3 and not _has_cap_exception(row, "pursuit"):
        errors.append("pursuit_priority exceeds cap despite weak evidence and formalizability")
    if scores.get("feasibility", 0) <= 2 and scores.get("pursuit_priority", 0) > 3 and not _has_cap_exception(row, "pursuit"):
        errors.append("pursuit_priority exceeds cap despite low feasibility")
    if scores.get("actionability", 0) <= 2 and scores.get("pursuit_priority", 0) > 3 and not _has_cap_exception(row, "pursuit"):
        errors.append("pursuit_priority exceeds cap despite low actionability")

    weak_auditability = (
        scores.get("evidence_grounding", 0) <= 3
        and scores.get("formalizability", 0) <= 3
    ) or (formal_field_missing and setup_field_missing and ambiguity_field_missing)
    if weak_auditability and scores.get("auditability_overall", 0) > 3 and not _has_cap_exception(row, "audit"):
        errors.append("auditability_overall exceeds cap despite weak or missing evidence/formalization structure")

    if errors:
        raise JudgeError(f"hard cap violations for {row.get('candidate_id')}: {errors}")


def _candidate_text(candidate: IndependentCandidate) -> str:
    return "\n".join(str(value) for value in candidate.candidate.values() if value is not None)


def _field_is_provided(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() not in {NOT_PROVIDED, "none", "n/a", "null"}


def candidate_has_concrete_evidence(candidate: IndependentCandidate) -> bool:
    text = _candidate_text(candidate)
    if re.search(
        r"\b(Paper\s+\d+|Corpus\s+#\d+|openreview|arxiv|doi:|supporting_papers|source_verified_gaps|retrieved_context|top_source|source_context|context items?)\b",
        text,
        re.IGNORECASE,
    ):
        return True
    source = str(candidate.candidate.get("source_context_or_grounding", "")).strip().lower()
    return bool(source and source != NOT_PROVIDED and len(source) > 40)


def candidate_has_visible_formal_structure(candidate: IndependentCandidate) -> bool:
    formal = candidate.candidate.get("formal_problem_statement")
    setup = candidate.candidate.get("assumptions_or_problem_setup")
    if _field_is_provided(formal) and _field_is_provided(setup):
        return True
    text = _candidate_text(candidate).lower()
    has_entity = bool(re.search(r"\b(entity|entities|variable|variables|arm|policy|reward|state|action|observation|feedback|distribution|estimator)\b", text))
    has_assumption = bool(re.search(r"\b(assumption|assume|constraint|under the condition|setting)\b", text))
    has_objective = bool(re.search(r"\b(objective|success criterion|minimize|maximize|regret|bound|identify|estimate|guarantee)\b", text))
    has_feedback = bool(re.search(r"\b(observation|feedback|evaluation model|measurement|benchmark|experiment|observed|sample)\b", text))
    return sum([has_entity, has_assumption, has_objective, has_feedback]) >= 3


def candidate_has_action_path(candidate: IndependentCandidate) -> bool:
    text = "\n".join(
        str(candidate.candidate.get(key, ""))
        for key in ("evaluation_plan", "expected_contribution", "proposed_direction")
    ).lower()
    if not text.strip() or text.strip() == NOT_PROVIDED:
        return False
    return bool(
        re.search(
            r"\b(theorem|algorithm|benchmark|dataset|experiment|empirical|proof|source-reading|read|evaluation|validate|compare|simulation|lower bound|upper bound)\b",
            text,
        )
    )


def audit_independent_calibration(value: dict[str, Any], candidate: IndependentCandidate) -> list[str]:
    flags: list[str] = []
    scores = value.get("scores", {})
    text = _candidate_text(candidate).lower()
    has_evidence = candidate_has_concrete_evidence(candidate)
    has_formal = candidate_has_visible_formal_structure(candidate)
    has_action = candidate_has_action_path(candidate)
    if not has_evidence and scores.get("evidence_grounding", 0) > 2:
        flags.append("evidence_grounding_above_2_without_concrete_source_evidence")
    if not has_evidence and scores.get("auditability_overall", 0) > 3:
        flags.append("auditability_above_3_without_concrete_source_evidence")
    if not has_formal and scores.get("formalizability", 0) > 3:
        flags.append("formalizability_above_3_without_visible_formal_structure")
    if not has_formal and scores.get("auditability_overall", 0) > 3:
        flags.append("auditability_above_3_without_visible_formal_structure")
    if re.search(r"\b(apply|application|extend|use)\b", text) and re.search(r"\b(known|existing|standard)\b", text) and scores.get("non_incrementality", 0) > 3:
        flags.append("non_incrementality_above_3_for_apparent_known_method_application")
    if not has_action and scores.get("actionability", 0) > 3:
        flags.append("actionability_above_3_without_evaluation_plan")
    if scores.get("evidence_grounding", 0) <= 2 and scores.get("formalizability", 0) <= 3 and scores.get("pursuit_priority", 0) > 3:
        flags.append("pursuit_priority_above_3_despite_weak_evidence_and_formalizability")
    if scores.get("feasibility", 0) <= 2 and scores.get("pursuit_priority", 0) > 3:
        flags.append("pursuit_priority_above_3_despite_low_feasibility")
    if scores.get("pursuit_priority", 0) == 5:
        strong_basis = (
            scores.get("clarity_specificity", 0) >= 4
            and scores.get("significance", 0) >= 4
            and scores.get("feasibility", 0) >= 4
            and (scores.get("evidence_grounding", 0) >= 4 or scores.get("formalizability", 0) >= 4)
        )
        if not strong_basis:
            flags.append("pursuit_priority_5_without_strong_specific_feasible_grounded_basis")
    return flags


def parse_model_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    candidates = [stripped]
    fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(item.strip() for item in fenced if item.strip())

    decoder = json.JSONDecoder()
    errors: list[str] = []
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
        else:
            if not isinstance(value, dict):
                raise JudgeError("Model response must be a JSON object")
            return value

    for start in [match.start() for match in re.finditer(r"\{", stripped)]:
        try:
            value, _ = decoder.raw_decode(stripped[start:])
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(value, dict):
            raise JudgeError("Model response must be a JSON object")
        return value

    raise JudgeError(f"Could not parse JSON object from model response: {'; '.join(errors[-3:])}")


def load_mock_response(value: str) -> str:
    stripped = value.lstrip()
    if stripped.startswith("{") or stripped.startswith("[") or "\n" in value:
        return value
    maybe_path = Path(value)
    try:
        if maybe_path.exists():
            return maybe_path.read_text(encoding="utf-8")
    except OSError:
        return value
    return value


def write_scores_csv(path: Path, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    ids = rubric_ids(config)
    fieldnames = (
        [
            "comparison_id",
            "domain",
            "baseline",
            "comparison_dir",
            "candidate_a_id",
            "candidate_b_id",
        ]
        + [f"candidate_a_{key}" for key in ids]
        + [f"candidate_b_{key}" for key in ids]
        + ["pairwise_preference", "confidence", "rationale", "novelty_caveat"]
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {
                "comparison_id": row.get("comparison_id"),
                "domain": row.get("domain"),
                "baseline": row.get("baseline"),
                "comparison_dir": row.get("comparison_dir"),
                "candidate_a_id": row.get("candidate_a_id"),
                "candidate_b_id": row.get("candidate_b_id"),
                "pairwise_preference": row.get("pairwise_preference"),
                "confidence": row.get("confidence"),
                "rationale": row.get("rationale"),
                "novelty_caveat": row.get("novelty_caveat"),
            }
            for key in ids:
                flat[f"candidate_a_{key}"] = row.get("candidate_a_scores", {}).get(key)
                flat[f"candidate_b_{key}"] = row.get("candidate_b_scores", {}).get(key)
            writer.writerow(flat)


def write_independent_scores_csv(path: Path, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    ids = rubric_ids(config)
    fieldnames = ["candidate_id", "domain", "candidate_file"] + ids + [
        "rank_in_batch",
        "confidence",
        "pre_score_checklist",
        "strengths",
        "weaknesses",
        "cap_rules_triggered",
        "cap_exceptions",
        "score_justification",
        "calibration_flags",
        "batch_calibration_notes",
        "rationale",
        "novelty_caveat",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {
                "candidate_id": row.get("candidate_id"),
                "domain": row.get("domain"),
                "candidate_file": row.get("candidate_file"),
                "rank_in_batch": row.get("rank_in_batch"),
                "confidence": row.get("confidence"),
                "pre_score_checklist": json.dumps(row.get("pre_score_checklist", {}), ensure_ascii=False),
                "strengths": json.dumps(row.get("strengths", []), ensure_ascii=False),
                "weaknesses": json.dumps(row.get("weaknesses", []), ensure_ascii=False),
                "cap_rules_triggered": json.dumps(row.get("cap_rules_triggered", []), ensure_ascii=False),
                "cap_exceptions": json.dumps(row.get("cap_exceptions", []), ensure_ascii=False),
                "score_justification": json.dumps(row.get("score_justification", {}), ensure_ascii=False),
                "calibration_flags": json.dumps(row.get("calibration_flags", []), ensure_ascii=False),
                "batch_calibration_notes": row.get("batch_calibration_notes"),
                "rationale": row.get("rationale"),
                "novelty_caveat": row.get("novelty_caveat"),
            }
            for key in ids:
                flat[key] = row.get("scores", {}).get(key)
            writer.writerow(flat)


def write_role_based_scores_csv(path: Path, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    ids = role_score_ids(config)
    fieldnames = [
        "candidate_id",
        "domain",
        "confidence",
        "valid_for_run",
        "invalid_roles",
        "cap_rules_triggered",
        "cap_violations",
    ] + ids + [
        "role_strengths",
        "role_weaknesses",
        "role_rationales",
        "novelty_caveat",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {
                "candidate_id": row.get("candidate_id"),
                "domain": row.get("domain"),
                "confidence": row.get("confidence"),
                "valid_for_run": row.get("valid_for_run"),
                "invalid_roles": json.dumps(row.get("invalid_roles", []), ensure_ascii=False),
                "cap_rules_triggered": json.dumps(row.get("cap_rules_triggered", []), ensure_ascii=False),
                "cap_violations": json.dumps(row.get("cap_violations", []), ensure_ascii=False),
                "role_strengths": json.dumps({rid: rec.get("strengths", []) for rid, rec in row.get("role_scores", {}).items()}, ensure_ascii=False),
                "role_weaknesses": json.dumps({rid: rec.get("weaknesses", []) for rid, rec in row.get("role_scores", {}).items()}, ensure_ascii=False),
                "role_rationales": json.dumps({rid: rec.get("rationale", "") for rid, rec in row.get("role_scores", {}).items()}, ensure_ascii=False),
                "novelty_caveat": row.get("novelty_caveat"),
            }
            for role_id, role_record in row.get("role_scores", {}).items():
                for key in role_score_ids(config, role_id):
                    flat[key] = role_record.get(key)
            writer.writerow(flat)


def ensure_role_based_output_files(
    output_dir: Path,
    config: dict[str, Any],
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw: list[dict[str, Any]],
) -> None:
    write_jsonl(output_dir / "raw_model_responses.jsonl", raw)
    write_jsonl(output_dir / "scores_blinded.jsonl", scores)
    write_role_based_scores_csv(output_dir / "scores_blinded.csv", scores, config)
    write_role_based_scores_csv(output_dir / "role_scores_blinded.csv", scores, config)
    write_jsonl(output_dir / "parse_errors.jsonl", parse_errors)


def write_formulation_quality_scores_csv(path: Path, rows: list[dict[str, Any]], *, unblinded: bool = False) -> None:
    fieldnames = ["candidate_id"]
    if unblinded:
        fieldnames.extend(["original_candidate_id", "domain", "method", "title"])
    else:
        fieldnames.extend(["domain", "candidate_file"])
    fieldnames.extend(FORMULATION_QUALITY_CRITERIA)
    fieldnames.extend(["recommended_action", "confidence", "strengths", "weaknesses", "cap_violations", "rationale", "novelty_caveat"])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {
                "candidate_id": row.get("candidate_id"),
                "domain": row.get("domain"),
                "recommended_action": row.get("recommended_action"),
                "confidence": row.get("confidence"),
                "strengths": json.dumps(row.get("strengths", []), ensure_ascii=False),
                "weaknesses": json.dumps(row.get("weaknesses", []), ensure_ascii=False),
                "cap_violations": json.dumps(row.get("cap_violations", []), ensure_ascii=False),
                "rationale": row.get("rationale"),
                "novelty_caveat": row.get("novelty_caveat"),
            }
            if unblinded:
                flat.update(
                    {
                        "original_candidate_id": row.get("original_candidate_id"),
                        "method": row.get("method"),
                        "title": row.get("title"),
                    }
                )
            else:
                flat["candidate_file"] = row.get("candidate_file")
            for key in FORMULATION_QUALITY_CRITERIA:
                flat[key] = row.get("scores", {}).get(key)
            writer.writerow(flat)


def ensure_formulation_quality_output_files(
    output_dir: Path,
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw: list[dict[str, Any]],
) -> None:
    write_jsonl(output_dir / "raw_model_responses.jsonl", raw)
    write_jsonl(output_dir / "formulation_quality_scores_blinded.jsonl", scores)
    write_formulation_quality_scores_csv(output_dir / "formulation_quality_scores_blinded.csv", scores, unblinded=False)
    write_jsonl(output_dir / "parse_errors.jsonl", parse_errors)
    # Generic filenames keep --postprocess-unblind compatible with the other independent modes.
    write_jsonl(output_dir / "scores_blinded.jsonl", scores)
    write_formulation_quality_scores_csv(output_dir / "scores_blinded.csv", scores, unblinded=False)


def formulation_quality_scores_valid(scores: list[dict[str, Any]]) -> bool:
    for row in scores:
        score_map = row.get("scores")
        if not isinstance(score_map, dict):
            return False
        if set(score_map) != set(FORMULATION_QUALITY_CRITERIA):
            return False
        for key in FORMULATION_QUALITY_CRITERIA:
            value = score_map.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10:
                return False
        if row.get("recommended_action") not in FORMULATION_QUALITY_ACTIONS:
            return False
        if row.get("confidence") not in {"LOW", "MEDIUM", "HIGH"}:
            return False
        if not isinstance(row.get("weaknesses"), list) or not row.get("weaknesses"):
            return False
    return True


def write_formulation_quality_audit(
    path: Path,
    *,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw_responses: list[dict[str, Any]],
    unblind: bool,
) -> None:
    cap_violation_count = sum(len(row.get("cap_violations", [])) for row in scores)
    lines = [
        "# Formulation Quality Judge Quality Audit",
        "",
        f"- scoring mode: {metadata.get('scoring_mode')}",
        f"- API key env var present: {metadata.get('api_key_env_present')}",
        f"- model: `{metadata.get('model')}`",
        f"- base_url specified: {bool(metadata.get('base_url'))}",
        f"- blinded candidate input exists: {Path(str(manifest.get('candidate_file'))).exists() if manifest.get('candidate_file') else False}",
        f"- blinding key not read during scoring: {not manifest.get('blinding_key_read_during_scoring', False)}",
        f"- method labels absent from judge prompts: {not manifest.get('method_label_findings_in_prompts')}",
        f"- score fields are valid 0-10 integers: {formulation_quality_scores_valid(scores) if scores else 'not_applicable'}",
        f"- cap validation enforced: {manifest.get('cap_validation_enforced')}",
        f"- cap violations count: {cap_violation_count}",
        f"- raw responses saved in live/mock mode: {bool(raw_responses) if metadata.get('mode') != 'dry_run' else 'not_applicable'}",
        f"- parse errors count: {len(parse_errors)}",
        "- no external search used by judge: True",
        f"- no weighted composite score computed: {not metadata.get('weighted_composite_computed', False)}",
        f"- pairwise preference requested: {manifest.get('pairwise_preferences_requested', False)}",
        f"- unblinding performed in this mode: {unblind}",
        "",
        "## Packet Counts",
        "",
        f"- planned candidates: {manifest.get('planned_candidate_count', 0)}",
        f"- candidate score records written: {len(scores)}",
        f"- raw responses written: {len(raw_responses)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_formulation_only_scores_csv(path: Path, rows: list[dict[str, Any]], *, unblinded: bool = False) -> None:
    fieldnames = ["candidate_id"]
    if unblinded:
        fieldnames.extend(["original_candidate_id", "domain", "method", "title"])
    else:
        fieldnames.extend(["domain", "candidate_file"])
    fieldnames.extend(FORMULATION_ONLY_CRITERIA)
    fieldnames.extend(["recommended_action", "confidence", "strengths", "weaknesses", "cap_violations", "rationale", "novelty_caveat"])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {
                "candidate_id": row.get("candidate_id"),
                "domain": row.get("domain"),
                "recommended_action": row.get("recommended_action"),
                "confidence": row.get("confidence"),
                "strengths": json.dumps(row.get("strengths", []), ensure_ascii=False),
                "weaknesses": json.dumps(row.get("weaknesses", []), ensure_ascii=False),
                "cap_violations": json.dumps(row.get("cap_violations", []), ensure_ascii=False),
                "rationale": row.get("rationale"),
                "novelty_caveat": row.get("novelty_caveat"),
            }
            if unblinded:
                flat.update(
                    {
                        "original_candidate_id": row.get("original_candidate_id"),
                        "method": row.get("method"),
                        "title": row.get("title"),
                    }
                )
            else:
                flat["candidate_file"] = row.get("candidate_file")
            for key in FORMULATION_ONLY_CRITERIA:
                flat[key] = row.get("scores", {}).get(key)
            writer.writerow(flat)


def ensure_formulation_only_output_files(
    output_dir: Path,
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw: list[dict[str, Any]],
) -> None:
    write_jsonl(output_dir / "raw_model_responses.jsonl", raw)
    write_jsonl(output_dir / "formulation_only_scores_blinded.jsonl", scores)
    write_formulation_only_scores_csv(output_dir / "formulation_only_scores_blinded.csv", scores, unblinded=False)
    write_jsonl(output_dir / "parse_errors.jsonl", parse_errors)
    write_jsonl(output_dir / "scores_blinded.jsonl", scores)
    write_formulation_only_scores_csv(output_dir / "scores_blinded.csv", scores, unblinded=False)


def formulation_only_scores_valid(scores: list[dict[str, Any]]) -> bool:
    for row in scores:
        score_map = row.get("scores")
        if not isinstance(score_map, dict):
            return False
        if set(score_map) != set(FORMULATION_ONLY_CRITERIA):
            return False
        for key in FORMULATION_ONLY_CRITERIA:
            value = score_map.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10:
                return False
        if row.get("recommended_action") not in FORMULATION_QUALITY_ACTIONS:
            return False
        if row.get("confidence") not in {"LOW", "MEDIUM", "HIGH"}:
            return False
        if not isinstance(row.get("weaknesses"), list) or not row.get("weaknesses"):
            return False
        if "weighted_composite" in json.dumps(row).lower() or "pairwise_preference" in row:
            return False
    return True


def write_formulation_only_audit(
    path: Path,
    *,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw_responses: list[dict[str, Any]],
    unblind: bool,
) -> None:
    cap_violation_count = sum(len(row.get("cap_violations", [])) for row in scores)
    lines = [
        "# Formulation-Only Judge Quality Audit",
        "",
        f"- scoring mode: {metadata.get('scoring_mode')}",
        f"- API key env var present: {metadata.get('api_key_env_present')}",
        f"- model: `{metadata.get('model')}`",
        f"- base_url specified: {bool(metadata.get('base_url'))}",
        f"- blinded candidate input exists: {Path(str(manifest.get('candidate_file'))).exists() if manifest.get('candidate_file') else False}",
        f"- blinding key not read during scoring: {not manifest.get('blinding_key_read_during_scoring', False)}",
        f"- method labels absent from judge prompts: {not manifest.get('method_label_findings_in_prompts')}",
        f"- score fields are valid 0-10 integers: {formulation_only_scores_valid(scores) if scores else 'not_applicable'}",
        f"- formulation-only fields used: {manifest.get('formulation_only_fields_used', False)}",
        f"- implementation/actionability fields excluded: {manifest.get('implementation_fields_excluded', False)}",
        f"- cap validation enforced: {manifest.get('cap_validation_enforced')}",
        f"- cap violations count: {cap_violation_count}",
        f"- raw responses saved in live/mock mode: {bool(raw_responses) if metadata.get('mode') != 'dry_run' else 'not_applicable'}",
        f"- parse errors count: {len(parse_errors)}",
        "- no external search used by judge: True",
        f"- no weighted composite score computed: {not metadata.get('weighted_composite_computed', False)}",
        f"- pairwise preference requested: {manifest.get('pairwise_preferences_requested', False)}",
        f"- unblinding performed in this mode: {unblind}",
        f"- blinding key read during postprocess: {manifest.get('blinding_key_read_during_postprocess', False)}",
        "",
        "## Packet Counts",
        "",
        f"- planned candidates: {manifest.get('planned_candidate_count', 0)}",
        f"- candidate score records written: {len(scores)}",
        f"- raw responses written: {len(raw_responses)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_personalized_formulation_scores_csv(path: Path, rows: list[dict[str, Any]], *, unblinded: bool = False) -> None:
    fieldnames = ["candidate_id"]
    if unblinded:
        fieldnames.extend(["original_candidate_id", "profile", "domain", "method", "title"])
    else:
        fieldnames.extend(["profile", "domain", "candidate_file"])
    fieldnames.extend(PERSONALIZED_FORMULATION_CRITERIA)
    fieldnames.extend(["recommended_action", "confidence", "strengths", "weaknesses", "cap_violations", "rationale", "personalization_caveat", "novelty_caveat"])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {
                "candidate_id": row.get("candidate_id"),
                "profile": row.get("profile"),
                "domain": row.get("domain"),
                "recommended_action": row.get("recommended_action"),
                "confidence": row.get("confidence"),
                "strengths": json.dumps(row.get("strengths", []), ensure_ascii=False),
                "weaknesses": json.dumps(row.get("weaknesses", []), ensure_ascii=False),
                "cap_violations": json.dumps(row.get("cap_violations", []), ensure_ascii=False),
                "rationale": row.get("rationale"),
                "personalization_caveat": row.get("personalization_caveat"),
                "novelty_caveat": row.get("novelty_caveat"),
            }
            if unblinded:
                flat.update(
                    {
                        "original_candidate_id": row.get("original_candidate_id"),
                        "method": row.get("method"),
                        "title": row.get("title"),
                    }
                )
            else:
                flat["candidate_file"] = row.get("candidate_file")
            for key in PERSONALIZED_FORMULATION_CRITERIA:
                flat[key] = row.get("scores", {}).get(key)
            writer.writerow(flat)


def ensure_personalized_formulation_output_files(
    output_dir: Path,
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw: list[dict[str, Any]],
) -> None:
    write_jsonl(output_dir / "raw_model_responses.jsonl", raw)
    write_jsonl(output_dir / "personalized_scores_blinded.jsonl", scores)
    write_personalized_formulation_scores_csv(output_dir / "personalized_scores_blinded.csv", scores, unblinded=False)
    write_jsonl(output_dir / "parse_errors.jsonl", parse_errors)
    write_jsonl(output_dir / "scores_blinded.jsonl", scores)
    write_personalized_formulation_scores_csv(output_dir / "scores_blinded.csv", scores, unblinded=False)


def personalized_formulation_scores_valid(scores: list[dict[str, Any]]) -> bool:
    for row in scores:
        score_map = row.get("scores")
        if not isinstance(score_map, dict):
            return False
        if set(score_map) != set(PERSONALIZED_FORMULATION_CRITERIA):
            return False
        for key in PERSONALIZED_FORMULATION_CRITERIA:
            value = score_map.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10:
                return False
        if row.get("recommended_action") not in FORMULATION_QUALITY_ACTIONS:
            return False
        if row.get("confidence") not in {"LOW", "MEDIUM", "HIGH"}:
            return False
        if not isinstance(row.get("weaknesses"), list) or not row.get("weaknesses"):
            return False
        if "weighted_composite" in json.dumps(row).lower() or "pairwise_preference" in row:
            return False
    return True


def write_personalized_formulation_audit(
    path: Path,
    *,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw_responses: list[dict[str, Any]],
    unblind: bool,
) -> None:
    cap_violation_count = sum(len(row.get("cap_violations", [])) for row in scores)
    lines = [
        "# Personalized Formulation Judge Quality Audit",
        "",
        f"- scoring mode: {metadata.get('scoring_mode')}",
        f"- API key env var present: {metadata.get('api_key_env_present')}",
        f"- model: `{metadata.get('model')}`",
        f"- base_url specified: {bool(metadata.get('base_url'))}",
        f"- blinded candidate input exists: {Path(str(manifest.get('candidate_file'))).exists() if manifest.get('candidate_file') else False}",
        f"- blinding key not read during scoring: {not manifest.get('blinding_key_read_during_scoring', False)}",
        f"- method labels absent from judge prompts: {not manifest.get('method_label_findings_in_prompts')}",
        f"- score fields are valid 0-10 integers: {personalized_formulation_scores_valid(scores) if scores else 'not_applicable'}",
        f"- profile name visible to judge: {manifest.get('profile_name_visible_to_judge', False)}",
        f"- hidden method labels absent: {not manifest.get('method_label_findings_in_prompts')}",
        f"- personalization fields used: {manifest.get('personalization_fields_used', False)}",
        f"- cap validation enforced: {manifest.get('cap_validation_enforced')}",
        f"- cap violations count: {cap_violation_count}",
        f"- raw responses saved in live/mock mode: {bool(raw_responses) if metadata.get('mode') != 'dry_run' else 'not_applicable'}",
        f"- parse errors count: {len(parse_errors)}",
        "- no external search used by judge: True",
        f"- no weighted composite score computed: {not metadata.get('weighted_composite_computed', False)}",
        f"- pairwise preference requested: {manifest.get('pairwise_preferences_requested', False)}",
        f"- unblinding performed in this mode: {unblind}",
        f"- blinding key read during postprocess: {manifest.get('blinding_key_read_during_postprocess', False)}",
        "",
        "## Packet Counts",
        "",
        f"- planned candidates: {manifest.get('planned_candidate_count', 0)}",
        f"- candidate score records written: {len(scores)}",
        f"- raw responses written: {len(raw_responses)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_prism_idea_quality_scores_csv(path: Path, rows: list[dict[str, Any]], *, unblinded: bool = False) -> None:
    fieldnames = ["candidate_id"]
    if unblinded:
        fieldnames.extend(["original_candidate_id", "domain", "method", "title"])
    else:
        fieldnames.extend(["domain", "candidate_file"])
    fieldnames.extend(PRISM_IDEA_QUALITY_CRITERIA)
    fieldnames.extend(["recommended_action", "confidence", "strengths", "weaknesses", "rationale", "novelty_caveat"])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {
                "candidate_id": row.get("candidate_id"),
                "domain": row.get("domain"),
                "recommended_action": row.get("recommended_action"),
                "confidence": row.get("confidence"),
                "strengths": json.dumps(row.get("strengths", []), ensure_ascii=False),
                "weaknesses": json.dumps(row.get("weaknesses", []), ensure_ascii=False),
                "rationale": row.get("rationale"),
                "novelty_caveat": row.get("novelty_caveat"),
            }
            if unblinded:
                flat.update(
                    {
                        "original_candidate_id": row.get("original_candidate_id"),
                        "method": row.get("method"),
                        "title": row.get("title"),
                    }
                )
            else:
                flat["candidate_file"] = row.get("candidate_file")
            for key in PRISM_IDEA_QUALITY_CRITERIA:
                flat[key] = row.get("scores", {}).get(key)
            writer.writerow(flat)


def ensure_prism_idea_quality_output_files(
    output_dir: Path,
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw: list[dict[str, Any]],
) -> None:
    write_jsonl(output_dir / "raw_model_responses.jsonl", raw)
    write_jsonl(output_dir / "prism_idea_quality_scores_blinded.jsonl", scores)
    write_prism_idea_quality_scores_csv(output_dir / "prism_idea_quality_scores_blinded.csv", scores, unblinded=False)
    write_jsonl(output_dir / "parse_errors.jsonl", parse_errors)
    write_jsonl(output_dir / "scores_blinded.jsonl", scores)
    write_prism_idea_quality_scores_csv(output_dir / "scores_blinded.csv", scores, unblinded=False)


def prism_idea_quality_scores_valid(scores: list[dict[str, Any]]) -> bool:
    for row in scores:
        score_map = row.get("scores")
        if not isinstance(score_map, dict):
            return False
        if set(score_map) != set(PRISM_IDEA_QUALITY_CRITERIA):
            return False
        for key in PRISM_IDEA_QUALITY_CRITERIA:
            value = score_map.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 10:
                return False
        if row.get("recommended_action") not in PRISM_IDEA_QUALITY_ACTIONS:
            return False
        if not row.get("weaknesses"):
            return False
        if "weighted_composite" in json.dumps(row).lower() or "pairwise_preference" in row:
            return False
    return True


def write_prism_idea_quality_audit(
    path: Path,
    *,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw_responses: list[dict[str, Any]],
    unblind: bool,
) -> None:
    lines = [
        "# PRISM / LiveIdeaBench-Style Judge Quality Audit",
        "",
        f"- scoring mode: {metadata.get('scoring_mode')}",
        f"- API key env var present: {metadata.get('api_key_env_present')}",
        f"- model specified: {bool(metadata.get('model'))}",
        f"- base_url specified: {bool(metadata.get('base_url'))}",
        f"- blinded candidate input exists: {Path(str(manifest.get('candidate_file'))).exists() if manifest.get('candidate_file') else False}",
        f"- blinding key not read during scoring: {not manifest.get('blinding_key_read_during_scoring', False)}",
        f"- method labels absent from judge prompts: {not manifest.get('method_label_findings_in_prompts')}",
        f"- score fields are valid 1-10 integers: {prism_idea_quality_scores_valid(scores) if scores else 'not_applicable'}",
        f"- parse errors count: {len(parse_errors)}",
        f"- raw responses saved in live/mock mode: {bool(raw_responses) if metadata.get('mode') != 'dry_run' else 'not_applicable'}",
        "- no external search used by judge: True",
        f"- no weighted composite score computed: {not metadata.get('weighted_composite_computed', False)}",
        f"- pairwise preference requested: {manifest.get('pairwise_preferences_requested', False)}",
        f"- unblinding performed in this mode: {unblind}",
        f"- blinding key read during postprocess: {manifest.get('blinding_key_read_during_postprocess', False)}",
        "",
        "## Packet Counts",
        "",
        f"- planned candidates: {manifest.get('planned_candidate_count', 'not_applicable')}",
        f"- planned pairs: {manifest.get('planned_pair_count', 0)}",
        f"- scores written: {len(scores)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_output_files(
    output_dir: Path,
    config: dict[str, Any],
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw: list[dict[str, Any]],
    *,
    scoring_mode: str,
) -> None:
    write_jsonl(output_dir / "raw_model_responses.jsonl", raw)
    write_jsonl(output_dir / "scores_blinded.jsonl", scores)
    if scoring_mode == "independent":
        write_independent_scores_csv(output_dir / "scores_blinded.csv", scores, config)
    else:
        write_scores_csv(output_dir / "scores_blinded.csv", scores, config)
    write_jsonl(output_dir / "parse_errors.jsonl", parse_errors)


def call_openrouter(config: dict[str, Any], prompt: str) -> tuple[str, dict[str, Any]]:
    judge_cfg = config["judge"]
    api_key = os.environ.get(str(judge_cfg.get("api_key_env", "OPENROUTER_API_KEY")))
    if not api_key:
        raise JudgeError("OPENROUTER_API_KEY is required for live scoring")
    base_url = str(judge_cfg["base_url"]).rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    site_url_env = judge_cfg.get("site_url_env")
    if site_url_env and os.environ.get(str(site_url_env)):
        headers["HTTP-Referer"] = os.environ[str(site_url_env)]
    if judge_cfg.get("app_title"):
        headers["X-Title"] = str(judge_cfg["app_title"])
    payload = {
        "model": judge_cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": float(judge_cfg.get("temperature", 0.0)),
        "max_tokens": int(judge_cfg.get("max_tokens", 4096)),
    }
    for optional_key in ("response_format", "reasoning", "reasoning_effort", "top_p", "seed"):
        if optional_key in judge_cfg:
            payload[optional_key] = judge_cfg[optional_key]
    last_error = None
    max_retries = int(judge_cfg.get("max_retries", 3))
    backoff = float(judge_cfg.get("retry_backoff_seconds", 5))
    for attempt in range(max_retries + 1):
        try:
            timeout_seconds = float(judge_cfg.get("timeout_seconds", 120))
            if hasattr(signal, "SIGALRM"):
                old_handler = signal.getsignal(signal.SIGALRM)

                def _handle_timeout(signum: int, frame: Any) -> None:
                    raise TimeoutError(f"OpenRouter call exceeded wall-clock timeout of {timeout_seconds:g}s")

                signal.signal(signal.SIGALRM, _handle_timeout)
                signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, old_handler)
            else:
                response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content, {"response_json": data, "attempt": attempt + 1}
        except Exception as exc:  # pragma: no cover - live path is not used in unit tests.
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(backoff)
    raise JudgeError(f"OpenRouter call failed: {last_error}")


def run_scoring(
    *,
    config: dict[str, Any],
    config_path: Path,
    comparison_root: Path,
    output_dir: Path,
    run_name: str,
    domains: list[str] | None = None,
    baseline_name: str | None = None,
    max_pairs: int | None = None,
    dry_run: bool = False,
    mock_response: str | None = None,
    no_network: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if no_network and not dry_run and not mock_response:
        raise JudgeError("--no-network requires --dry-run or --mock-response")
    if not dry_run and not mock_response:
        api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
        if not os.environ.get(api_key_env):
            raise JudgeError(f"{api_key_env} is required for live scoring")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()) and not (resume or force):
        raise JudgeError(f"Output directory is not empty; use --resume or --force: {output_dir}")

    comparison_dirs = discover_comparison_dirs(comparison_root, domains)
    all_pairs: list[CandidatePair] = []
    incomplete_pairs: list[dict[str, Any]] = []
    prompt_label_findings: list[dict[str, Any]] = []
    packet_entries = []
    for comp_dir in comparison_dirs:
        baseline = infer_baseline(comp_dir, comparison_root, baseline_name)
        candidates = load_blinded_candidates(comp_dir)
        pairs, incomplete = build_pairs(comparison_root, comp_dir, baseline, max_pairs=max_pairs)
        all_pairs.extend(pairs)
        incomplete_pairs.extend(incomplete)
        entry = {
            "comparison_dir": str(comp_dir),
            "domain": infer_domain(comp_dir, comparison_root),
            "baseline": baseline,
            "candidate_count": len(candidates),
            "pair_count": len(pairs),
            "incomplete_candidate_count": len(incomplete),
            "files": {name: str(comp_dir / name) for name in REQUIRED_PACKET_FILES},
            "blinding_key_present": (comp_dir / BLINDING_KEY_FILE).exists(),
        }
        packet_entries.append(entry)
        for pair in pairs:
            prompt = build_judge_prompt(config, pair)
            labels = labels_found_in_prompt(prompt)
            if labels:
                prompt_label_findings.append(
                    {"comparison_id": pair.comparison_id, "comparison_dir": str(comp_dir), "labels": labels}
                )

    raw_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    mock_text = load_mock_response(mock_response) if mock_response else None

    if not dry_run:
        for pair in all_pairs:
            prompt = build_judge_prompt(config, pair)
            if mock_text is not None:
                response_text = mock_text
                response_meta = {"source": "mock_response"}
            else:
                response_text, response_meta = call_openrouter(config, prompt)
            raw_responses.append(
                {
                    "comparison_id": pair.comparison_id,
                    "domain": pair.domain,
                    "baseline": pair.baseline,
                    "comparison_dir": str(pair.comparison_dir),
                    "raw_response": response_text,
                    "metadata": response_meta,
                }
            )
            try:
                parsed = parse_model_json(response_text)
                scores.append(validate_score_object(parsed, pair=pair, config=config))
            except Exception as exc:
                parse_errors.append(
                    {
                        "comparison_id": pair.comparison_id,
                        "domain": pair.domain,
                        "comparison_dir": str(pair.comparison_dir),
                        "error": str(exc),
                        "raw_response": response_text,
                    }
                )

    manifest = {
        "run_name": run_name,
        "comparison_root": str(comparison_root),
        "comparison_dir_count": len(comparison_dirs),
        "planned_pair_count": len(all_pairs),
        "incomplete_pairs": incomplete_pairs,
        "packets": packet_entries,
        "blinding_key_read_during_scoring": False,
        "method_label_findings_in_prompts": prompt_label_findings,
        "no_weighted_composite": True,
    }
    metadata = {
        "run_name": run_name,
        "created_at": utc_now_iso(),
        "mode": "dry_run" if dry_run else ("mock_response" if mock_response else "live"),
        "config_path": str(config_path),
        "comparison_root": str(comparison_root),
        "output_dir": str(output_dir),
        "model": config["judge"].get("model"),
        "base_url": config["judge"].get("base_url"),
        "api_key_env": config["judge"].get("api_key_env"),
        "api_key_env_present": bool(os.environ.get(str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY")))),
        "network_used": (not dry_run and mock_response is None),
        "external_search_used": False,
        "weighted_composite_computed": False,
        "score_count": len(scores),
        "parse_error_count": len(parse_errors),
    }
    (output_dir / "judge_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "judge_config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output_dir / "scoring_inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ensure_output_files(output_dir, config, scores, parse_errors, raw_responses, scoring_mode="pairwise")
    write_audit(
        output_dir / "judge_quality_audit.md",
        config=config,
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=parse_errors,
        raw_responses=raw_responses,
        unblind=False,
    )
    write_readme(output_dir / "README.md", metadata, manifest)
    return {"metadata": metadata, "manifest": manifest, "scores": scores, "parse_errors": parse_errors}


def run_independent_scoring(
    *,
    config: dict[str, Any],
    config_path: Path,
    candidate_file: Path,
    output_dir: Path,
    run_name: str,
    domain: str | None = None,
    dry_run: bool = False,
    mock_response: str | None = None,
    no_network: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if no_network and not dry_run and not mock_response:
        raise JudgeError("--no-network requires --dry-run or --mock-response")
    if not dry_run and not mock_response:
        api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
        if not os.environ.get(api_key_env):
            raise JudgeError(f"{api_key_env} is required for live scoring")
    output_dir.mkdir(parents=True, exist_ok=True)
    allowed_existing = {candidate_file.resolve()}
    allowed_existing.update(path.resolve() for path in output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))
    existing = [path for path in output_dir.iterdir() if path.resolve() not in allowed_existing]
    if existing and not (resume or force):
        raise JudgeError(f"Output directory contains scoring outputs; use --resume or --force: {output_dir}")

    candidates = load_independent_candidates(candidate_file, domain=domain)
    prompt_label_findings = []
    for candidate in candidates:
        prompt = build_independent_judge_prompt(config, candidate)
        labels = labels_found_in_prompt(prompt)
        if labels:
            prompt_label_findings.append(
                {"candidate_id": candidate.candidate_id, "candidate_file": str(candidate_file), "labels": labels}
            )

    raw_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    mock_text = load_mock_response(mock_response) if mock_response else None

    if not dry_run:
        for candidate in candidates:
            prompt = build_independent_judge_prompt(config, candidate)
            if mock_text is not None:
                response_text = mock_text
                response_meta = {"source": "mock_response"}
            else:
                response_text, response_meta = call_openrouter(config, prompt)
            raw_responses.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "domain": candidate.domain,
                    "candidate_file": str(candidate.candidate_file),
                    "raw_response": response_text,
                    "metadata": response_meta,
                }
            )
            try:
                parsed = parse_model_json(response_text)
                scores.append(validate_independent_score_object(parsed, candidate=candidate, config=config))
            except Exception as exc:
                parse_errors.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "domain": candidate.domain,
                        "candidate_file": str(candidate.candidate_file),
                        "error": str(exc),
                        "raw_response": response_text,
                    }
                )

    manifest = {
        "run_name": run_name,
        "scoring_mode": "independent",
        "candidate_file": str(candidate_file),
        "planned_candidate_count": len(candidates),
        "planned_pair_count": 0,
        "packets": [
            {
                "candidate_file": str(candidate_file),
                "domain": domain or sorted({candidate.domain for candidate in candidates}),
                "candidate_count": len(candidates),
                "pair_count": 0,
                "files": {"independent_candidates": str(candidate_file)},
                "blinding_key_present": bool(list(output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))),
            }
        ],
        "blinding_key_read_during_scoring": False,
        "method_label_findings_in_prompts": prompt_label_findings,
        "no_weighted_composite": True,
        "pairwise_preferences_requested": False,
    }
    metadata = {
        "run_name": run_name,
        "created_at": utc_now_iso(),
        "mode": "dry_run" if dry_run else ("mock_response" if mock_response else "live"),
        "scoring_mode": "independent",
        "config_path": str(config_path),
        "candidate_file": str(candidate_file),
        "output_dir": str(output_dir),
        "model": config["judge"].get("model"),
        "base_url": config["judge"].get("base_url"),
        "api_key_env": config["judge"].get("api_key_env"),
        "api_key_env_present": bool(os.environ.get(str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY")))),
        "network_used": (not dry_run and mock_response is None),
        "external_search_used": False,
        "weighted_composite_computed": False,
        "pairwise_enabled": False,
        "score_count": len(scores),
        "parse_error_count": len(parse_errors),
    }
    (output_dir / "judge_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "judge_config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output_dir / "scoring_inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ensure_output_files(output_dir, config, scores, parse_errors, raw_responses, scoring_mode="independent")
    write_audit(
        output_dir / "judge_quality_audit.md",
        config=config,
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=parse_errors,
        raw_responses=raw_responses,
        unblind=False,
    )
    write_readme(output_dir / "README.md", metadata, manifest)
    return {"metadata": metadata, "manifest": manifest, "scores": scores, "parse_errors": parse_errors}


def run_batch_calibrated_independent_scoring(
    *,
    config: dict[str, Any],
    config_path: Path,
    candidate_file: Path,
    output_dir: Path,
    run_name: str,
    domain: str | None = None,
    dry_run: bool = False,
    mock_response: str | None = None,
    no_network: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if no_network and not dry_run and not mock_response:
        raise JudgeError("--no-network requires --dry-run or --mock-response")
    if not dry_run and not mock_response:
        api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
        if not os.environ.get(api_key_env):
            raise JudgeError(f"{api_key_env} is required for live scoring")
    output_dir.mkdir(parents=True, exist_ok=True)
    allowed_existing = {candidate_file.resolve()}
    allowed_existing.update(path.resolve() for path in output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))
    existing = [path for path in output_dir.iterdir() if path.resolve() not in allowed_existing]
    if existing and not (resume or force):
        raise JudgeError(f"Output directory contains scoring outputs; use --resume or --force: {output_dir}")

    candidates = load_independent_candidates(candidate_file, domain=domain)
    prompt = build_batch_calibrated_judge_prompt(config, candidates)
    prompt_label_findings = []
    labels = labels_found_in_prompt(prompt)
    if labels:
        prompt_label_findings.append({"candidate_file": str(candidate_file), "labels": labels})

    raw_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    mock_text = load_mock_response(mock_response) if mock_response else None
    batch_calibration_notes = ""

    if not dry_run:
        if mock_text is not None:
            response_text = mock_text
            response_meta = {"source": "mock_response"}
        else:
            response_text, response_meta = call_openrouter(config, prompt)
        raw_responses.append(
            {
                "candidate_file": str(candidate_file),
                "candidate_count": len(candidates),
                "domain": domain or sorted({candidate.domain for candidate in candidates}),
                "raw_response": response_text,
                "metadata": response_meta,
            }
        )
        try:
            parsed = parse_model_json(response_text)
            scores, batch_calibration_notes = validate_batch_calibrated_score_object(
                parsed,
                candidates=candidates,
                config=config,
            )
        except Exception as exc:
            parse_errors.append(
                {
                    "candidate_file": str(candidate_file),
                    "candidate_count": len(candidates),
                    "domain": domain or sorted({candidate.domain for candidate in candidates}),
                    "error": str(exc),
                    "raw_response": response_text,
                }
            )

    manifest = {
        "run_name": run_name,
        "scoring_mode": "independent_batch_calibrated",
        "candidate_file": str(candidate_file),
        "planned_candidate_count": len(candidates),
        "planned_pair_count": 0,
        "batch_prompt_count": 1,
        "packets": [
            {
                "candidate_file": str(candidate_file),
                "domain": domain or sorted({candidate.domain for candidate in candidates}),
                "candidate_count": len(candidates),
                "pair_count": 0,
                "files": {"independent_candidates": str(candidate_file)},
                "blinding_key_present": bool(list(output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))),
            }
        ],
        "blinding_key_read_during_scoring": False,
        "method_label_findings_in_prompts": prompt_label_findings,
        "no_weighted_composite": True,
        "pairwise_preferences_requested": False,
        "batch_calibrated_prompt": True,
    }
    metadata = {
        "run_name": run_name,
        "created_at": utc_now_iso(),
        "mode": "dry_run" if dry_run else ("mock_response" if mock_response else "live"),
        "scoring_mode": "independent_batch_calibrated",
        "config_path": str(config_path),
        "candidate_file": str(candidate_file),
        "output_dir": str(output_dir),
        "model": config["judge"].get("model"),
        "base_url": config["judge"].get("base_url"),
        "api_key_env": config["judge"].get("api_key_env"),
        "api_key_env_present": bool(os.environ.get(str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY")))),
        "network_used": (not dry_run and mock_response is None),
        "external_search_used": False,
        "weighted_composite_computed": False,
        "pairwise_enabled": False,
        "score_count": len(scores),
        "parse_error_count": len(parse_errors),
        "batch_calibration_notes": batch_calibration_notes,
    }
    (output_dir / "judge_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "judge_config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output_dir / "scoring_inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ensure_output_files(output_dir, config, scores, parse_errors, raw_responses, scoring_mode="independent")
    write_audit(
        output_dir / "judge_quality_audit.md",
        config=config,
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=parse_errors,
        raw_responses=raw_responses,
        unblind=False,
    )
    write_readme(output_dir / "README.md", metadata, manifest)
    return {"metadata": metadata, "manifest": manifest, "scores": scores, "parse_errors": parse_errors}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mock_response_sequence(mock_response: str | None) -> list[str]:
    if not mock_response:
        return []
    text = load_mock_response(mock_response)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1 and all(line.startswith("{") for line in lines):
        return lines
    return [text]


def _mock_response_for_call(sequence: list[str], index: int) -> str:
    if not sequence:
        raise JudgeError("mock response sequence is empty")
    if index < len(sequence):
        return sequence[index]
    return sequence[-1]


def run_role_based_scoring(
    *,
    config: dict[str, Any],
    config_path: Path,
    candidate_file: Path,
    output_dir: Path,
    run_name: str,
    domain: str | None = None,
    dry_run: bool = False,
    mock_response: str | None = None,
    no_network: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if no_network and not dry_run and not mock_response:
        raise JudgeError("--no-network requires --dry-run or --mock-response")
    if not dry_run and not mock_response:
        api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
        if not os.environ.get(api_key_env):
            raise JudgeError(f"{api_key_env} is required for live scoring")
    output_dir.mkdir(parents=True, exist_ok=True)
    allowed_existing = {candidate_file.resolve()}
    allowed_existing.update(path.resolve() for path in output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))
    existing = [path for path in output_dir.iterdir() if path.resolve() not in allowed_existing]
    if existing and not (resume or force):
        raise JudgeError(f"Output directory contains scoring outputs; use --resume or --force: {output_dir}")

    candidates = load_independent_candidates(candidate_file, domain=domain)
    roles = role_definitions(config)
    prompt_label_findings: list[dict[str, Any]] = []
    for candidate in candidates:
        for role in roles:
            role_id = str(role["id"])
            prompt = build_role_based_judge_prompt(config, candidate, role_id)
            labels = labels_found_in_prompt(prompt)
            if labels:
                prompt_label_findings.append({"candidate_id": candidate.candidate_id, "role_id": role_id, "labels": labels})
    if prompt_label_findings:
        raise JudgeError(f"Role-based prompts contain forbidden method labels: {prompt_label_findings}")

    raw_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    mock_sequence = _mock_response_sequence(mock_response)
    mock_index = 0
    max_cap_retries = int(config.get("evaluation", {}).get("max_cap_violation_retries", 1))
    retry_on_cap_violation = bool(config.get("evaluation", {}).get("retry_on_cap_violation", True))

    if not dry_run:
        for candidate in candidates:
            candidate_role_scores: dict[str, dict[str, Any]] = {}
            candidate_cap_rules: list[str] = []
            candidate_cap_violations: list[str] = []
            invalid_roles: list[str] = []
            for role in roles:
                role_id = str(role["id"])
                retry_feedback: list[str] | None = None
                parsed_role: dict[str, Any] | None = None
                role_errors: list[str] = []
                role_triggered: list[str] = []
                attempts_allowed = 1 + (max_cap_retries if retry_on_cap_violation else 0)
                for attempt in range(1, attempts_allowed + 1):
                    prompt = build_role_based_judge_prompt(config, candidate, role_id, retry_feedback=retry_feedback)
                    if mock_sequence:
                        response_text = _mock_response_for_call(mock_sequence, mock_index)
                        mock_index += 1
                        response_meta = {"source": "mock_response", "attempt": attempt}
                    else:
                        response_text, response_meta = call_openrouter(config, prompt)
                    raw_responses.append(
                        {
                            "candidate_id": candidate.candidate_id,
                            "domain": candidate.domain,
                            "candidate_file": str(candidate.candidate_file),
                            "role_id": role_id,
                            "attempt": attempt,
                            "prompt_sha256": _sha256_text(prompt),
                            "raw_response": response_text,
                            "metadata": response_meta,
                        }
                    )
                    try:
                        parsed = parse_model_json(response_text)
                        role_record = validate_role_score_response(parsed, candidate=candidate, config=config, role_id=role_id)
                        role_triggered, role_errors = validate_role_cap_rules(candidate, role_id=role_id, role_record=role_record)
                        if role_errors and attempt < attempts_allowed:
                            retry_feedback = role_errors
                            continue
                        parsed_role = role_record
                        break
                    except Exception as exc:
                        role_errors = [str(exc)]
                        if attempt < attempts_allowed and retry_on_cap_violation:
                            retry_feedback = role_errors
                            continue
                        break
                candidate_cap_rules.extend(f"{role_id}:{item}" for item in role_triggered)
                if role_errors:
                    invalid_roles.append(role_id)
                    candidate_cap_violations.extend(f"{role_id}: {item}" for item in role_errors)
                    parse_errors.append(
                        {
                            "candidate_id": candidate.candidate_id,
                            "domain": candidate.domain,
                            "candidate_file": str(candidate.candidate_file),
                            "role_id": role_id,
                            "error": "; ".join(role_errors),
                            "attempts": attempts_allowed,
                        }
                    )
                if parsed_role is not None:
                    candidate_role_scores[role_id] = parsed_role
            scores.append(
                aggregate_role_scores(
                    candidate=candidate,
                    role_scores=candidate_role_scores,
                    cap_rules_triggered=candidate_cap_rules,
                    cap_violations=candidate_cap_violations,
                    invalid_roles=invalid_roles,
                )
            )

    manifest = {
        "run_name": run_name,
        "scoring_mode": ROLE_BASED_MODE,
        "candidate_file": str(candidate_file),
        "planned_candidate_count": len(candidates),
        "planned_role_count": len(candidates) * len(roles),
        "planned_pair_count": 0,
        "roles": [{"id": role.get("id"), "scores": role.get("scores")} for role in roles],
        "packets": [
            {
                "candidate_file": str(candidate_file),
                "domain": domain or sorted({candidate.domain for candidate in candidates}),
                "candidate_count": len(candidates),
                "pair_count": 0,
                "files": {"independent_candidates": str(candidate_file)},
                "blinding_key_present": bool(list(output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))),
            }
        ],
        "blinding_key_read_during_scoring": False,
        "method_label_findings_in_prompts": prompt_label_findings,
        "no_weighted_composite": True,
        "pairwise_preferences_requested": False,
        "role_based": True,
        "cap_validation_enforced": bool(config.get("evaluation", {}).get("enforce_cap_rules", False)),
        "retry_on_cap_violation": retry_on_cap_violation,
        "max_cap_violation_retries": max_cap_retries,
    }
    metadata = {
        "run_name": run_name,
        "created_at": utc_now_iso(),
        "mode": "dry_run" if dry_run else ("mock_response" if mock_response else "live"),
        "scoring_mode": ROLE_BASED_MODE,
        "config_path": str(config_path),
        "candidate_file": str(candidate_file),
        "output_dir": str(output_dir),
        "model": config["judge"].get("model"),
        "base_url": config["judge"].get("base_url"),
        "api_key_env": config["judge"].get("api_key_env"),
        "api_key_env_present": bool(os.environ.get(str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY")))),
        "network_used": (not dry_run and mock_response is None),
        "external_search_used": False,
        "weighted_composite_computed": False,
        "pairwise_enabled": False,
        "score_count": len(scores),
        "role_response_count": len(raw_responses),
        "parse_error_count": len(parse_errors),
        "cap_violation_count": sum(len(row.get("cap_violations", [])) for row in scores),
    }
    (output_dir / "judge_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "judge_config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output_dir / "scoring_inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ensure_role_based_output_files(output_dir, config, scores, parse_errors, raw_responses)
    write_role_based_audit(
        output_dir / "judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=parse_errors,
        raw_responses=raw_responses,
        unblind=False,
    )
    write_readme(output_dir / "README.md", metadata, manifest)
    return {"metadata": metadata, "manifest": manifest, "scores": scores, "parse_errors": parse_errors}


def run_formulation_quality_scoring(
    *,
    config: dict[str, Any],
    config_path: Path,
    candidate_file: Path,
    output_dir: Path,
    run_name: str,
    domain: str | None = None,
    dry_run: bool = False,
    mock_response: str | None = None,
    no_network: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if no_network and not dry_run and not mock_response:
        raise JudgeError("--no-network requires --dry-run or --mock-response")
    if not dry_run and not mock_response:
        api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
        if not os.environ.get(api_key_env):
            raise JudgeError(f"{api_key_env} is required for live scoring")
    output_dir.mkdir(parents=True, exist_ok=True)
    allowed_existing = {candidate_file.resolve()}
    existing = [path for path in output_dir.iterdir() if path.resolve() not in allowed_existing]
    if existing and not (resume or force):
        raise JudgeError(f"Output directory contains scoring outputs; use --resume or --force: {output_dir}")

    candidates = load_independent_candidates(candidate_file, domain=domain)
    prompt_label_findings: list[dict[str, Any]] = []
    for candidate in candidates:
        prompt = build_formulation_quality_judge_prompt(config, candidate)
        labels = labels_found_in_prompt(prompt)
        if labels:
            prompt_label_findings.append({"candidate_id": candidate.candidate_id, "candidate_file": str(candidate_file), "labels": labels})
    if prompt_label_findings:
        raise JudgeError(f"Formulation-quality prompts contain forbidden method labels: {prompt_label_findings}")

    raw_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    mock_sequence = _mock_response_sequence(mock_response)
    mock_index = 0
    max_cap_retries = int(config.get("evaluation", {}).get("max_cap_violation_retries", 1))
    retry_on_cap_violation = bool(config.get("evaluation", {}).get("retry_on_cap_violation", True))

    if not dry_run:
        for candidate in candidates:
            parsed_score: dict[str, Any] | None = None
            errors: list[str] = []
            attempts_allowed = 1 + (max_cap_retries if retry_on_cap_violation else 0)
            retry_feedback: list[str] | None = None
            for attempt in range(1, attempts_allowed + 1):
                prompt = build_formulation_quality_judge_prompt(config, candidate, retry_feedback=retry_feedback)
                if mock_sequence:
                    response_text = _mock_response_for_call(mock_sequence, mock_index)
                    mock_index += 1
                    response_meta = {"source": "mock_response", "attempt": attempt}
                else:
                    try:
                        response_text, response_meta = call_openrouter(config, prompt)
                    except Exception as exc:
                        errors = [str(exc)]
                        raw_responses.append(
                            {
                                "candidate_id": candidate.candidate_id,
                                "domain": candidate.domain,
                                "candidate_file": str(candidate.candidate_file),
                                "attempt": attempt,
                                "prompt_sha256": _sha256_text(prompt),
                                "raw_response": "",
                                "metadata": {"error": str(exc), "attempt": attempt},
                            }
                        )
                        if attempt < attempts_allowed:
                            retry_feedback = errors
                            continue
                        break
                raw_responses.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "domain": candidate.domain,
                        "candidate_file": str(candidate.candidate_file),
                        "attempt": attempt,
                        "prompt_sha256": _sha256_text(prompt),
                        "raw_response": response_text,
                        "metadata": response_meta,
                    }
                )
                try:
                    parsed = parse_model_json(response_text)
                    candidate_score = validate_formulation_quality_score_object(parsed, candidate=candidate)
                    errors = list(candidate_score.get("cap_violations", []))
                    if errors and attempt < attempts_allowed:
                        retry_feedback = errors
                        continue
                    parsed_score = candidate_score
                    break
                except Exception as exc:
                    errors = [str(exc)]
                    if attempt < attempts_allowed:
                        retry_feedback = errors
                        continue
                    break
            if parsed_score is not None:
                scores.append(parsed_score)
            else:
                parse_errors.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "domain": candidate.domain,
                        "candidate_file": str(candidate.candidate_file),
                        "error": "; ".join(errors),
                        "attempts": attempts_allowed,
                    }
                )
            ensure_formulation_only_output_files(output_dir, scores, parse_errors, raw_responses)

    manifest = {
        "run_name": run_name,
        "scoring_mode": FORMULATION_QUALITY_MODE,
        "candidate_file": str(candidate_file),
        "planned_candidate_count": len(candidates),
        "planned_pair_count": 0,
        "packets": [
            {
                "candidate_file": str(candidate_file),
                "domain": domain or sorted({candidate.domain for candidate in candidates}),
                "candidate_count": len(candidates),
                "pair_count": 0,
                "files": {"independent_candidates": str(candidate_file)},
                "blinding_key_present": False,
            }
        ],
        "blinding_key_read_during_scoring": False,
        "method_label_findings_in_prompts": prompt_label_findings,
        "no_weighted_composite": True,
        "pairwise_preferences_requested": False,
        "cap_validation_enforced": True,
        "retry_on_cap_violation": retry_on_cap_violation,
        "max_cap_violation_retries": max_cap_retries,
    }
    metadata = {
        "run_name": run_name,
        "created_at": utc_now_iso(),
        "mode": "dry_run" if dry_run else ("mock_response" if mock_response else "live"),
        "scoring_mode": FORMULATION_QUALITY_MODE,
        "config_path": str(config_path),
        "candidate_file": str(candidate_file),
        "output_dir": str(output_dir),
        "model": config["judge"].get("model"),
        "base_url": config["judge"].get("base_url"),
        "api_key_env": config["judge"].get("api_key_env"),
        "api_key_env_present": bool(os.environ.get(str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY")))),
        "network_used": (not dry_run and mock_response is None),
        "external_search_used": False,
        "weighted_composite_computed": False,
        "pairwise_enabled": False,
        "score_count": len(scores),
        "parse_error_count": len(parse_errors),
        "cap_violation_count": sum(len(row.get("cap_violations", [])) for row in scores),
    }
    (output_dir / "judge_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "judge_config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output_dir / "scoring_inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ensure_formulation_quality_output_files(output_dir, scores, parse_errors, raw_responses)
    write_formulation_quality_audit(
        output_dir / "formulation_quality_judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=parse_errors,
        raw_responses=raw_responses,
        unblind=False,
    )
    write_readme(output_dir / "README.md", metadata, manifest)
    return {"metadata": metadata, "manifest": manifest, "scores": scores, "parse_errors": parse_errors}


def run_formulation_only_scoring(
    *,
    config: dict[str, Any],
    config_path: Path,
    candidate_file: Path,
    output_dir: Path,
    run_name: str,
    domain: str | None = None,
    dry_run: bool = False,
    mock_response: str | None = None,
    no_network: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if no_network and not dry_run and not mock_response:
        raise JudgeError("--no-network requires --dry-run or --mock-response")
    if not dry_run and not mock_response:
        api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
        if not os.environ.get(api_key_env):
            raise JudgeError(f"{api_key_env} is required for live scoring")
    output_dir.mkdir(parents=True, exist_ok=True)
    allowed_existing = {candidate_file.resolve()}
    existing = [path for path in output_dir.iterdir() if path.resolve() not in allowed_existing]
    if existing and not (resume or force):
        raise JudgeError(f"Output directory contains scoring outputs; use --resume or --force: {output_dir}")

    candidates = load_independent_candidates(candidate_file, domain=domain)
    prompt_label_findings: list[dict[str, Any]] = []
    for candidate in candidates:
        prompt = build_formulation_only_judge_prompt(config, candidate)
        labels = labels_found_in_prompt(prompt)
        if re.search(r"\bbaselines?\b", prompt, re.IGNORECASE):
            labels.append("baseline")
        if labels:
            prompt_label_findings.append({"candidate_id": candidate.candidate_id, "candidate_file": str(candidate_file), "labels": labels})
    if prompt_label_findings:
        raise JudgeError(f"Formulation-only prompts contain forbidden method labels: {prompt_label_findings}")

    raw_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    mock_sequence = _mock_response_sequence(mock_response)
    mock_index = 0
    max_cap_retries = int(config.get("evaluation", {}).get("max_cap_violation_retries", 1))
    retry_on_cap_violation = bool(config.get("evaluation", {}).get("retry_on_cap_violation", True))

    if not dry_run:
        for candidate in candidates:
            parsed_score: dict[str, Any] | None = None
            errors: list[str] = []
            attempts_allowed = 1 + (max_cap_retries if retry_on_cap_violation else 0)
            retry_feedback: list[str] | None = None
            for attempt in range(1, attempts_allowed + 1):
                prompt = build_formulation_only_judge_prompt(config, candidate, retry_feedback=retry_feedback)
                if mock_sequence:
                    response_text = _mock_response_for_call(mock_sequence, mock_index)
                    mock_index += 1
                    response_meta = {"source": "mock_response", "attempt": attempt}
                else:
                    try:
                        response_text, response_meta = call_openrouter(config, prompt)
                    except Exception as exc:
                        errors = [str(exc)]
                        raw_responses.append(
                            {
                                "candidate_id": candidate.candidate_id,
                                "domain": candidate.domain,
                                "candidate_file": str(candidate.candidate_file),
                                "attempt": attempt,
                                "prompt_sha256": _sha256_text(prompt),
                                "raw_response": "",
                                "metadata": {"error": str(exc), "attempt": attempt},
                            }
                        )
                        if attempt < attempts_allowed:
                            retry_feedback = errors
                            continue
                        break
                raw_responses.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "domain": candidate.domain,
                        "candidate_file": str(candidate.candidate_file),
                        "attempt": attempt,
                        "prompt_sha256": _sha256_text(prompt),
                        "raw_response": response_text,
                        "metadata": response_meta,
                    }
                )
                try:
                    parsed = parse_model_json(response_text)
                    candidate_score = validate_formulation_only_score_object(parsed, candidate=candidate)
                    errors = list(candidate_score.get("cap_violations", []))
                    if errors and attempt < attempts_allowed:
                        retry_feedback = errors
                        continue
                    parsed_score = candidate_score
                    break
                except Exception as exc:
                    errors = [str(exc)]
                    if attempt < attempts_allowed:
                        retry_feedback = errors
                        continue
                    break
            if parsed_score is not None:
                scores.append(parsed_score)
            else:
                parse_errors.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "domain": candidate.domain,
                        "candidate_file": str(candidate.candidate_file),
                        "error": "; ".join(errors),
                        "attempts": attempts_allowed,
                    }
                )
            ensure_formulation_only_output_files(output_dir, scores, parse_errors, raw_responses)

    manifest = {
        "run_name": run_name,
        "scoring_mode": FORMULATION_ONLY_MODE,
        "candidate_file": str(candidate_file),
        "planned_candidate_count": len(candidates),
        "planned_pair_count": 0,
        "packets": [
            {
                "candidate_file": str(candidate_file),
                "domain": domain or sorted({candidate.domain for candidate in candidates}),
                "candidate_count": len(candidates),
                "pair_count": 0,
                "files": {"independent_candidates": str(candidate_file)},
                "blinding_key_present": False,
            }
        ],
        "blinding_key_read_during_scoring": False,
        "method_label_findings_in_prompts": prompt_label_findings,
        "no_weighted_composite": True,
        "pairwise_preferences_requested": False,
        "cap_validation_enforced": True,
        "retry_on_cap_violation": retry_on_cap_violation,
        "max_cap_violation_retries": max_cap_retries,
        "formulation_only_fields_used": True,
        "implementation_fields_excluded": True,
    }
    metadata = {
        "run_name": run_name,
        "created_at": utc_now_iso(),
        "mode": "dry_run" if dry_run else ("mock_response" if mock_response else "live"),
        "scoring_mode": FORMULATION_ONLY_MODE,
        "config_path": str(config_path),
        "candidate_file": str(candidate_file),
        "output_dir": str(output_dir),
        "model": config["judge"].get("model"),
        "base_url": config["judge"].get("base_url"),
        "api_key_env": config["judge"].get("api_key_env"),
        "api_key_env_present": bool(os.environ.get(str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY")))),
        "network_used": (not dry_run and mock_response is None),
        "external_search_used": False,
        "weighted_composite_computed": False,
        "pairwise_enabled": False,
        "score_count": len(scores),
        "parse_error_count": len(parse_errors),
        "cap_violation_count": sum(len(row.get("cap_violations", [])) for row in scores),
    }
    (output_dir / "judge_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "judge_config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output_dir / "scoring_inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ensure_formulation_only_output_files(output_dir, scores, parse_errors, raw_responses)
    write_formulation_only_audit(
        output_dir / "formulation_only_judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=parse_errors,
        raw_responses=raw_responses,
        unblind=False,
    )
    write_readme(output_dir / "README.md", metadata, manifest)
    return {"metadata": metadata, "manifest": manifest, "scores": scores, "parse_errors": parse_errors}


def run_personalized_formulation_scoring(
    *,
    config: dict[str, Any],
    config_path: Path,
    candidate_file: Path,
    output_dir: Path,
    run_name: str,
    domain: str | None = None,
    dry_run: bool = False,
    mock_response: str | None = None,
    no_network: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if no_network and not dry_run and not mock_response:
        raise JudgeError("--no-network requires --dry-run or --mock-response")
    if not dry_run and not mock_response:
        api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
        if not os.environ.get(api_key_env):
            raise JudgeError(f"{api_key_env} is required for live scoring")
    output_dir.mkdir(parents=True, exist_ok=True)
    allowed_existing = {candidate_file.resolve()}
    existing = [path for path in output_dir.iterdir() if path.resolve() not in allowed_existing]
    if existing and not (resume or force):
        raise JudgeError(f"Output directory contains scoring outputs; use --resume or --force: {output_dir}")

    candidates = load_independent_candidates(candidate_file, domain=domain)
    prompt_label_findings: list[dict[str, Any]] = []
    for candidate in candidates:
        prompt = build_personalized_formulation_judge_prompt(config, candidate)
        labels = labels_found_in_prompt(prompt)
        if re.search(r"\bbaselines?\b", prompt, re.IGNORECASE):
            labels.append("baseline")
        if labels:
            prompt_label_findings.append({"candidate_id": candidate.candidate_id, "candidate_file": str(candidate_file), "labels": labels})
    if prompt_label_findings:
        raise JudgeError(f"Personalized formulation prompts contain forbidden method labels: {prompt_label_findings}")

    raw_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    mock_sequence = _mock_response_sequence(mock_response)
    mock_index = 0
    max_cap_retries = int(config.get("evaluation", {}).get("max_cap_violation_retries", 1))
    retry_on_cap_violation = bool(config.get("evaluation", {}).get("retry_on_cap_violation", True))

    if not dry_run:
        for candidate in candidates:
            parsed_score: dict[str, Any] | None = None
            errors: list[str] = []
            attempts_allowed = 1 + (max_cap_retries if retry_on_cap_violation else 0)
            retry_feedback: list[str] | None = None
            for attempt in range(1, attempts_allowed + 1):
                prompt = build_personalized_formulation_judge_prompt(config, candidate, retry_feedback=retry_feedback)
                if mock_sequence:
                    response_text = _mock_response_for_call(mock_sequence, mock_index)
                    mock_index += 1
                    response_meta = {"source": "mock_response", "attempt": attempt}
                else:
                    try:
                        response_text, response_meta = call_openrouter(config, prompt)
                    except Exception as exc:
                        errors = [str(exc)]
                        raw_responses.append(
                            {
                                "candidate_id": candidate.candidate_id,
                                "profile": _json_text(candidate.candidate.get("profile")),
                                "domain": candidate.domain,
                                "candidate_file": str(candidate.candidate_file),
                                "attempt": attempt,
                                "prompt_sha256": _sha256_text(prompt),
                                "raw_response": "",
                                "metadata": {"error": str(exc), "attempt": attempt},
                            }
                        )
                        if attempt < attempts_allowed:
                            retry_feedback = errors
                            continue
                        break
                raw_responses.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "profile": _json_text(candidate.candidate.get("profile")),
                        "domain": candidate.domain,
                        "candidate_file": str(candidate.candidate_file),
                        "attempt": attempt,
                        "prompt_sha256": _sha256_text(prompt),
                        "raw_response": response_text,
                        "metadata": response_meta,
                    }
                )
                try:
                    parsed = parse_model_json(response_text)
                    candidate_score = validate_personalized_formulation_score_object(parsed, candidate=candidate)
                    errors = list(candidate_score.get("cap_violations", []))
                    if errors and attempt < attempts_allowed:
                        retry_feedback = errors
                        continue
                    parsed_score = candidate_score
                    break
                except Exception as exc:
                    errors = [str(exc)]
                    if attempt < attempts_allowed:
                        retry_feedback = errors
                        continue
                    break
            if parsed_score is not None:
                scores.append(parsed_score)
            else:
                parse_errors.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "profile": _json_text(candidate.candidate.get("profile")),
                        "domain": candidate.domain,
                        "candidate_file": str(candidate.candidate_file),
                        "error": "; ".join(errors),
                        "attempts": attempts_allowed,
                    }
                )
            ensure_personalized_formulation_output_files(output_dir, scores, parse_errors, raw_responses)

    manifest = {
        "run_name": run_name,
        "scoring_mode": PERSONALIZED_FORMULATION_MODE,
        "candidate_file": str(candidate_file),
        "planned_candidate_count": len(candidates),
        "planned_pair_count": 0,
        "packets": [
            {
                "candidate_file": str(candidate_file),
                "domain": domain or sorted({candidate.domain for candidate in candidates}),
                "candidate_count": len(candidates),
                "pair_count": 0,
                "files": {"independent_candidates": str(candidate_file)},
                "blinding_key_present": False,
            }
        ],
        "blinding_key_read_during_scoring": False,
        "method_label_findings_in_prompts": prompt_label_findings,
        "no_weighted_composite": True,
        "pairwise_preferences_requested": False,
        "cap_validation_enforced": True,
        "retry_on_cap_violation": retry_on_cap_violation,
        "max_cap_violation_retries": max_cap_retries,
        "personalization_fields_used": True,
        "profile_name_visible_to_judge": True,
    }
    metadata = {
        "run_name": run_name,
        "created_at": utc_now_iso(),
        "mode": "dry_run" if dry_run else ("mock_response" if mock_response else "live"),
        "scoring_mode": PERSONALIZED_FORMULATION_MODE,
        "config_path": str(config_path),
        "candidate_file": str(candidate_file),
        "output_dir": str(output_dir),
        "model": config["judge"].get("model"),
        "base_url": config["judge"].get("base_url"),
        "api_key_env": config["judge"].get("api_key_env"),
        "api_key_env_present": bool(os.environ.get(str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY")))),
        "network_used": (not dry_run and mock_response is None),
        "external_search_used": False,
        "weighted_composite_computed": False,
        "pairwise_enabled": False,
        "score_count": len(scores),
        "parse_error_count": len(parse_errors),
        "cap_violation_count": sum(len(row.get("cap_violations", [])) for row in scores),
    }
    (output_dir / "judge_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "judge_config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output_dir / "scoring_inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ensure_personalized_formulation_output_files(output_dir, scores, parse_errors, raw_responses)
    write_personalized_formulation_audit(
        output_dir / "judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=parse_errors,
        raw_responses=raw_responses,
        unblind=False,
    )
    write_readme(output_dir / "README.md", metadata, manifest)
    return {"metadata": metadata, "manifest": manifest, "scores": scores, "parse_errors": parse_errors}


def run_prism_idea_quality_scoring(
    *,
    config: dict[str, Any],
    config_path: Path,
    candidate_file: Path,
    output_dir: Path,
    run_name: str,
    domain: str | None = None,
    dry_run: bool = False,
    mock_response: str | None = None,
    no_network: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if no_network and not dry_run and not mock_response:
        raise JudgeError("--no-network requires --dry-run or --mock-response")
    if not dry_run and not mock_response:
        api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
        if not os.environ.get(api_key_env):
            raise JudgeError(f"{api_key_env} is required for live scoring")
    output_dir.mkdir(parents=True, exist_ok=True)
    allowed_existing = {candidate_file.resolve()}
    existing = [path for path in output_dir.iterdir() if path.resolve() not in allowed_existing]
    if existing and not (resume or force):
        raise JudgeError(f"Output directory contains scoring outputs; use --resume or --force: {output_dir}")

    candidates = load_independent_candidates(candidate_file, domain=domain)
    prompt_label_findings: list[dict[str, Any]] = []
    for candidate in candidates:
        prompt = build_prism_idea_quality_judge_prompt(config, candidate)
        labels = labels_found_in_prompt(prompt)
        if labels:
            prompt_label_findings.append({"candidate_id": candidate.candidate_id, "candidate_file": str(candidate_file), "labels": labels})
    if prompt_label_findings:
        raise JudgeError(f"PRISM idea-quality prompts contain forbidden method labels: {prompt_label_findings}")

    raw_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    mock_sequence = _mock_response_sequence(mock_response)
    mock_index = 0

    if not dry_run:
        for candidate in candidates:
            parsed_score: dict[str, Any] | None = None
            errors: list[str] = []
            retry_feedback: list[str] | None = None
            for attempt in range(1, 3):
                prompt = build_prism_idea_quality_judge_prompt(config, candidate, retry_feedback=retry_feedback)
                if mock_sequence:
                    response_text = _mock_response_for_call(mock_sequence, mock_index)
                    mock_index += 1
                    response_meta = {"source": "mock_response", "attempt": attempt}
                else:
                    response_text, response_meta = call_openrouter(config, prompt)
                raw_responses.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "domain": candidate.domain,
                        "candidate_file": str(candidate.candidate_file),
                        "attempt": attempt,
                        "prompt_sha256": _sha256_text(prompt),
                        "raw_response": response_text,
                        "metadata": response_meta,
                    }
                )
                try:
                    parsed = parse_model_json(response_text)
                    parsed_score = validate_prism_idea_quality_score_object(parsed, candidate=candidate)
                    break
                except Exception as exc:
                    errors = [str(exc)]
                    retry_feedback = errors
                    continue
            if parsed_score is not None:
                scores.append(parsed_score)
            else:
                parse_errors.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "domain": candidate.domain,
                        "candidate_file": str(candidate.candidate_file),
                        "error": "; ".join(errors),
                        "attempts": 2,
                    }
                )

    manifest = {
        "run_name": run_name,
        "scoring_mode": PRISM_IDEA_QUALITY_MODE,
        "candidate_file": str(candidate_file),
        "planned_candidate_count": len(candidates),
        "planned_pair_count": 0,
        "packets": [
            {
                "candidate_file": str(candidate_file),
                "domain": domain or sorted({candidate.domain for candidate in candidates}),
                "candidate_count": len(candidates),
                "pair_count": 0,
                "files": {"independent_candidates": str(candidate_file)},
                "blinding_key_present": False,
            }
        ],
        "blinding_key_read_during_scoring": False,
        "method_label_findings_in_prompts": prompt_label_findings,
        "no_weighted_composite": True,
        "pairwise_preferences_requested": False,
        "cap_validation_enforced": False,
    }
    metadata = {
        "run_name": run_name,
        "created_at": utc_now_iso(),
        "mode": "dry_run" if dry_run else ("mock_response" if mock_response else "live"),
        "scoring_mode": PRISM_IDEA_QUALITY_MODE,
        "config_path": str(config_path),
        "candidate_file": str(candidate_file),
        "output_dir": str(output_dir),
        "model": config["judge"].get("model"),
        "base_url": config["judge"].get("base_url"),
        "api_key_env": config["judge"].get("api_key_env"),
        "api_key_env_present": bool(os.environ.get(str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY")))),
        "network_used": (not dry_run and mock_response is None),
        "external_search_used": False,
        "weighted_composite_computed": False,
        "pairwise_enabled": False,
        "score_count": len(scores),
        "parse_error_count": len(parse_errors),
    }
    (output_dir / "judge_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "judge_config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output_dir / "scoring_inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ensure_prism_idea_quality_output_files(output_dir, scores, parse_errors, raw_responses)
    write_prism_idea_quality_audit(
        output_dir / "judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=parse_errors,
        raw_responses=raw_responses,
        unblind=False,
    )
    write_readme(output_dir / "README.md", metadata, manifest)
    return {"metadata": metadata, "manifest": manifest, "scores": scores, "parse_errors": parse_errors}


def run_pairwise_preference_scoring(
    *,
    config: dict[str, Any],
    config_path: Path,
    pairwise_packet_file: Path,
    output_dir: Path,
    run_name: str,
    dry_run: bool = False,
    mock_response: str | None = None,
    no_network: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if no_network and not dry_run and not mock_response:
        raise JudgeError("--no-network requires --dry-run or --mock-response")
    if not dry_run and not mock_response:
        api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
        if not os.environ.get(api_key_env):
            raise JudgeError(f"{api_key_env} is required for live scoring")
    output_dir.mkdir(parents=True, exist_ok=True)
    allowed_existing = {pairwise_packet_file.resolve()}
    existing = [path for path in output_dir.iterdir() if path.resolve() not in allowed_existing]
    if existing and not (resume or force):
        raise JudgeError(f"Output directory contains scoring outputs; use --resume or --force: {output_dir}")

    pairs = load_pairwise_preference_pairs(pairwise_packet_file)
    prompt_label_findings = []
    for pair in pairs:
        prompt = build_pairwise_preference_prompt(config, pair)
        labels = labels_found_in_prompt(prompt)
        if labels:
            prompt_label_findings.append({"pair_id": pair.pair_id, "labels": labels})

    raw_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    mock_text = load_mock_response(mock_response) if mock_response else None

    if not dry_run:
        for pair in pairs:
            prompt = build_pairwise_preference_prompt(config, pair)
            if mock_text is not None:
                response_text = mock_text
                response_meta = {"source": "mock_response"}
            else:
                response_text, response_meta = call_openrouter(config, prompt)
            raw_responses.append(
                {
                    "pair_id": pair.pair_id,
                    "domain": pair.domain,
                    "raw_response": response_text,
                    "metadata": response_meta,
                }
            )
            try:
                parsed = parse_model_json(response_text)
                scores.append(validate_pairwise_preference_object(parsed, pair=pair, config=config))
            except Exception as exc:
                parse_errors.append(
                    {
                        "pair_id": pair.pair_id,
                        "domain": pair.domain,
                        "error": str(exc),
                        "raw_response": response_text,
                    }
                )

    blinding_key_file = pairwise_packet_file.parent / "pairwise_blinding_key.json"
    manifest = {
        "run_name": run_name,
        "scoring_mode": "pairwise_preference",
        "pairwise_packet_file": str(pairwise_packet_file),
        "blinding_key_file": str(blinding_key_file),
        "planned_candidate_count": "not_applicable",
        "planned_pair_count": len(pairs),
        "packets": [
            {
                "pairwise_packet_file": str(pairwise_packet_file),
                "domain": sorted({pair.domain for pair in pairs}),
                "pair_count": len(pairs),
                "files": {"pairwise_pairs_blinded": str(pairwise_packet_file)},
                "blinding_key_present": blinding_key_file.exists(),
            }
        ],
        "blinding_key_read_during_scoring": False,
        "method_label_findings_in_prompts": prompt_label_findings,
        "no_weighted_composite": True,
        "pairwise_preferences_requested": True,
        "numeric_scores_requested": False,
    }
    metadata = {
        "run_name": run_name,
        "created_at": utc_now_iso(),
        "mode": "dry_run" if dry_run else ("mock_response" if mock_response else "live"),
        "scoring_mode": "pairwise_preference",
        "config_path": str(config_path),
        "pairwise_packet_file": str(pairwise_packet_file),
        "output_dir": str(output_dir),
        "model": config["judge"].get("model"),
        "base_url": config["judge"].get("base_url"),
        "api_key_env": config["judge"].get("api_key_env"),
        "api_key_env_present": bool(os.environ.get(str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY")))),
        "network_used": (not dry_run and mock_response is None),
        "external_search_used": False,
        "weighted_composite_computed": False,
        "pairwise_enabled": True,
        "numeric_scores_computed": False,
        "score_count": len(scores),
        "parse_error_count": len(parse_errors),
    }
    (output_dir / "judge_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "judge_config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output_dir / "scoring_inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_jsonl(output_dir / "raw_model_responses.jsonl", raw_responses)
    write_jsonl(output_dir / "pairwise_results_blinded.jsonl", scores)
    write_jsonl(output_dir / "parse_errors.jsonl", parse_errors)
    write_pairwise_preference_audit(
        output_dir / "judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=parse_errors,
        raw_responses=raw_responses,
        unblind=False,
    )
    write_readme(output_dir / "README.md", metadata, manifest)
    return {"metadata": metadata, "manifest": manifest, "scores": scores, "parse_errors": parse_errors}


def run_four_way_ranked_scoring(
    *,
    config: dict[str, Any],
    config_path: Path,
    packet_dir: Path,
    output_dir: Path,
    run_name: str,
    dry_run: bool = False,
    mock_response: str | None = None,
    no_network: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if no_network and not dry_run and not mock_response:
        raise JudgeError("--no-network requires --dry-run or --mock-response")
    if not dry_run and not mock_response:
        api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
        if not os.environ.get(api_key_env):
            raise JudgeError(f"{api_key_env} is required for live scoring")
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [path for path in output_dir.iterdir()]
    if existing and not (resume or force):
        raise JudgeError(f"Output directory contains scoring outputs; use --resume or --force: {output_dir}")
    packets = load_four_way_packets(packet_dir)
    prompt_label_findings = []
    for packet in packets:
        prompt = build_four_way_ranked_prompt(config, packet)
        labels = labels_found_in_prompt(prompt)
        if labels:
            prompt_label_findings.append({"domain": packet.domain, "labels": labels})
    if prompt_label_findings:
        raise JudgeError(f"Four-way ranked prompts contain forbidden method labels: {prompt_label_findings}")
    raw_responses: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    mock_text = load_mock_response(mock_response) if mock_response else None
    if not dry_run:
        for packet in packets:
            prompt = build_four_way_ranked_prompt(config, packet)
            if mock_text is not None:
                response_text = mock_text
                response_meta = {"source": "mock_response"}
            else:
                response_text, response_meta = call_openrouter(config, prompt)
            raw_responses.append({"domain": packet.domain, "packet_file": str(packet.packet_file), "raw_response": response_text, "metadata": response_meta})
            try:
                parsed = parse_model_json(response_text)
                scores.append(validate_four_way_ranked_object(parsed, packet=packet, config=config))
            except Exception as exc:
                parse_errors.append({"domain": packet.domain, "packet_file": str(packet.packet_file), "error": str(exc), "raw_response": response_text})
    manifest = {
        "run_name": run_name,
        "scoring_mode": "four_way_ranked",
        "packet_dir": str(packet_dir),
        "planned_candidate_count": 4 * len(packets),
        "planned_pair_count": 0,
        "planned_domain_count": len(packets),
        "packets": [{"domain": packet.domain, "packet_file": str(packet.packet_file), "candidate_count": len(packet.candidates)} for packet in packets],
        "blinding_key_read_during_scoring": False,
        "method_label_findings_in_prompts": prompt_label_findings,
        "no_weighted_composite": True,
        "pairwise_preferences_requested": False,
        "numeric_scores_requested": False,
    }
    metadata = {
        "run_name": run_name,
        "created_at": utc_now_iso(),
        "mode": "dry_run" if dry_run else ("mock_response" if mock_response else "live"),
        "scoring_mode": "four_way_ranked",
        "config_path": str(config_path),
        "packet_dir": str(packet_dir),
        "output_dir": str(output_dir),
        "model": config["judge"].get("model"),
        "base_url": config["judge"].get("base_url"),
        "api_key_env": config["judge"].get("api_key_env"),
        "api_key_env_present": bool(os.environ.get(str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY")))),
        "network_used": (not dry_run and mock_response is None),
        "external_search_used": False,
        "weighted_composite_computed": False,
        "pairwise_enabled": False,
        "numeric_scores_computed": False,
        "score_count": len(scores),
        "parse_error_count": len(parse_errors),
    }
    (output_dir / "judge_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "judge_config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output_dir / "scoring_inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_jsonl(output_dir / "raw_model_responses.jsonl", raw_responses)
    write_jsonl(output_dir / "four_way_results_blinded.jsonl", scores)
    write_jsonl(output_dir / "parse_errors.jsonl", parse_errors)
    write_four_way_audit(output_dir / "judge_quality_audit.md", metadata=metadata, manifest=manifest, scores=scores, parse_errors=parse_errors, raw_responses=raw_responses, unblind=False)
    write_readme(output_dir / "README.md", metadata, manifest)
    return {"metadata": metadata, "manifest": manifest, "scores": scores, "parse_errors": parse_errors}


def score_values_valid(scores: list[dict[str, Any]], config: dict[str, Any]) -> bool:
    try:
        for score in scores:
            if "scores" in score:
                dummy_candidate = IndependentCandidate(
                    candidate_id=str(score.get("candidate_id")),
                    domain=str(score.get("domain")),
                    candidate={"candidate_id": score.get("candidate_id")},
                    candidate_file=Path(str(score.get("candidate_file", "."))),
                )
                validate_independent_score_object(dict(score), candidate=dummy_candidate, config=config)
            else:
                dummy_pair = CandidatePair(
                    comparison_id=str(score.get("comparison_id")),
                    domain=str(score.get("domain")),
                    baseline=str(score.get("baseline")),
                    comparison_dir=Path(str(score.get("comparison_dir", "."))),
                    candidate_a={"candidate_id": score.get("candidate_a_id")},
                    candidate_b={"candidate_id": score.get("candidate_b_id")},
                )
                validate_score_object(dict(score), pair=dummy_pair, config=config)
        return True
    except Exception:
        return False


def write_audit(
    path: Path,
    *,
    config: dict[str, Any],
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw_responses: list[dict[str, Any]],
    unblind: bool,
) -> None:
    scoring_mode = metadata.get("scoring_mode") or manifest.get("scoring_mode") or "pairwise"
    independent_like = scoring_mode in {"independent", "independent_batch_calibrated"}
    if independent_like:
        blinded_inputs_exist = all(Path(entry["files"]["independent_candidates"]).exists() for entry in manifest.get("packets", []))
    else:
        blinded_inputs_exist = all(Path(entry["files"]["blinded_review_packet.md"]).exists() for entry in manifest.get("packets", []))
    pairwise_valid = score_values_valid(scores, config) if scores and scoring_mode == "pairwise" else "not_applicable"
    score_valid = score_values_valid(scores, config) if scores else "not_applicable"
    calibration_flag_count = sum(len(score.get("calibration_flags", [])) for score in scores)
    lines = [
        "# Judge Quality Audit",
        "",
        f"- scoring mode: {scoring_mode}",
        f"- config loaded: {bool(config)}",
        f"- API key env var present: {metadata.get('api_key_env_present')}",
        f"- model specified: {bool(config.get('judge', {}).get('model'))}",
        f"- base_url specified: {bool(config.get('judge', {}).get('base_url'))}",
        f"- blinded inputs exist: {blinded_inputs_exist}",
        f"- blinding key not read during scoring: {not manifest.get('blinding_key_read_during_scoring', False)}",
        f"- method labels absent from judge prompts: {not manifest.get('method_label_findings_in_prompts')}",
        f"- all score fields are 1-5 in mock/live scoring: {score_valid}",
        f"- pairwise preference valid: {pairwise_valid}",
        f"- confidence valid: {score_valid}",
        f"- raw responses saved in live/mock mode: {bool(raw_responses) if metadata.get('mode') != 'dry_run' else 'not_applicable'}",
        f"- parse errors count: {len(parse_errors)}",
        f"- calibration flags count: {calibration_flag_count}",
        "- no external search used by judge: True",
        f"- no weighted composite score computed: {not metadata.get('weighted_composite_computed', False)}",
        f"- pairwise preference requested: {manifest.get('pairwise_preferences_requested', scoring_mode == 'pairwise')}",
        f"- unblinding performed in this mode: {unblind}",
        f"- unblinding only performed in postprocess mode: {bool(unblind) or metadata.get('mode') != 'postprocess_unblind'}",
        "",
        "## Packet Counts",
        "",
        f"- comparison dirs: {manifest.get('comparison_dir_count', 0)}",
        f"- planned candidates: {manifest.get('planned_candidate_count', 'not_applicable')}",
        f"- planned pairs: {manifest.get('planned_pair_count', 0)}",
        f"- incomplete pairs: {len(manifest.get('incomplete_pairs', []))}",
        f"- scores written: {len(scores)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_pairwise_preference_audit(
    path: Path,
    *,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw_responses: list[dict[str, Any]],
    unblind: bool,
) -> None:
    winners_valid = all(row.get("winner") in PAIRWISE_WINNERS for row in scores)
    criterion_valid = all(
        isinstance(row.get("criterion_winners"), dict)
        and sorted(row.get("criterion_winners", {}).keys()) == sorted(PAIRWISE_PREFERENCE_CRITERIA)
        and all(value in PAIRWISE_CRITERION_WINNERS for value in row.get("criterion_winners", {}).values())
        for row in scores
    )
    confidence_valid = all(row.get("confidence") in {"LOW", "MEDIUM", "HIGH"} for row in scores)
    lines = [
        "# Pairwise Preference Judge Quality Audit",
        "",
        f"- scoring mode: {metadata.get('scoring_mode')}",
        f"- API key env var present: {metadata.get('api_key_env_present')}",
        f"- model specified: {bool(metadata.get('model'))}",
        f"- base_url specified: {bool(metadata.get('base_url'))}",
        f"- blinded pair packet exists: {Path(str(manifest.get('pairwise_packet_file'))).exists() if manifest.get('pairwise_packet_file') else False}",
        f"- blinding key not read during scoring: {not manifest.get('blinding_key_read_during_scoring', False)}",
        f"- method labels absent from judge prompts: {not manifest.get('method_label_findings_in_prompts')}",
        f"- numeric scores requested: {manifest.get('numeric_scores_requested', False)}",
        f"- winner values valid: {winners_valid}",
        f"- criterion winner values valid: {criterion_valid}",
        f"- confidence valid: {confidence_valid}",
        f"- raw responses saved in live/mock mode: {bool(raw_responses) if metadata.get('mode') != 'dry_run' else 'not_applicable'}",
        f"- parse errors count: {len(parse_errors)}",
        "- no external search used by judge: True",
        f"- no weighted composite score computed: {not metadata.get('weighted_composite_computed', False)}",
        f"- pairwise preference requested: {manifest.get('pairwise_preferences_requested', True)}",
        f"- unblinding performed in this mode: {unblind}",
        f"- unblinding only performed in postprocess mode: {bool(unblind) or metadata.get('mode') != 'postprocess_unblind'}",
        "",
        "## Packet Counts",
        "",
        f"- planned pairs: {manifest.get('planned_pair_count', 0)}",
        f"- scores written: {len(scores)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_four_way_audit(
    path: Path,
    *,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw_responses: list[dict[str, Any]],
    unblind: bool,
) -> None:
    rankings_valid = True
    for row in scores:
        rankings = row.get("criterion_rankings", {})
        if sorted(rankings.keys()) != sorted(FOUR_WAY_RANK_CRITERIA):
            rankings_valid = False
            break
        ids = set(str(cid) for cid in row.get("candidate_ids", []))
        for criterion_rows in rankings.values():
            if len(criterion_rows) != 4 or {str(item.get("candidate_id")) for item in criterion_rows} != ids:
                rankings_valid = False
                break
            if any(not isinstance(item.get("rank"), int) or not 1 <= item.get("rank") <= 4 for item in criterion_rows):
                rankings_valid = False
                break
    confidence_valid = all(row.get("confidence") in {"LOW", "MEDIUM", "HIGH"} for row in scores)
    lines = [
        "# Four-Way Ranked Judge Quality Audit",
        "",
        f"- scoring mode: {metadata.get('scoring_mode')}",
        f"- API key env var present: {metadata.get('api_key_env_present')}",
        f"- model specified: {bool(metadata.get('model'))}",
        f"- base_url specified: {bool(metadata.get('base_url'))}",
        f"- blinded packet inputs exist: {Path(str(manifest.get('packet_dir'))).exists() if manifest.get('packet_dir') else False}",
        f"- blinding key not read during scoring: {not manifest.get('blinding_key_read_during_scoring', False)}",
        f"- method labels absent from judge prompts: {not manifest.get('method_label_findings_in_prompts')}",
        f"- numeric scores requested: {manifest.get('numeric_scores_requested', False)}",
        f"- rankings valid: {rankings_valid}",
        f"- confidence valid: {confidence_valid}",
        f"- raw responses saved in live/mock mode: {bool(raw_responses) if metadata.get('mode') != 'dry_run' else 'not_applicable'}",
        f"- parse errors count: {len(parse_errors)}",
        "- no external search used by judge: True",
        f"- no weighted composite score computed: {not metadata.get('weighted_composite_computed', False)}",
        f"- pairwise preference requested: {manifest.get('pairwise_preferences_requested', False)}",
        f"- unblinding performed in this mode: {unblind}",
        f"- unblinding only performed in postprocess mode: {bool(unblind) or metadata.get('mode') != 'postprocess_unblind'}",
        "",
        "## Packet Counts",
        "",
        f"- planned domains: {manifest.get('planned_domain_count', 0)}",
        f"- planned candidates: {manifest.get('planned_candidate_count', 0)}",
        f"- results written: {len(scores)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def role_based_score_values_valid(scores: list[dict[str, Any]], config: dict[str, Any]) -> bool:
    try:
        expected_roles = {str(role["id"]) for role in role_definitions(config)}
        for row in scores:
            role_scores = row.get("role_scores")
            if not isinstance(role_scores, dict):
                return False
            if set(role_scores) - expected_roles:
                return False
            for role_id, role_record in role_scores.items():
                for key in role_score_ids(config, role_id):
                    value = role_record.get(key)
                    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10:
                        return False
                if not isinstance(role_record.get("weaknesses"), list) or not role_record.get("weaknesses"):
                    return False
        return True
    except Exception:
        return False


def write_role_based_audit(
    path: Path,
    *,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    scores: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    raw_responses: list[dict[str, Any]],
    unblind: bool,
) -> None:
    cap_violation_count = sum(len(row.get("cap_violations", [])) for row in scores)
    invalid_role_count = sum(len(row.get("invalid_roles", [])) for row in scores)
    score_valid = role_based_score_values_valid(scores, {"roles": manifest.get("roles", [])}) if scores else "not_applicable"
    roles = [str(role.get("id")) for role in manifest.get("roles", []) if isinstance(role, dict)]
    lines = [
        "# Role-Based Judge Quality Audit",
        "",
        f"- scoring mode: {metadata.get('scoring_mode')}",
        f"- API key env var present: {metadata.get('api_key_env_present')}",
        f"- model: `{metadata.get('model')}`",
        f"- base_url specified: {bool(metadata.get('base_url'))}",
        f"- roles: {', '.join(roles)}",
        f"- blinded candidate input exists: {Path(str(manifest.get('candidate_file'))).exists() if manifest.get('candidate_file') else False}",
        f"- blinding key not read during scoring: {not manifest.get('blinding_key_read_during_scoring', False)}",
        f"- method labels absent from judge prompts: {not manifest.get('method_label_findings_in_prompts')}",
        f"- score fields are valid 0-10 integers: {score_valid}",
        f"- role weaknesses present: {score_valid}",
        f"- cap validation enforced: {manifest.get('cap_validation_enforced')}",
        f"- retry on cap violation: {manifest.get('retry_on_cap_violation')}",
        f"- max cap violation retries: {manifest.get('max_cap_violation_retries')}",
        f"- cap violations count: {cap_violation_count}",
        f"- invalid role count: {invalid_role_count}",
        f"- raw responses saved in live/mock mode: {bool(raw_responses) if metadata.get('mode') != 'dry_run' else 'not_applicable'}",
        f"- parse errors count: {len(parse_errors)}",
        "- no external search used by judge: True",
        f"- no weighted composite score computed: {not metadata.get('weighted_composite_computed', False)}",
        f"- pairwise preference requested: {manifest.get('pairwise_preferences_requested', False)}",
        f"- unblinding performed in this mode: {unblind}",
        "",
        "## Packet Counts",
        "",
        f"- planned candidates: {manifest.get('planned_candidate_count', 0)}",
        f"- planned role responses: {manifest.get('planned_role_count', 0)}",
        f"- planned pairs: {manifest.get('planned_pair_count', 0)}",
        f"- candidate score records written: {len(scores)}",
        f"- raw role responses written: {len(raw_responses)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme(path: Path, metadata: dict[str, Any], manifest: dict[str, Any]) -> None:
    scoring_mode = metadata.get("scoring_mode") or manifest.get("scoring_mode") or "pairwise"
    text = f"""# SGHA OpenRouter LLM Judge Run

Run name: `{metadata['run_name']}`

Mode: `{metadata['mode']}`

Scoring mode: `{scoring_mode}`

This directory contains blinded LLM-judge inputs and outputs. Dry-run mode performs
packet validation only. Mock-response mode validates parsing and output writing
without network calls. Live mode is available for later use with OpenRouter.

No weighted composite score is computed. Novelty scores mean novelty potential
from the provided text only, not proven external novelty.

Blinding keys are not read during scoring. Run postprocess-unblind only after
scoring is complete.

Planned candidates: {manifest.get('planned_candidate_count', 'not_applicable')}
Planned pairs: {manifest.get('planned_pair_count', 0)}
"""
    path.write_text(text, encoding="utf-8")


def load_scores(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise JudgeError(f"scores_blinded.jsonl not found: {path}")
    return read_jsonl(path)


def load_blinding_key(comparison_dir: Path) -> dict[str, dict[str, Any]]:
    path = comparison_dir / BLINDING_KEY_FILE
    if not path.exists():
        raise JudgeError(f"Missing blinding key for postprocess: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise JudgeError(f"Blinding key must be a list: {path}")
    mapping = {}
    for row in data:
        if isinstance(row, dict) and row.get("blinded_candidate_id"):
            mapping[str(row["blinded_candidate_id"])] = row
    return mapping


def load_independent_blinding_key(output_dir: Path) -> dict[str, dict[str, Any]]:
    candidates = sorted(output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))
    if not candidates:
        raise JudgeError(f"Missing independent blinding key in {output_dir}")
    if len(candidates) > 1:
        preferred = [path for path in candidates if path.name == "bandits_blinding_key.json"]
        if len(preferred) == 1:
            path = preferred[0]
        else:
            raise JudgeError(f"Multiple independent blinding keys found: {candidates}")
    else:
        path = candidates[0]
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise JudgeError(f"Blinding key must be a list: {path}")
    mapping = {}
    for row in data:
        if isinstance(row, dict) and row.get("blinded_candidate_id"):
            mapping[str(row["blinded_candidate_id"])] = row
    return mapping


def load_pairwise_preference_blinding_key(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise JudgeError(f"Missing pairwise blinding key: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise JudgeError(f"Pairwise blinding key must be a list: {path}")
    mapping = {}
    for row in data:
        if isinstance(row, dict) and row.get("pair_id"):
            mapping[str(row["pair_id"])] = row
    return mapping


def load_four_way_blinding_keys(packet_dir: Path) -> dict[str, dict[str, dict[str, Any]]]:
    mapping: dict[str, dict[str, dict[str, Any]]] = {}
    for path in sorted(packet_dir.glob("*_4way_blinding_key.json")):
        domain = path.name.removesuffix("_4way_blinding_key.json")
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise JudgeError(f"Four-way blinding key must be a list: {path}")
        domain_map = {}
        for row in rows:
            if isinstance(row, dict) and row.get("blinded_candidate_id"):
                domain_map[str(row["blinded_candidate_id"])] = row
        mapping[domain] = domain_map
    return mapping


def reparse_pairwise_preference_raw_responses(
    *,
    config: dict[str, Any],
    output_dir: Path,
    metadata: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_path = output_dir / "raw_model_responses.jsonl"
    if not raw_path.exists():
        return [], []
    pair_file = Path(str(metadata.get("pairwise_packet_file") or manifest.get("pairwise_packet_file")))
    pair_by_id = {pair.pair_id: pair for pair in load_pairwise_preference_pairs(pair_file)}
    scores: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    for raw in read_jsonl(raw_path):
        pair_id = str(raw.get("pair_id"))
        pair = pair_by_id.get(pair_id)
        if pair is None:
            parse_errors.append({"pair_id": pair_id, "error": "Unknown pair_id in raw response", "raw_response": raw.get("raw_response")})
            continue
        try:
            parsed = parse_model_json(str(raw.get("raw_response", "")))
            scores.append(validate_pairwise_preference_object(parsed, pair=pair, config=config))
        except Exception as exc:
            parse_errors.append(
                {
                    "pair_id": pair_id,
                    "domain": raw.get("domain"),
                    "error": str(exc),
                    "raw_response": raw.get("raw_response"),
                }
            )
    write_jsonl(output_dir / "pairwise_results_blinded.jsonl", scores)
    write_jsonl(output_dir / "parse_errors.jsonl", parse_errors)
    metadata["score_count"] = len(scores)
    metadata["parse_error_count"] = len(parse_errors)
    return scores, parse_errors


def postprocess_unblind(*, config: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    metadata_path = output_dir / "judge_run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    manifest_path = output_dir / "scoring_inputs_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    scoring_mode = metadata.get("scoring_mode") or manifest.get("scoring_mode") or config.get("evaluation", {}).get("scoring_mode", "pairwise")
    if scoring_mode == "pairwise_preference":
        scores = read_jsonl(output_dir / "pairwise_results_blinded.jsonl") if (output_dir / "pairwise_results_blinded.jsonl").exists() else []
        if not scores and (output_dir / "raw_model_responses.jsonl").exists():
            scores, _ = reparse_pairwise_preference_raw_responses(
                config=config,
                output_dir=output_dir,
                metadata=metadata,
                manifest=manifest,
            )
        return postprocess_unblind_pairwise_preference(config=config, output_dir=output_dir, scores=scores, metadata=metadata, manifest=manifest)
    if scoring_mode == "four_way_ranked":
        scores = read_jsonl(output_dir / "four_way_results_blinded.jsonl")
        return postprocess_unblind_four_way_ranked(config=config, output_dir=output_dir, scores=scores, metadata=metadata, manifest=manifest)
    if scoring_mode == FORMULATION_QUALITY_MODE:
        key_candidates = sorted(output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))
        if not key_candidates:
            raise JudgeError(f"Missing formulation-quality blinding key in {output_dir}; use --postprocess-formulation-quality with --blinding-key-file")
        if len(key_candidates) > 1:
            raise JudgeError(f"Multiple formulation-quality blinding keys found: {key_candidates}")
        return postprocess_unblind_formulation_quality(
            scoring_dir=output_dir,
            postprocess_dir=output_dir,
            blinding_key_file=key_candidates[0],
            blank_scoring_sheet=None,
        )
    if scoring_mode == FORMULATION_ONLY_MODE:
        key_candidates = sorted(output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))
        if not key_candidates:
            raise JudgeError(f"Missing formulation-only blinding key in {output_dir}; use --postprocess-formulation-only with --blinding-key-file")
        if len(key_candidates) > 1:
            raise JudgeError(f"Multiple formulation-only blinding keys found: {key_candidates}")
        return postprocess_unblind_formulation_only(
            scoring_dir=output_dir,
            postprocess_dir=output_dir,
            blinding_key_file=key_candidates[0],
        )
    if scoring_mode == PERSONALIZED_FORMULATION_MODE:
        key_candidates = sorted(output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))
        if not key_candidates:
            raise JudgeError(f"Missing personalized formulation blinding key in {output_dir}; use --postprocess-personalized-formulation with --blinding-key-file")
        if len(key_candidates) > 1:
            raise JudgeError(f"Multiple personalized formulation blinding keys found: {key_candidates}")
        return postprocess_unblind_personalized_formulation(
            scoring_dir=output_dir,
            postprocess_dir=output_dir,
            blinding_key_file=key_candidates[0],
        )
    if scoring_mode == PRISM_IDEA_QUALITY_MODE:
        key_candidates = sorted(output_dir.glob(INDEPENDENT_BLINDING_KEY_GLOB))
        if not key_candidates:
            raise JudgeError(f"Missing PRISM idea-quality blinding key in {output_dir}; use --postprocess-prism-idea-quality with --blinding-key-file")
        if len(key_candidates) > 1:
            raise JudgeError(f"Multiple PRISM idea-quality blinding keys found: {key_candidates}")
        return postprocess_unblind_prism_idea_quality(
            scoring_dir=output_dir,
            postprocess_dir=output_dir,
            blinding_key_file=key_candidates[0],
        )
    scores = load_scores(output_dir / "scores_blinded.jsonl")
    if scoring_mode == ROLE_BASED_MODE:
        return postprocess_unblind_role_based(config=config, output_dir=output_dir, scores=scores, metadata=metadata, manifest=manifest)
    if scoring_mode in {"independent", "independent_batch_calibrated"}:
        return postprocess_unblind_independent(config=config, output_dir=output_dir, scores=scores, metadata=metadata, manifest=manifest)

    unblinded = []
    key_cache: dict[str, dict[str, dict[str, Any]]] = {}
    for score in scores:
        comp_dir = Path(str(score.get("comparison_dir")))
        if str(comp_dir) not in key_cache:
            key_cache[str(comp_dir)] = load_blinding_key(comp_dir)
        key = key_cache[str(comp_dir)]
        a_key = key.get(str(score.get("candidate_a_id")), {})
        b_key = key.get(str(score.get("candidate_b_id")), {})
        row = dict(score)
        row["candidate_a_method"] = a_key.get("method", "UNKNOWN")
        row["candidate_a_original_id"] = a_key.get("candidate_id", "UNKNOWN")
        row["candidate_b_method"] = b_key.get("method", "UNKNOWN")
        row["candidate_b_original_id"] = b_key.get("candidate_id", "UNKNOWN")
        unblinded.append(row)
    write_jsonl(output_dir / "scores_unblinded.jsonl", unblinded)
    write_unblinded_scores_csv(output_dir / "scores_unblinded.csv", unblinded, config)
    write_group_averages(output_dir / "scores_by_method.csv", unblinded, config, group_key="method")
    write_group_averages(output_dir / "scores_by_domain.csv", unblinded, config, group_key="domain")
    write_pairwise_preferences(output_dir / "pairwise_preferences.csv", unblinded)
    (output_dir / "judge_summary.md").write_text(
        "# Judge Summary\n\n"
        "Postprocess unblinding complete. Per-criterion means are reported separately; "
        "no weighted composite score is computed.\n",
        encoding="utf-8",
    )
    metadata["postprocess_unblind_completed_at"] = utc_now_iso()
    metadata["weighted_composite_computed"] = False
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest["blinding_key_read_during_postprocess"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_audit(
        output_dir / "judge_quality_audit.md",
        config=config,
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=read_jsonl(output_dir / "parse_errors.jsonl") if (output_dir / "parse_errors.jsonl").exists() else [],
        raw_responses=read_jsonl(output_dir / "raw_model_responses.jsonl") if (output_dir / "raw_model_responses.jsonl").exists() else [],
        unblind=True,
    )
    return {"scores_unblinded": unblinded}


def postprocess_unblind_role_based(
    *,
    config: dict[str, Any],
    output_dir: Path,
    scores: list[dict[str, Any]],
    metadata: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    key = load_independent_blinding_key(output_dir)
    unblinded = []
    for score in scores:
        key_row = key.get(str(score.get("candidate_id")), {})
        row = dict(score)
        row["method"] = key_row.get("method_hidden_label") or key_row.get("method") or "UNKNOWN"
        row["original_candidate_id"] = key_row.get("candidate_id") or key_row.get("original_candidate_id") or "UNKNOWN"
        row["title"] = key_row.get("title") or "UNKNOWN"
        unblinded.append(row)
    write_jsonl(output_dir / "scores_unblinded.jsonl", unblinded)
    write_role_based_unblinded_scores_csv(output_dir / "scores_unblinded.csv", unblinded, config)
    write_role_based_group_averages(output_dir / "scores_by_method.csv", unblinded, config, group_key="method")
    write_role_based_group_averages(output_dir / "scores_by_criterion.csv", unblinded, config, group_key="criterion")
    write_role_based_scores_by_candidate(output_dir / "scores_by_candidate.csv", unblinded, config)
    write_role_based_summary(output_dir / "judge_summary.md", unblinded, config)

    metadata_path = output_dir / "judge_run_metadata.json"
    metadata["postprocess_unblind_completed_at"] = utc_now_iso()
    metadata["weighted_composite_computed"] = False
    metadata["pairwise_enabled"] = False
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest_path = output_dir / "scoring_inputs_manifest.json"
    manifest["blinding_key_read_during_postprocess"] = True
    manifest["pairwise_preferences_written"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_role_based_audit(
        output_dir / "judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=read_jsonl(output_dir / "parse_errors.jsonl") if (output_dir / "parse_errors.jsonl").exists() else [],
        raw_responses=read_jsonl(output_dir / "raw_model_responses.jsonl") if (output_dir / "raw_model_responses.jsonl").exists() else [],
        unblind=True,
    )
    return {"scores_unblinded": unblinded}


def postprocess_unblind_independent(
    *,
    config: dict[str, Any],
    output_dir: Path,
    scores: list[dict[str, Any]],
    metadata: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    key = load_independent_blinding_key(output_dir)
    unblinded = []
    for score in scores:
        key_row = key.get(str(score.get("candidate_id")), {})
        row = dict(score)
        row["method"] = key_row.get("method_hidden_label") or key_row.get("method") or "UNKNOWN"
        row["original_candidate_id"] = key_row.get("candidate_id") or key_row.get("original_candidate_id") or "UNKNOWN"
        row["title"] = key_row.get("title") or "UNKNOWN"
        unblinded.append(row)
    write_jsonl(output_dir / "scores_unblinded.jsonl", unblinded)
    write_independent_unblinded_scores_csv(output_dir / "scores_unblinded.csv", unblinded, config)
    write_independent_group_averages(output_dir / "scores_by_method.csv", unblinded, config, group_key="method")
    write_independent_group_averages(output_dir / "scores_by_criterion.csv", unblinded, config, group_key="criterion")
    write_scores_by_candidate(output_dir / "scores_by_candidate.csv", unblinded, config)
    write_independent_summary(output_dir / "judge_summary.md", unblinded, config)

    metadata_path = output_dir / "judge_run_metadata.json"
    metadata["postprocess_unblind_completed_at"] = utc_now_iso()
    metadata["weighted_composite_computed"] = False
    metadata["pairwise_enabled"] = False
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest_path = output_dir / "scoring_inputs_manifest.json"
    manifest["blinding_key_read_during_postprocess"] = True
    manifest["pairwise_preferences_written"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_audit(
        output_dir / "judge_quality_audit.md",
        config=config,
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=read_jsonl(output_dir / "parse_errors.jsonl") if (output_dir / "parse_errors.jsonl").exists() else [],
        raw_responses=read_jsonl(output_dir / "raw_model_responses.jsonl") if (output_dir / "raw_model_responses.jsonl").exists() else [],
        unblind=True,
    )
    return {"scores_unblinded": unblinded}


def load_formulation_quality_blinding_key(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise JudgeError(f"Missing formulation-quality blinding key: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise JudgeError(f"Blinding key must be a list: {path}")
    mapping: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("blinded_candidate_id"):
            mapping[str(row["blinded_candidate_id"])] = row
    return mapping


def _mean(values: list[float]) -> float | str:
    return round(sum(values) / len(values), 4) if values else ""


def _stddev(values: list[float]) -> float | str:
    if len(values) < 2:
        return ""
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return round(variance ** 0.5, 4)


def _stderr(values: list[float]) -> float | str:
    if len(values) < 2:
        return ""
    std = _stddev(values)
    return round(float(std) / (len(values) ** 0.5), 4) if std != "" else ""


def write_formulation_quality_group_scores(path: Path, rows: list[dict[str, Any]], group_keys: list[str]) -> None:
    fieldnames = group_keys + ["n"]
    for key in FORMULATION_QUALITY_CRITERIA:
        fieldnames.extend([f"mean_{key}", f"std_{key}", f"se_{key}"])
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(tuple(str(row.get(key, "UNKNOWN")) for key in group_keys), []).append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group, group_rows in sorted(grouped.items()):
            out = {key: group[index] for index, key in enumerate(group_keys)}
            out["n"] = len(group_rows)
            for criterion in FORMULATION_QUALITY_CRITERIA:
                vals = [float(row.get("scores", {}).get(criterion)) for row in group_rows if isinstance(row.get("scores", {}).get(criterion), int)]
                out[f"mean_{criterion}"] = _mean(vals)
                out[f"std_{criterion}"] = _stddev(vals)
                out[f"se_{criterion}"] = _stderr(vals)
            writer.writerow(out)


def write_formulation_quality_action_counts(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["method", "n"] + sorted(FORMULATION_QUALITY_ACTIONS)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("method", "UNKNOWN")), []).append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for method, method_rows in sorted(grouped.items()):
            counts = collections.Counter(str(row.get("recommended_action")) for row in method_rows)
            out = {"method": method, "n": len(method_rows)}
            for action in sorted(FORMULATION_QUALITY_ACTIONS):
                out[action] = counts.get(action, 0)
            writer.writerow(out)


def write_formulation_quality_filled_sheet(path: Path, rows: list[dict[str, Any]], blank_sheet: Path | None) -> None:
    if blank_sheet and blank_sheet.exists():
        with blank_sheet.open(encoding="utf-8") as handle:
            blank_rows = list(csv.DictReader(handle))
        fieldnames = list(blank_rows[0].keys()) if blank_rows else []
    else:
        blank_rows = []
        fieldnames = ["domain", "method", "candidate_id", "title"] + [f"{key}_0_to_10" for key in [c.removesuffix("_0_to_10") for c in FORMULATION_QUALITY_CRITERIA]] + ["comments", "recommended_action"]
    if not fieldnames:
        fieldnames = ["domain", "method", "candidate_id", "title"] + list(FORMULATION_QUALITY_CRITERIA) + ["comments", "recommended_action"]
    score_by_key = {
        (str(row.get("domain")), str(row.get("method")), str(row.get("original_candidate_id"))): row
        for row in rows
    }
    if not blank_rows:
        blank_rows = [
            {
                "domain": row.get("domain"),
                "method": row.get("method"),
                "candidate_id": row.get("original_candidate_id"),
                "title": row.get("title"),
                "comments": "",
                "recommended_action": "",
            }
            for row in rows
        ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for blank in blank_rows:
            row = dict(blank)
            score_row = score_by_key.get((str(blank.get("domain")), str(blank.get("method")), str(blank.get("candidate_id"))))
            if score_row is not None:
                for criterion in FORMULATION_QUALITY_CRITERIA:
                    sheet_key = criterion
                    if sheet_key not in row and criterion.endswith("_0_to_10"):
                        sheet_key = criterion
                    if sheet_key in fieldnames:
                        row[sheet_key] = score_row.get("scores", {}).get(criterion)
                if "recommended_action" in fieldnames:
                    row["recommended_action"] = score_row.get("recommended_action")
                if "comments" in fieldnames:
                    row["comments"] = score_row.get("rationale")
            writer.writerow(row)


def postprocess_unblind_formulation_quality(
    *,
    scoring_dir: Path,
    postprocess_dir: Path,
    blinding_key_file: Path,
    blank_scoring_sheet: Path | None = None,
) -> dict[str, Any]:
    postprocess_dir.mkdir(parents=True, exist_ok=True)
    scores = read_jsonl(scoring_dir / "formulation_quality_scores_blinded.jsonl")
    key = load_formulation_quality_blinding_key(blinding_key_file)
    unblinded: list[dict[str, Any]] = []
    for score in scores:
        key_row = key.get(str(score.get("candidate_id")), {})
        row = dict(score)
        row["method"] = key_row.get("method_hidden_label") or key_row.get("method") or "UNKNOWN"
        row["original_candidate_id"] = key_row.get("candidate_id") or key_row.get("original_candidate_id") or "UNKNOWN"
        row["title"] = key_row.get("title") or "UNKNOWN"
        unblinded.append(row)

    write_jsonl(postprocess_dir / "formulation_quality_scores_unblinded.jsonl", unblinded)
    write_formulation_quality_scores_csv(postprocess_dir / "formulation_quality_scores_unblinded.csv", unblinded, unblinded=True)
    write_formulation_quality_group_scores(postprocess_dir / "formulation_quality_scores_by_method.csv", unblinded, ["method"])
    write_formulation_quality_group_scores(postprocess_dir / "formulation_quality_scores_by_domain.csv", unblinded, ["domain"])
    write_formulation_quality_group_scores(postprocess_dir / "formulation_quality_scores_by_domain_method.csv", unblinded, ["domain", "method"])
    write_formulation_quality_action_counts(postprocess_dir / "recommended_actions_by_method.csv", unblinded)
    write_formulation_quality_filled_sheet(postprocess_dir / "formulation_quality_scoring_sheet_filled.csv", unblinded, blank_scoring_sheet)

    metadata_path = scoring_dir / "judge_run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    metadata["postprocess_unblind_completed_at"] = utc_now_iso()
    metadata["weighted_composite_computed"] = False
    metadata["pairwise_enabled"] = False
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest_path = scoring_dir / "scoring_inputs_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest["blinding_key_read_during_postprocess"] = True
    manifest["blinding_key_read_during_scoring"] = False
    manifest["pairwise_preferences_written"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_formulation_quality_audit(
        scoring_dir / "formulation_quality_judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=read_jsonl(scoring_dir / "parse_errors.jsonl") if (scoring_dir / "parse_errors.jsonl").exists() else [],
        raw_responses=read_jsonl(scoring_dir / "raw_model_responses.jsonl") if (scoring_dir / "raw_model_responses.jsonl").exists() else [],
        unblind=True,
    )
    return {"scores_unblinded": unblinded}


def write_formulation_only_group_scores(path: Path, rows: list[dict[str, Any]], group_keys: list[str]) -> None:
    fieldnames = group_keys + ["n"]
    for key in FORMULATION_ONLY_CRITERIA:
        fieldnames.extend([f"mean_{key}", f"std_{key}", f"se_{key}"])
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(tuple(str(row.get(key, "UNKNOWN")) for key in group_keys), []).append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group, group_rows in sorted(grouped.items()):
            out = {key: group[index] for index, key in enumerate(group_keys)}
            out["n"] = len(group_rows)
            for criterion in FORMULATION_ONLY_CRITERIA:
                vals = [float(row.get("scores", {}).get(criterion)) for row in group_rows if isinstance(row.get("scores", {}).get(criterion), int)]
                out[f"mean_{criterion}"] = _mean(vals)
                out[f"std_{criterion}"] = _stddev(vals)
                out[f"se_{criterion}"] = _stderr(vals)
            writer.writerow(out)


def write_personalized_formulation_group_scores(path: Path, rows: list[dict[str, Any]], group_keys: list[str]) -> None:
    fieldnames = group_keys + ["n"]
    for key in PERSONALIZED_FORMULATION_CRITERIA:
        fieldnames.extend([f"mean_{key}", f"std_{key}", f"se_{key}"])
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(tuple(str(row.get(key, "UNKNOWN")) for key in group_keys), []).append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group, group_rows in sorted(grouped.items()):
            out = {key: group[index] for index, key in enumerate(group_keys)}
            out["n"] = len(group_rows)
            for criterion in PERSONALIZED_FORMULATION_CRITERIA:
                vals = [float(row.get("scores", {}).get(criterion)) for row in group_rows if isinstance(row.get("scores", {}).get(criterion), int)]
                out[f"mean_{criterion}"] = _mean(vals)
                out[f"std_{criterion}"] = _stddev(vals)
                out[f"se_{criterion}"] = _stderr(vals)
            writer.writerow(out)


def write_formulation_only_action_counts(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["method", "n"] + sorted(FORMULATION_QUALITY_ACTIONS)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("method", "UNKNOWN")), []).append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for method, method_rows in sorted(grouped.items()):
            counts = collections.Counter(str(row.get("recommended_action")) for row in method_rows)
            out = {"method": method, "n": len(method_rows)}
            for action in sorted(FORMULATION_QUALITY_ACTIONS):
                out[action] = counts.get(action, 0)
            writer.writerow(out)


def write_personalized_formulation_action_counts(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["candidate_id", "profile", "n"] + sorted(FORMULATION_QUALITY_ACTIONS)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((str(row.get("original_candidate_id") or row.get("candidate_id")), str(row.get("profile", "UNKNOWN"))), []).append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for (candidate_id, profile), group_rows in sorted(grouped.items()):
            counts = collections.Counter(str(row.get("recommended_action")) for row in group_rows)
            out = {"candidate_id": candidate_id, "profile": profile, "n": len(group_rows)}
            for action in sorted(FORMULATION_QUALITY_ACTIONS):
                out[action] = counts.get(action, 0)
            writer.writerow(out)


def postprocess_unblind_formulation_only(
    *,
    scoring_dir: Path,
    postprocess_dir: Path,
    blinding_key_file: Path,
) -> dict[str, Any]:
    postprocess_dir.mkdir(parents=True, exist_ok=True)
    scores = read_jsonl(scoring_dir / "formulation_only_scores_blinded.jsonl")
    key = load_formulation_quality_blinding_key(blinding_key_file)
    unblinded: list[dict[str, Any]] = []
    for score in scores:
        key_row = key.get(str(score.get("candidate_id")), {})
        row = dict(score)
        row["method"] = key_row.get("method_hidden_label") or key_row.get("method") or "UNKNOWN"
        row["original_candidate_id"] = key_row.get("candidate_id") or key_row.get("original_candidate_id") or "UNKNOWN"
        row["title"] = key_row.get("title") or "UNKNOWN"
        unblinded.append(row)

    write_jsonl(postprocess_dir / "formulation_only_scores_unblinded.jsonl", unblinded)
    write_formulation_only_scores_csv(postprocess_dir / "formulation_only_scores_unblinded.csv", unblinded, unblinded=True)
    write_formulation_only_group_scores(postprocess_dir / "formulation_only_scores_by_method.csv", unblinded, ["method"])
    write_formulation_only_group_scores(postprocess_dir / "formulation_only_scores_by_domain.csv", unblinded, ["domain"])
    write_formulation_only_group_scores(postprocess_dir / "formulation_only_scores_by_domain_method.csv", unblinded, ["domain", "method"])
    write_formulation_only_action_counts(postprocess_dir / "recommended_actions_by_method.csv", unblinded)

    metadata_path = scoring_dir / "judge_run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    metadata["postprocess_unblind_completed_at"] = utc_now_iso()
    metadata["weighted_composite_computed"] = False
    metadata["pairwise_enabled"] = False
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest_path = scoring_dir / "scoring_inputs_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest["blinding_key_read_during_postprocess"] = True
    manifest["blinding_key_read_during_scoring"] = False
    manifest["pairwise_preferences_written"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_formulation_only_audit(
        scoring_dir / "formulation_only_judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=read_jsonl(scoring_dir / "parse_errors.jsonl") if (scoring_dir / "parse_errors.jsonl").exists() else [],
        raw_responses=read_jsonl(scoring_dir / "raw_model_responses.jsonl") if (scoring_dir / "raw_model_responses.jsonl").exists() else [],
        unblind=True,
    )
    return {"scores_unblinded": unblinded}


def postprocess_unblind_personalized_formulation(
    *,
    scoring_dir: Path,
    postprocess_dir: Path,
    blinding_key_file: Path,
) -> dict[str, Any]:
    postprocess_dir.mkdir(parents=True, exist_ok=True)
    scores = read_jsonl(scoring_dir / "personalized_scores_blinded.jsonl")
    key = load_formulation_quality_blinding_key(blinding_key_file)
    unblinded: list[dict[str, Any]] = []
    for score in scores:
        key_row = key.get(str(score.get("candidate_id")), {})
        row = dict(score)
        row["method"] = key_row.get("method_hidden_label") or key_row.get("method") or "UNKNOWN"
        row["original_candidate_id"] = key_row.get("candidate_id") or key_row.get("original_candidate_id") or "UNKNOWN"
        row["profile"] = key_row.get("profile") or row.get("profile") or "UNKNOWN"
        row["title"] = key_row.get("title") or "UNKNOWN"
        unblinded.append(row)

    write_jsonl(postprocess_dir / "personalized_scores_unblinded.jsonl", unblinded)
    write_personalized_formulation_scores_csv(postprocess_dir / "personalized_scores_unblinded.csv", unblinded, unblinded=True)
    write_personalized_formulation_group_scores(postprocess_dir / "personalized_scores_by_profile.csv", unblinded, ["profile"])
    write_personalized_formulation_group_scores(postprocess_dir / "personalized_scores_by_candidate.csv", unblinded, ["original_candidate_id", "profile", "title"])
    write_personalized_formulation_action_counts(postprocess_dir / "recommended_actions_by_candidate.csv", unblinded)

    metadata_path = scoring_dir / "judge_run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    metadata["postprocess_unblind_completed_at"] = utc_now_iso()
    metadata["weighted_composite_computed"] = False
    metadata["pairwise_enabled"] = False
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest_path = scoring_dir / "scoring_inputs_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest["blinding_key_read_during_postprocess"] = True
    manifest["blinding_key_read_during_scoring"] = False
    manifest["pairwise_preferences_written"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_personalized_formulation_audit(
        scoring_dir / "judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=read_jsonl(scoring_dir / "parse_errors.jsonl") if (scoring_dir / "parse_errors.jsonl").exists() else [],
        raw_responses=read_jsonl(scoring_dir / "raw_model_responses.jsonl") if (scoring_dir / "raw_model_responses.jsonl").exists() else [],
        unblind=True,
    )
    return {"scores_unblinded": unblinded}


def write_prism_idea_quality_group_scores(path: Path, rows: list[dict[str, Any]], group_keys: list[str]) -> None:
    fieldnames = group_keys + ["n"]
    for key in PRISM_IDEA_QUALITY_CRITERIA:
        fieldnames.extend([f"mean_{key}", f"std_{key}", f"se_{key}"])
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(tuple(str(row.get(key, "UNKNOWN")) for key in group_keys), []).append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group, group_rows in sorted(grouped.items()):
            out = {key: group[index] for index, key in enumerate(group_keys)}
            out["n"] = len(group_rows)
            for criterion in PRISM_IDEA_QUALITY_CRITERIA:
                vals = [float(row.get("scores", {}).get(criterion)) for row in group_rows if isinstance(row.get("scores", {}).get(criterion), int)]
                out[f"mean_{criterion}"] = _mean(vals)
                out[f"std_{criterion}"] = _stddev(vals)
                out[f"se_{criterion}"] = _stderr(vals)
            writer.writerow(out)


def write_prism_idea_quality_action_counts(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["method", "n"] + sorted(PRISM_IDEA_QUALITY_ACTIONS)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("method", "UNKNOWN")), []).append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for method, method_rows in sorted(grouped.items()):
            counts = collections.Counter(str(row.get("recommended_action")) for row in method_rows)
            out = {"method": method, "n": len(method_rows)}
            for action in sorted(PRISM_IDEA_QUALITY_ACTIONS):
                out[action] = counts.get(action, 0)
            writer.writerow(out)


def postprocess_unblind_prism_idea_quality(
    *,
    scoring_dir: Path,
    postprocess_dir: Path,
    blinding_key_file: Path,
) -> dict[str, Any]:
    postprocess_dir.mkdir(parents=True, exist_ok=True)
    scores = read_jsonl(scoring_dir / "prism_idea_quality_scores_blinded.jsonl")
    key = load_formulation_quality_blinding_key(blinding_key_file)
    unblinded: list[dict[str, Any]] = []
    for score in scores:
        key_row = key.get(str(score.get("candidate_id")), {})
        row = dict(score)
        row["method"] = key_row.get("method_hidden_label") or key_row.get("method") or "UNKNOWN"
        row["original_candidate_id"] = key_row.get("candidate_id") or key_row.get("original_candidate_id") or "UNKNOWN"
        row["title"] = key_row.get("title") or "UNKNOWN"
        unblinded.append(row)

    write_jsonl(postprocess_dir / "prism_idea_quality_scores_unblinded.jsonl", unblinded)
    write_prism_idea_quality_scores_csv(postprocess_dir / "prism_idea_quality_scores_unblinded.csv", unblinded, unblinded=True)
    write_prism_idea_quality_group_scores(postprocess_dir / "prism_idea_quality_scores_by_method.csv", unblinded, ["method"])
    write_prism_idea_quality_group_scores(postprocess_dir / "prism_idea_quality_scores_by_domain.csv", unblinded, ["domain"])
    write_prism_idea_quality_group_scores(postprocess_dir / "prism_idea_quality_scores_by_domain_method.csv", unblinded, ["domain", "method"])
    write_prism_idea_quality_action_counts(postprocess_dir / "recommended_actions_by_method.csv", unblinded)

    metadata_path = scoring_dir / "judge_run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    metadata["postprocess_unblind_completed_at"] = utc_now_iso()
    metadata["weighted_composite_computed"] = False
    metadata["pairwise_enabled"] = False
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest_path = scoring_dir / "scoring_inputs_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest["blinding_key_read_during_postprocess"] = True
    manifest["blinding_key_read_during_scoring"] = False
    manifest["pairwise_preferences_written"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_prism_idea_quality_audit(
        scoring_dir / "judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=read_jsonl(scoring_dir / "parse_errors.jsonl") if (scoring_dir / "parse_errors.jsonl").exists() else [],
        raw_responses=read_jsonl(scoring_dir / "raw_model_responses.jsonl") if (scoring_dir / "raw_model_responses.jsonl").exists() else [],
        unblind=True,
    )
    return {"scores_unblinded": unblinded}


def _winner_pool(row: dict[str, Any]) -> str:
    if row.get("winner") == "A":
        return str(row.get("candidate_a_pool", "UNKNOWN"))
    if row.get("winner") == "B":
        return str(row.get("candidate_b_pool", "UNKNOWN"))
    return str(row.get("winner"))


def _method_family(pool: str) -> str:
    if pool.startswith("SGHA_"):
        return "SGHA"
    return pool


def _pair_stats(rows: list[dict[str, Any]], first_pool: str, second_pool: str) -> dict[str, Any]:
    relevant = [
        row
        for row in rows
        if {row.get("candidate_a_pool"), row.get("candidate_b_pool")} == {first_pool, second_pool}
    ]
    wins = losses = ties = cannot = 0
    for row in relevant:
        winner = row.get("winner")
        if winner == "CANNOT_JUDGE":
            cannot += 1
        elif winner == "TIE":
            ties += 1
        elif _winner_pool(row) == first_pool:
            wins += 1
        elif _winner_pool(row) == second_pool:
            losses += 1
    non_ties = wins + losses
    scorable = wins + losses + ties
    return {
        "first_pool": first_pool,
        "second_pool": second_pool,
        "comparisons": len(relevant),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "cannot_judge": cannot,
        "win_rate_excluding_ties": round(wins / non_ties, 4) if non_ties else "",
        "win_rate_tie_half": round((wins + 0.5 * ties) / scorable, 4) if scorable else "",
    }


def _write_pairwise_results_unblinded_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "pair_id",
        "domain",
        "comparison_group",
        "comparison_type",
        "candidate_a_pool",
        "candidate_a_original_id",
        "candidate_a_title",
        "candidate_b_pool",
        "candidate_b_original_id",
        "candidate_b_title",
        "winner",
        "winning_pool",
        "winning_candidate_id",
        "confidence",
        "criterion_winners",
        "why_winner",
        "candidate_a_weakness",
        "candidate_b_weakness",
        "novelty_caveat",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {key: row.get(key) for key in fieldnames}
            out["criterion_winners"] = json.dumps(row.get("criterion_winners", {}), ensure_ascii=False)
            writer.writerow(out)


def _write_win_rates_by_pool(path: Path, rows: list[dict[str, Any]]) -> None:
    pools = sorted({str(row.get("candidate_a_pool")) for row in rows} | {str(row.get("candidate_b_pool")) for row in rows})
    fieldnames = ["pool", "comparisons", "wins", "losses", "ties", "cannot_judge", "win_rate_excluding_ties", "win_rate_tie_half"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for pool in pools:
            wins = losses = ties = cannot = total = 0
            for row in rows:
                if pool not in {row.get("candidate_a_pool"), row.get("candidate_b_pool")}:
                    continue
                total += 1
                winner = row.get("winner")
                if winner == "CANNOT_JUDGE":
                    cannot += 1
                elif winner == "TIE":
                    ties += 1
                elif _winner_pool(row) == pool:
                    wins += 1
                else:
                    losses += 1
            non_ties = wins + losses
            scorable = wins + losses + ties
            writer.writerow(
                {
                    "pool": pool,
                    "comparisons": total,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "cannot_judge": cannot,
                    "win_rate_excluding_ties": round(wins / non_ties, 4) if non_ties else "",
                    "win_rate_tie_half": round((wins + 0.5 * ties) / scorable, 4) if scorable else "",
                }
            )


def _write_win_rates_by_method(path: Path, rows: list[dict[str, Any]]) -> None:
    methods = sorted({_method_family(str(row.get("candidate_a_pool"))) for row in rows} | {_method_family(str(row.get("candidate_b_pool"))) for row in rows})
    fieldnames = ["method", "comparisons", "wins", "losses", "ties", "cannot_judge", "win_rate_excluding_ties", "win_rate_tie_half"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for method in methods:
            wins = losses = ties = cannot = total = 0
            for row in rows:
                a_method = _method_family(str(row.get("candidate_a_pool")))
                b_method = _method_family(str(row.get("candidate_b_pool")))
                if method not in {a_method, b_method}:
                    continue
                total += 1
                winner = row.get("winner")
                if winner == "CANNOT_JUDGE":
                    cannot += 1
                elif winner == "TIE":
                    ties += 1
                elif (winner == "A" and a_method == method) or (winner == "B" and b_method == method):
                    wins += 1
                else:
                    losses += 1
            non_ties = wins + losses
            scorable = wins + losses + ties
            writer.writerow(
                {
                    "method": method,
                    "comparisons": total,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "cannot_judge": cannot,
                    "win_rate_excluding_ties": round(wins / non_ties, 4) if non_ties else "",
                    "win_rate_tie_half": round((wins + 0.5 * ties) / scorable, 4) if scorable else "",
                }
            )


def _write_criterion_win_rates(path: Path, rows: list[dict[str, Any]]) -> None:
    groups = sorted({str(row.get("comparison_group")) for row in rows})
    fieldnames = [
        "comparison_group",
        "criterion",
        "first_pool",
        "second_pool",
        "first_wins",
        "second_wins",
        "ties",
        "cannot_judge",
        "first_win_rate_excluding_ties",
        "first_win_rate_tie_half",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group in groups:
            group_rows = [row for row in rows if row.get("comparison_group") == group]
            if not group_rows:
                continue
            first_pool, second_pool = group.split("_vs_", 1) if "_vs_" in group else ("UNKNOWN", "UNKNOWN")
            for criterion in PAIRWISE_PREFERENCE_CRITERIA:
                first_wins = second_wins = ties = cannot = 0
                for row in group_rows:
                    if row.get("winner") == "CANNOT_JUDGE":
                        cannot += 1
                        continue
                    side_value = row.get("criterion_winners", {}).get(criterion)
                    if side_value == "TIE":
                        ties += 1
                    elif side_value == "A":
                        if row.get("candidate_a_pool") == first_pool:
                            first_wins += 1
                        else:
                            second_wins += 1
                    elif side_value == "B":
                        if row.get("candidate_b_pool") == first_pool:
                            first_wins += 1
                        else:
                            second_wins += 1
                non_ties = first_wins + second_wins
                scorable = first_wins + second_wins + ties
                writer.writerow(
                    {
                        "comparison_group": group,
                        "criterion": criterion,
                        "first_pool": first_pool,
                        "second_pool": second_pool,
                        "first_wins": first_wins,
                        "second_wins": second_wins,
                        "ties": ties,
                        "cannot_judge": cannot,
                        "first_win_rate_excluding_ties": round(first_wins / non_ties, 4) if non_ties else "",
                        "first_win_rate_tie_half": round((first_wins + 0.5 * ties) / scorable, 4) if scorable else "",
                    }
                )


def _candidate_win_counts(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    counts: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        for side in ("a", "b"):
            key = (str(row.get(f"candidate_{side}_pool")), str(row.get(f"candidate_{side}_original_id")))
            counts.setdefault(key, {"pool": key[0], "candidate_id": key[1], "title": row.get(f"candidate_{side}_title"), "wins": 0, "losses": 0, "ties": 0})
        winner = row.get("winner")
        a_key = (str(row.get("candidate_a_pool")), str(row.get("candidate_a_original_id")))
        b_key = (str(row.get("candidate_b_pool")), str(row.get("candidate_b_original_id")))
        if winner == "A":
            counts[a_key]["wins"] += 1
            counts[b_key]["losses"] += 1
        elif winner == "B":
            counts[b_key]["wins"] += 1
            counts[a_key]["losses"] += 1
        elif winner == "TIE":
            counts[a_key]["ties"] += 1
            counts[b_key]["ties"] += 1
    return counts


def _pairwise_metric_lines(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| comparison | n | first wins | second wins | ties | cannot judge | first win rate excl ties | first win rate tie=0.5 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for second_pool in ("SIMPLE_QWEN", "QWEN_RAG", "NATIVE_AI_SCIENTIST_V2", "SGHA_DIRECT", "SGHA_AMBITION_FINAL", "SGHA_LEGACY_EVOLUTION"):
        stats = _pair_stats(rows, "SGHA_FINAL_FAMILY", second_pool)
        if stats["comparisons"]:
            lines.append(
                f"| SGHA_FINAL_FAMILY vs {second_pool} | {stats['comparisons']} | {stats['wins']} | {stats['losses']} | {stats['ties']} | {stats['cannot_judge']} | {stats['win_rate_excluding_ties']} | {stats['win_rate_tie_half']} |"
            )
    return lines


def _write_pairwise_judge_summary(path: Path, rows: list[dict[str, Any]], metadata: dict[str, Any], parse_errors: list[dict[str, Any]]) -> None:
    lines = [
        "# Pairwise Judge Summary",
        "",
        f"- model: `{metadata.get('model')}`",
        f"- candidates/pairs scored: {len(rows)}",
        f"- parse errors: {len(parse_errors)}",
        "- no numeric scores or weighted composite score computed",
        "",
        "## Main Win Rates",
        "",
        *_pairwise_metric_lines(rows),
    ]
    counts = _candidate_win_counts(rows)
    if counts:
        strongest = sorted(counts.values(), key=lambda row: (-row["wins"], row["losses"], row["pool"], row["candidate_id"]))[0]
        lines.extend(
            [
                "",
                "## Strongest Winning Candidate",
                "",
                f"- {strongest['pool']} `{strongest['candidate_id']}`: {strongest['wins']} wins, {strongest['losses']} losses, {strongest['ties']} ties",
                f"- title: {strongest.get('title')}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_pairwise_bandits_report(path: Path, rows: list[dict[str, Any]], metadata: dict[str, Any], manifest: dict[str, Any], parse_errors: list[dict[str, Any]]) -> None:
    trial_dir = path.parent
    packet_audit = trial_dir / "pairwise_packets" / "pairwise_packet_audit.json"
    packet_data = json.loads(packet_audit.read_text(encoding="utf-8")) if packet_audit.exists() else {}
    counts = _candidate_win_counts(rows)
    strongest = sorted(counts.values(), key=lambda row: (-row["wins"], row["losses"], row["pool"], row["candidate_id"]))[0] if counts else {}
    baseline_beats = [
        row
        for row in rows
        if str(row.get("comparison_type")) == "primary"
        and _winner_pool(row) not in {"SGHA_FINAL_FAMILY", "TIE", "CANNOT_JUDGE"}
    ]
    lines = [
        "# Pairwise Bandits Report",
        "",
        "## Trial",
        "",
        f"- trial directory: `{trial_dir}`",
        f"- OpenRouter model: `{metadata.get('model')}`",
        f"- pairwise comparisons scored: {len(rows)}",
        f"- parse errors: {len(parse_errors)}",
        "- numeric scores: not computed",
        "- weighted composite score: not computed",
        "- external search: not used",
        "- caveat: Bandits-only trial, not a final paper-wide result.",
        "- caveat: novelty is judged only as potential from provided text; no external novelty proof.",
        "",
        "## Candidate Pools",
        "",
    ]
    for pool, count in packet_data.get("pool_counts", {}).items():
        selected = packet_data.get("selected_counts", {}).get(pool, 0)
        lines.append(f"- {pool}: {count} available, {selected} selected")
    lines.extend(
        [
            "",
            "## Pairwise Win Rates",
            "",
            *_pairwise_metric_lines(rows),
            "",
            "## Strongest Winning Candidate",
            "",
        ]
    )
    if strongest:
        lines.extend(
            [
                f"- pool: {strongest.get('pool')}",
                f"- candidate: `{strongest.get('candidate_id')}`",
                f"- title: {strongest.get('title')}",
                f"- wins/losses/ties: {strongest.get('wins')}/{strongest.get('losses')}/{strongest.get('ties')}",
            ]
        )
    lines.extend(["", "## Primary Pairs Where A Non-Final Candidate Beat SGHA Final", ""])
    if baseline_beats:
        for row in baseline_beats:
            lines.append(
                f"- {row['pair_id']}: {row['winning_pool']} `{row['winning_candidate_id']}` beat SGHA_FINAL_FAMILY "
                f"({row['candidate_a_pool']} `{row['candidate_a_original_id']}` vs {row['candidate_b_pool']} `{row['candidate_b_original_id']}`)"
            )
    else:
        lines.append("- None.")
    ties = sum(1 for row in rows if row.get("winner") == "TIE")
    cannot = sum(1 for row in rows if row.get("winner") == "CANNOT_JUDGE")
    lines.extend(
        [
            "",
            "## Discriminativeness",
            "",
            f"- ties: {ties}",
            f"- cannot judge: {cannot}",
            "- This pairwise trial is more discriminative than the independent scoring trial because it produces direct wins/losses between candidate pools instead of relying on compressed 1-5 pursuit-priority scores.",
            "",
            "## Output Files",
            "",
            f"- unblinded results: `{trial_dir / 'pairwise_results' / 'pairwise_results_unblinded.csv'}`",
            f"- pool win rates: `{trial_dir / 'pairwise_results' / 'win_rates_by_pool.csv'}`",
            f"- criterion win rates: `{trial_dir / 'pairwise_results' / 'criterion_win_rates.csv'}`",
            f"- judge summary: `{trial_dir / 'pairwise_results' / 'pairwise_judge_summary.md'}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def postprocess_unblind_pairwise_preference(
    *,
    config: dict[str, Any],
    output_dir: Path,
    scores: list[dict[str, Any]],
    metadata: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    key_path = Path(str(manifest.get("blinding_key_file") or output_dir.parent / "pairwise_packets" / "pairwise_blinding_key.json"))
    key = load_pairwise_preference_blinding_key(key_path)
    unblinded: list[dict[str, Any]] = []
    for score in scores:
        key_row = key.get(str(score.get("pair_id")), {})
        row = dict(score)
        row.update(
            {
                "comparison_group": key_row.get("comparison_group", "UNKNOWN"),
                "comparison_type": key_row.get("comparison_type", "UNKNOWN"),
                "candidate_a_pool": key_row.get("candidate_a_pool", "UNKNOWN"),
                "candidate_a_original_id": key_row.get("candidate_a_original_id", "UNKNOWN"),
                "candidate_a_title": key_row.get("candidate_a_title", "UNKNOWN"),
                "candidate_b_pool": key_row.get("candidate_b_pool", "UNKNOWN"),
                "candidate_b_original_id": key_row.get("candidate_b_original_id", "UNKNOWN"),
                "candidate_b_title": key_row.get("candidate_b_title", "UNKNOWN"),
            }
        )
        winning_pool = _winner_pool(row)
        row["winning_pool"] = winning_pool
        if row.get("winner") == "A":
            row["winning_candidate_id"] = row.get("candidate_a_original_id")
            row["winning_title"] = row.get("candidate_a_title")
        elif row.get("winner") == "B":
            row["winning_candidate_id"] = row.get("candidate_b_original_id")
            row["winning_title"] = row.get("candidate_b_title")
        else:
            row["winning_candidate_id"] = row.get("winner")
            row["winning_title"] = row.get("winner")
        unblinded.append(row)

    parse_errors = read_jsonl(output_dir / "parse_errors.jsonl") if (output_dir / "parse_errors.jsonl").exists() else []
    write_jsonl(output_dir / "pairwise_results_unblinded.jsonl", unblinded)
    _write_pairwise_results_unblinded_csv(output_dir / "pairwise_results_unblinded.csv", unblinded)
    _write_win_rates_by_method(output_dir / "win_rates_by_method.csv", unblinded)
    _write_win_rates_by_pool(output_dir / "win_rates_by_pool.csv", unblinded)
    _write_criterion_win_rates(output_dir / "criterion_win_rates.csv", unblinded)
    _write_pairwise_judge_summary(output_dir / "pairwise_judge_summary.md", unblinded, metadata, parse_errors)

    metadata_path = output_dir / "judge_run_metadata.json"
    metadata["postprocess_unblind_completed_at"] = utc_now_iso()
    metadata["weighted_composite_computed"] = False
    metadata["numeric_scores_computed"] = False
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest_path = output_dir / "scoring_inputs_manifest.json"
    manifest["blinding_key_read_during_postprocess"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    raw = read_jsonl(output_dir / "raw_model_responses.jsonl") if (output_dir / "raw_model_responses.jsonl").exists() else []
    write_pairwise_preference_audit(
        output_dir / "judge_quality_audit.md",
        metadata=metadata,
        manifest=manifest,
        scores=scores,
        parse_errors=parse_errors,
        raw_responses=raw,
        unblind=True,
    )
    _write_pairwise_bandits_report(output_dir.parent / "PAIRWISE_BANDITS_REPORT.md", unblinded, metadata, manifest, parse_errors)
    return {"scores_unblinded": unblinded}


def _four_way_candidate_rank_rows(unblinded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in unblinded:
        domain = result.get("domain")
        key = result.get("blinding_key", {})
        candidate_rows: dict[str, dict[str, Any]] = {}
        for cid in result.get("candidate_ids", []):
            key_row = key.get(str(cid), {})
            candidate_rows[str(cid)] = {
                "domain": domain,
                "blinded_candidate_id": cid,
                "method": key_row.get("method", "UNKNOWN"),
                "original_candidate_id": key_row.get("candidate_id", "UNKNOWN"),
                "title": key_row.get("title", "UNKNOWN"),
                "best_overall": result.get("best_overall_candidate", {}).get("candidate_id") == cid,
                "most_auditable": result.get("most_auditable_candidate", {}).get("candidate_id") == cid,
                "most_actionable": result.get("most_actionable_candidate", {}).get("candidate_id") == cid,
                "most_novel_potential": result.get("most_novel_potential_candidate", {}).get("candidate_id") == cid,
            }
        for criterion, ranking in result.get("criterion_rankings", {}).items():
            for item in ranking:
                cid = str(item.get("candidate_id"))
                candidate_rows[cid][criterion] = item.get("rank")
                candidate_rows[cid][f"{criterion}_reason"] = item.get("reason")
        rows.extend(candidate_rows.values())
    return rows


def _write_four_way_unblinded_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "domain",
        "method",
        "original_candidate_id",
        "blinded_candidate_id",
        "title",
        *FOUR_WAY_RANK_CRITERIA,
        "best_overall",
        "most_auditable",
        "most_actionable",
        "most_novel_potential",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _write_mean_rank_by_method(path: Path, rows: list[dict[str, Any]]) -> None:
    methods = sorted({str(row.get("method")) for row in rows})
    fieldnames = ["method", "n_domains"] + [f"mean_rank_{criterion}" for criterion in FOUR_WAY_RANK_CRITERIA]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for method in methods:
            method_rows = [row for row in rows if row.get("method") == method]
            out = {"method": method, "n_domains": len({row.get("domain") for row in method_rows})}
            for criterion in FOUR_WAY_RANK_CRITERIA:
                vals = [float(row[criterion]) for row in method_rows if isinstance(row.get(criterion), int)]
                out[f"mean_rank_{criterion}"] = round(sum(vals) / len(vals), 4) if vals else ""
            writer.writerow(out)


def _write_win_counts_by_method(path: Path, rows: list[dict[str, Any]]) -> None:
    methods = sorted({str(row.get("method")) for row in rows})
    fieldnames = ["method", "best_overall_count", "most_auditable_count", "most_actionable_count", "most_novel_potential_count"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for method in methods:
            method_rows = [row for row in rows if row.get("method") == method]
            writer.writerow(
                {
                    "method": method,
                    "best_overall_count": sum(1 for row in method_rows if row.get("best_overall")),
                    "most_auditable_count": sum(1 for row in method_rows if row.get("most_auditable")),
                    "most_actionable_count": sum(1 for row in method_rows if row.get("most_actionable")),
                    "most_novel_potential_count": sum(1 for row in method_rows if row.get("most_novel_potential")),
                }
            )


def _write_criterion_rank_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    methods = sorted({str(row.get("method")) for row in rows})
    fieldnames = ["criterion", "method", "n", "mean_rank", "rank1_count"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for criterion in FOUR_WAY_RANK_CRITERIA:
            for method in methods:
                vals = [int(row[criterion]) for row in rows if row.get("method") == method and isinstance(row.get(criterion), int)]
                writer.writerow(
                    {
                        "criterion": criterion,
                        "method": method,
                        "n": len(vals),
                        "mean_rank": round(sum(vals) / len(vals), 4) if vals else "",
                        "rank1_count": sum(1 for val in vals if val == 1),
                    }
                )


def _write_domain_winners(path: Path, unblinded: list[dict[str, Any]]) -> None:
    fieldnames = [
        "domain",
        "best_overall_method",
        "best_overall_candidate_id",
        "most_auditable_method",
        "most_auditable_candidate_id",
        "most_actionable_method",
        "most_actionable_candidate_id",
        "most_novel_potential_method",
        "most_novel_potential_candidate_id",
        "confidence",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in unblinded:
            key = result.get("blinding_key", {})
            out = {"domain": result.get("domain"), "confidence": result.get("confidence")}
            for winner_key, prefix in [
                ("best_overall_candidate", "best_overall"),
                ("most_auditable_candidate", "most_auditable"),
                ("most_actionable_candidate", "most_actionable"),
                ("most_novel_potential_candidate", "most_novel_potential"),
            ]:
                cid = result.get(winner_key, {}).get("candidate_id")
                key_row = key.get(str(cid), {})
                out[f"{prefix}_method"] = key_row.get("method", "UNKNOWN")
                out[f"{prefix}_candidate_id"] = key_row.get("candidate_id", "UNKNOWN")
            writer.writerow(out)


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_four_way_summary(path: Path, candidate_rows: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    mean_rows: dict[str, dict[str, Any]] = {}
    for method in sorted({str(row.get("method")) for row in candidate_rows}):
        method_rows = [row for row in candidate_rows if row.get("method") == method]
        mean_rows[method] = {
            criterion: round(sum(float(row[criterion]) for row in method_rows) / len(method_rows), 4)
            for criterion in FOUR_WAY_RANK_CRITERIA
        }
    winner_counts = {
        method: {
            "best_overall": sum(1 for row in candidate_rows if row.get("method") == method and row.get("best_overall")),
            "most_auditable": sum(1 for row in candidate_rows if row.get("method") == method and row.get("most_auditable")),
            "most_actionable": sum(1 for row in candidate_rows if row.get("method") == method and row.get("most_actionable")),
            "most_novel_potential": sum(1 for row in candidate_rows if row.get("method") == method and row.get("most_novel_potential")),
        }
        for method in sorted({str(row.get("method")) for row in candidate_rows})
    }
    lines = [
        "# Four-Way Ranked Judge Summary",
        "",
        f"- model: `{metadata.get('model')}`",
        f"- domains judged: {len({row.get('domain') for row in candidate_rows})}",
        "- lower mean rank is better",
        "- no weighted composite score computed",
        "",
        "## Mean Ranks By Method",
        "",
        "| method | pursuit_priority | evidence_grounding | formalizability |",
        "|---|---:|---:|---:|",
    ]
    for method, values in mean_rows.items():
        lines.append(f"| {method} | {values['pursuit_priority']} | {values['evidence_grounding']} | {values['formalizability']} |")
    lines.extend(["", "## Special Winner Counts", "", "| method | best overall | most auditable | most actionable | most novel potential |", "|---|---:|---:|---:|---:|"])
    for method, counts in winner_counts.items():
        lines.append(f"| {method} | {counts['best_overall']} | {counts['most_auditable']} | {counts['most_actionable']} | {counts['most_novel_potential']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_best_of_method_report(path: Path, candidate_rows: list[dict[str, Any]], unblinded: list[dict[str, Any]], metadata: dict[str, Any], parse_errors: list[dict[str, Any]]) -> None:
    selection_path = path.parent / "selection" / "selected_best_candidates_unblinded.jsonl"
    selected = read_jsonl(selection_path) if selection_path.exists() else []
    mean_by_method: dict[str, dict[str, float]] = {}
    for method in sorted({str(row.get("method")) for row in candidate_rows}):
        method_rows = [row for row in candidate_rows if row.get("method") == method]
        mean_by_method[method] = {
            criterion: round(sum(float(row[criterion]) for row in method_rows) / len(method_rows), 4)
            for criterion in FOUR_WAY_RANK_CRITERIA
        }
    winner_counts = {
        method: {
            "best_overall": sum(1 for row in candidate_rows if row.get("method") == method and row.get("best_overall")),
            "most_auditable": sum(1 for row in candidate_rows if row.get("method") == method and row.get("most_auditable")),
            "most_actionable": sum(1 for row in candidate_rows if row.get("method") == method and row.get("most_actionable")),
            "most_novel_potential": sum(1 for row in candidate_rows if row.get("method") == method and row.get("most_novel_potential")),
        }
        for method in sorted({str(row.get("method")) for row in candidate_rows})
    }
    lines = [
        "# Best-of-Method 4-Way Report",
        "",
        "## Trial",
        "",
        f"- evaluation directory: `{path.parent}`",
        f"- OpenRouter model: `{metadata.get('model')}`",
        f"- domains judged: {len(unblinded)}",
        f"- parse errors: {len(parse_errors)}",
        "- no weighted composite score computed",
        "- no external novelty check; novelty is only novelty potential from provided text",
        "- caveat: only five domains, not powered for statistical significance",
        "",
        "## Selected Candidates",
        "",
        "| domain | method | candidate | selection method | title |",
        "|---|---|---|---|---|",
    ]
    for row in selected:
        lines.append(f"| {row.get('domain')} | {row.get('method')} | `{row.get('candidate_id')}` | {row.get('selection_method')} | {row.get('title')} |")
    lines.extend(["", "## Mean Ranks By Method", "", "| method | pursuit_priority | evidence_grounding | formalizability | actionability | best overall count |", "|---|---:|---:|---:|---:|---:|"])
    for method, values in mean_by_method.items():
        lines.append(f"| {method} | {values['pursuit_priority']} | {values['evidence_grounding']} | {values['formalizability']} | {values['actionability']} | {winner_counts[method]['best_overall']} |")
    lines.extend(["", "## Domain-Level Winners", "", "| domain | best overall | most auditable | most actionable | most novel potential |", "|---|---|---|---|---|"])
    for result in unblinded:
        key = result.get("blinding_key", {})
        def winner_label(winner_key: str) -> str:
            cid = result.get(winner_key, {}).get("candidate_id")
            key_row = key.get(str(cid), {})
            return f"{key_row.get('method', 'UNKNOWN')} `{key_row.get('candidate_id', 'UNKNOWN')}`"

        lines.append(
            f"| {result.get('domain')} | {winner_label('best_overall_candidate')} | {winner_label('most_auditable_candidate')} | {winner_label('most_actionable_candidate')} | {winner_label('most_novel_potential_candidate')} |"
        )
    lines.extend(
        [
            "",
            "## Recommended Paper Use",
            "",
            "Use these results as descriptive ranking / qualitative evidence only. Do not present them as a statistical significance claim.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def postprocess_unblind_four_way_ranked(
    *,
    config: dict[str, Any],
    output_dir: Path,
    scores: list[dict[str, Any]],
    metadata: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    packet_dir = Path(str(manifest.get("packet_dir") or output_dir.parent / "four_way_packets"))
    key_map = load_four_way_blinding_keys(packet_dir)
    unblinded: list[dict[str, Any]] = []
    for score in scores:
        row = dict(score)
        domain_key = key_map.get(str(score.get("domain")), {})
        row["blinding_key"] = domain_key
        for special in FOUR_WAY_SPECIAL_WINNERS:
            cid = str(row.get(special, {}).get("candidate_id"))
            key_row = domain_key.get(cid, {})
            row[special]["method"] = key_row.get("method", "UNKNOWN")
            row[special]["original_candidate_id"] = key_row.get("candidate_id", "UNKNOWN")
            row[special]["title"] = key_row.get("title", "UNKNOWN")
        unblinded.append(row)
    parse_errors = read_jsonl(output_dir / "parse_errors.jsonl") if (output_dir / "parse_errors.jsonl").exists() else []
    candidate_rows = _four_way_candidate_rank_rows(unblinded)
    write_jsonl(output_dir / "four_way_results_unblinded.jsonl", unblinded)
    _write_four_way_unblinded_csv(output_dir / "four_way_results_unblinded.csv", candidate_rows)
    _write_mean_rank_by_method(output_dir / "mean_rank_by_method.csv", candidate_rows)
    _write_win_counts_by_method(output_dir / "win_counts_by_method.csv", candidate_rows)
    _write_criterion_rank_summary(output_dir / "criterion_rank_summary.csv", candidate_rows)
    _write_domain_winners(output_dir / "domain_winners.csv", unblinded)
    _write_four_way_summary(output_dir / "four_way_judge_summary.md", candidate_rows, metadata)

    metadata_path = output_dir / "judge_run_metadata.json"
    metadata["postprocess_unblind_completed_at"] = utc_now_iso()
    metadata["weighted_composite_computed"] = False
    metadata["numeric_scores_computed"] = False
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest_path = output_dir / "scoring_inputs_manifest.json"
    manifest["blinding_key_read_during_postprocess"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    raw = read_jsonl(output_dir / "raw_model_responses.jsonl") if (output_dir / "raw_model_responses.jsonl").exists() else []
    write_four_way_audit(output_dir / "judge_quality_audit.md", metadata=metadata, manifest=manifest, scores=scores, parse_errors=parse_errors, raw_responses=raw, unblind=True)
    _write_best_of_method_report(output_dir.parent / "BEST_OF_METHOD_4WAY_REPORT.md", candidate_rows, unblinded, metadata, parse_errors)
    return {"scores_unblinded": unblinded, "candidate_rank_rows": candidate_rows}


def write_unblinded_scores_csv(path: Path, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    ids = rubric_ids(config)
    fieldnames = (
        ["comparison_id", "domain", "baseline", "candidate_a_id", "candidate_a_method", "candidate_a_original_id", "candidate_b_id", "candidate_b_method", "candidate_b_original_id"]
        + [f"candidate_a_{key}" for key in ids]
        + [f"candidate_b_{key}" for key in ids]
        + ["pairwise_preference", "confidence", "rationale", "novelty_caveat"]
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {key: row.get(key) for key in fieldnames}
            for key in ids:
                flat[f"candidate_a_{key}"] = row.get("candidate_a_scores", {}).get(key)
                flat[f"candidate_b_{key}"] = row.get("candidate_b_scores", {}).get(key)
            writer.writerow(flat)


def write_independent_unblinded_scores_csv(path: Path, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    ids = rubric_ids(config)
    fieldnames = ["candidate_id", "original_candidate_id", "domain", "method", "title"] + ids + [
        "rank_in_batch",
        "confidence",
        "pre_score_checklist",
        "strengths",
        "weaknesses",
        "cap_rules_triggered",
        "cap_exceptions",
        "score_justification",
        "calibration_flags",
        "batch_calibration_notes",
        "rationale",
        "novelty_caveat",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {
                "candidate_id": row.get("candidate_id"),
                "original_candidate_id": row.get("original_candidate_id"),
                "domain": row.get("domain"),
                "method": row.get("method"),
                "title": row.get("title"),
                "rank_in_batch": row.get("rank_in_batch"),
                "confidence": row.get("confidence"),
                "pre_score_checklist": json.dumps(row.get("pre_score_checklist", {}), ensure_ascii=False),
                "strengths": json.dumps(row.get("strengths", []), ensure_ascii=False),
                "weaknesses": json.dumps(row.get("weaknesses", []), ensure_ascii=False),
                "cap_rules_triggered": json.dumps(row.get("cap_rules_triggered", []), ensure_ascii=False),
                "cap_exceptions": json.dumps(row.get("cap_exceptions", []), ensure_ascii=False),
                "score_justification": json.dumps(row.get("score_justification", {}), ensure_ascii=False),
                "calibration_flags": json.dumps(row.get("calibration_flags", []), ensure_ascii=False),
                "batch_calibration_notes": row.get("batch_calibration_notes"),
                "rationale": row.get("rationale"),
                "novelty_caveat": row.get("novelty_caveat"),
            }
            for key in ids:
                flat[key] = row.get("scores", {}).get(key)
            writer.writerow(flat)


def write_role_based_unblinded_scores_csv(path: Path, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    ids = role_score_ids(config)
    fieldnames = ["candidate_id", "original_candidate_id", "domain", "method", "title", "confidence", "valid_for_run"] + ids + [
        "invalid_roles",
        "cap_rules_triggered",
        "cap_violations",
        "role_strengths",
        "role_weaknesses",
        "role_rationales",
        "novelty_caveat",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {
                "candidate_id": row.get("candidate_id"),
                "original_candidate_id": row.get("original_candidate_id"),
                "domain": row.get("domain"),
                "method": row.get("method"),
                "title": row.get("title"),
                "confidence": row.get("confidence"),
                "valid_for_run": row.get("valid_for_run"),
                "invalid_roles": json.dumps(row.get("invalid_roles", []), ensure_ascii=False),
                "cap_rules_triggered": json.dumps(row.get("cap_rules_triggered", []), ensure_ascii=False),
                "cap_violations": json.dumps(row.get("cap_violations", []), ensure_ascii=False),
                "role_strengths": json.dumps({rid: rec.get("strengths", []) for rid, rec in row.get("role_scores", {}).items()}, ensure_ascii=False),
                "role_weaknesses": json.dumps({rid: rec.get("weaknesses", []) for rid, rec in row.get("role_scores", {}).items()}, ensure_ascii=False),
                "role_rationales": json.dumps({rid: rec.get("rationale", "") for rid, rec in row.get("role_scores", {}).items()}, ensure_ascii=False),
                "novelty_caveat": row.get("novelty_caveat"),
            }
            for role_id, role_record in row.get("role_scores", {}).items():
                for key in role_score_ids(config, role_id):
                    flat[key] = role_record.get(key)
            writer.writerow(flat)


def _role_based_flat_score(row: dict[str, Any], key: str) -> int | None:
    for role_record in row.get("role_scores", {}).values():
        value = role_record.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def write_role_based_scores_by_candidate(path: Path, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    ids = role_score_ids(config)
    fieldnames = ["candidate_id", "original_candidate_id", "domain", "method", "title", "confidence", "valid_for_run"] + ids + ["invalid_roles", "cap_violations"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {
                "candidate_id": row.get("candidate_id"),
                "original_candidate_id": row.get("original_candidate_id"),
                "domain": row.get("domain"),
                "method": row.get("method"),
                "title": row.get("title"),
                "confidence": row.get("confidence"),
                "valid_for_run": row.get("valid_for_run"),
                "invalid_roles": json.dumps(row.get("invalid_roles", []), ensure_ascii=False),
                "cap_violations": json.dumps(row.get("cap_violations", []), ensure_ascii=False),
            }
            for key in ids:
                out[key] = _role_based_flat_score(row, key)
            writer.writerow(out)


def write_role_based_group_averages(path: Path, rows: list[dict[str, Any]], config: dict[str, Any], group_key: str) -> None:
    ids = role_score_ids(config)
    if group_key == "criterion":
        fieldnames = ["criterion", "n", "mean_score"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for key in ids:
                vals = [float(value) for row in rows if isinstance((value := _role_based_flat_score(row, key)), int)]
                writer.writerow({"criterion": key, "n": len(vals), "mean_score": round(sum(vals) / len(vals), 4) if vals else ""})
        return
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(group_key, "UNKNOWN")), []).append(row)
    fieldnames = [group_key, "n"] + [f"mean_{key}" for key in ids]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group, group_rows in sorted(grouped.items()):
            out = {group_key: group, "n": len(group_rows)}
            for key in ids:
                vals = [float(value) for row in group_rows if isinstance((value := _role_based_flat_score(row, key)), int)]
                out[f"mean_{key}"] = round(sum(vals) / len(vals), 4) if vals else ""
            writer.writerow(out)


def write_role_based_summary(path: Path, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    ids = role_score_ids(config)
    by_method: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_method.setdefault(str(row.get("method", "UNKNOWN")), []).append(row)
    lines = [
        "# Role-Based 10-Point LLM Judge Summary",
        "",
        "Postprocess unblinding complete. Scores are per-role and per-criterion; no weighted composite score is computed.",
        "No pairwise preference was requested or written.",
        "",
        "| method | n | mean research_priority_10 | mean auditability_10 | mean evidence_grounding_10 | cap violations |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, method_rows in sorted(by_method.items()):
        def mean(key: str) -> str:
            vals = [float(value) for row in method_rows if isinstance((value := _role_based_flat_score(row, key)), int)]
            return str(round(sum(vals) / len(vals), 4)) if vals else ""

        cap_count = sum(len(row.get("cap_violations", [])) for row in method_rows)
        lines.append(
            f"| {method} | {len(method_rows)} | {mean('research_priority_10')} | {mean('auditability_10')} | {mean('evidence_grounding_10')} | {cap_count} |"
        )
    lines.extend(["", "## Criteria", ""])
    lines.append(", ".join(ids))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_scores_by_candidate(path: Path, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    ids = rubric_ids(config)
    fieldnames = ["candidate_id", "original_candidate_id", "domain", "method", "title"] + ids + ["rank_in_batch", "confidence", "pre_score_checklist", "cap_rules_triggered", "cap_exceptions", "calibration_flags"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {
                "candidate_id": row.get("candidate_id"),
                "original_candidate_id": row.get("original_candidate_id"),
                "domain": row.get("domain"),
                "method": row.get("method"),
                "title": row.get("title"),
            }
            for key in ids:
                out[key] = row.get("scores", {}).get(key)
            out["rank_in_batch"] = row.get("rank_in_batch")
            out["confidence"] = row.get("confidence")
            out["pre_score_checklist"] = json.dumps(row.get("pre_score_checklist", {}), ensure_ascii=False)
            out["cap_rules_triggered"] = json.dumps(row.get("cap_rules_triggered", []), ensure_ascii=False)
            out["cap_exceptions"] = json.dumps(row.get("cap_exceptions", []), ensure_ascii=False)
            out["calibration_flags"] = json.dumps(row.get("calibration_flags", []), ensure_ascii=False)
            writer.writerow(out)


def write_independent_group_averages(path: Path, rows: list[dict[str, Any]], config: dict[str, Any], group_key: str) -> None:
    ids = rubric_ids(config)
    if group_key == "criterion":
        fieldnames = ["criterion", "n", "mean_score"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for key in ids:
                vals = [float(row.get("scores", {}).get(key)) for row in rows if isinstance(row.get("scores", {}).get(key), int)]
                writer.writerow({"criterion": key, "n": len(vals), "mean_score": round(sum(vals) / len(vals), 4) if vals else ""})
        return
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(group_key, "UNKNOWN")), []).append(row)
    fieldnames = [group_key, "n"] + [f"mean_{key}" for key in ids]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group, group_rows in sorted(grouped.items()):
            out = {group_key: group, "n": len(group_rows)}
            for key in ids:
                vals = [float(row.get("scores", {}).get(key)) for row in group_rows if isinstance(row.get("scores", {}).get(key), int)]
                out[f"mean_{key}"] = round(sum(vals) / len(vals), 4) if vals else ""
            writer.writerow(out)


def write_independent_summary(path: Path, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    ids = rubric_ids(config)
    by_method: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_method.setdefault(str(row.get("method", "UNKNOWN")), []).append(row)
    lines = [
        "# Independent LLM Judge Summary",
        "",
        "Postprocess unblinding complete. Scores are per-criterion averages; no weighted composite score is computed.",
        "No pairwise preference was requested or written.",
        "",
        "| method | n | mean pursuit_priority | mean auditability_overall | mean overall_worth_reading |",
        "|---|---:|---:|---:|---:|",
    ]
    for method, method_rows in sorted(by_method.items()):
        def mean(key: str) -> str:
            vals = [float(row.get("scores", {}).get(key)) for row in method_rows if isinstance(row.get("scores", {}).get(key), int)]
            return str(round(sum(vals) / len(vals), 4)) if vals else ""

        lines.append(
            f"| {method} | {len(method_rows)} | {mean('pursuit_priority')} | {mean('auditability_overall')} | {mean('overall_worth_reading')} |"
        )
    lines.extend(["", "## Criteria", ""])
    lines.append(", ".join(ids))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _json_text(value: Any) -> str:
    if value is None:
        return NOT_PROVIDED
    if isinstance(value, str):
        text = value.strip()
        return text if text else NOT_PROVIDED
    if isinstance(value, (dict, list)):
        if not value:
            return NOT_PROVIDED
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _safe_source_context(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    allowed_keys = (
        "context_mode",
        "corpus_context_mode",
        "paper_count_available",
        "chunk_count",
        "retrieved_context_ids",
        "paper_ids_shown",
        "input_files_read_count",
        "prompt_context_sha256",
        "context_sha256",
    )
    return {key: value[key] for key in allowed_keys if key in value}


def _sanitize_blinded_text(value: str) -> str:
    text = value
    replacements = {
        "SGHA_FULL": "method-hidden",
        "SIMPLE_QWEN": "method-hidden",
        "QWEN_RAG": "method-hidden",
        "NATIVE_AI_SCIENTIST_V2": "method-hidden",
        "AI_SCIENTIST": "method-hidden",
        "AI-Scientist": "method-hidden",
        "Native AI-Scientist": "method-hidden",
        "Simple Qwen": "method-hidden",
        "Qwen+RAG": "method-hidden",
        "Qwen RAG": "method-hidden",
        "SGHA": "the system",
    }
    for old, new in replacements.items():
        text = re.sub(rf"(?<![A-Za-z0-9_\-]){re.escape(old)}(?![A-Za-z0-9_\-])", new, text, flags=re.IGNORECASE)
    text = re.sub(r"(?<![A-Za-z0-9_\-])baselines(?![A-Za-z0-9_\-])", "reference methods", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<![A-Za-z0-9_\-])baseline(?![A-Za-z0-9_\-])", "reference method", text, flags=re.IGNORECASE)
    return text


def _sanitize_candidate_for_blinding(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str):
            out[key] = _sanitize_blinded_text(value)
        else:
            out[key] = value
    return out


def _join_labeled_fields(fields: list[tuple[str, Any]]) -> str:
    parts = []
    for label, value in fields:
        text = _json_text(value)
        if text != NOT_PROVIDED:
            parts.append(f"{label}: {text}")
    return "\n".join(parts) if parts else NOT_PROVIDED


def _load_family_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("families", "project_families"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise JudgeError(f"Could not find family rows in {path}")


def _normalize_sgha_family(row: dict[str, Any]) -> dict[str, Any]:
    formal = row.get("formal_problem_formulation") if isinstance(row.get("formal_problem_formulation"), dict) else {}
    setup = formal.get("mathematical_setup") if isinstance(formal.get("mathematical_setup"), dict) else {}
    assumptions = formal.get("assumptions") if isinstance(formal.get("assumptions"), list) else row.get("assumptions")
    contribution = _join_labeled_fields(
        [
            ("theorem_target", row.get("theorem_target")),
            ("algorithmic_target", row.get("algorithmic_target")),
            ("empirical_target", row.get("empirical_target")),
            ("constructive_or_evaluation_target", row.get("constructive_or_evaluation_target")),
        ]
    )
    evaluation = _join_labeled_fields(
        [
            ("theorem_target", row.get("theorem_target")),
            ("algorithmic_target", row.get("algorithmic_target")),
            ("empirical_target", row.get("empirical_target")),
            ("evaluation_protocol", formal.get("evaluation_protocol")),
            ("falsification_condition", row.get("falsification_condition")),
        ]
    )
    risks = _join_labeled_fields(
        [
            ("main_risk", row.get("main_risk")),
            ("main_risks", row.get("main_risks")),
            ("downgrade_reasons", row.get("downgrade_reasons")),
            ("formalization_risk", formal.get("formalization_risk")),
        ]
    )
    source = _join_labeled_fields(
        [
            ("supporting_papers", row.get("supporting_papers")),
            ("source_verified_gaps", row.get("source_verified_gaps")),
            ("source_direct_formulations", row.get("source_direct_formulations")),
            ("source_grounding", formal.get("source_grounding")),
            ("formalization_confidence", formal.get("formalization_confidence")),
            ("requires_human_definition", formal.get("requires_human_definition")),
        ]
    )
    proposed = _join_labeled_fields(
        [
            ("research_object", row.get("research_object")),
            ("problem_class", row.get("problem_class")),
            ("assumption_shift", row.get("assumption_shift")),
            ("failure_boundary_or_mechanism", row.get("failure_boundary_or_mechanism")),
            ("plain_language_problem", formal.get("plain_language_problem")),
        ]
    )
    setup_text = _join_labeled_fields(
        [
            ("entities", setup.get("entities")),
            ("variables", setup.get("variables")),
            ("data_or_observations", setup.get("data_or_observations")),
            ("feedback_or_measurement_model", setup.get("feedback_or_measurement_model")),
            ("decision_variables_or_outputs", setup.get("decision_variables_or_outputs")),
            ("objective", setup.get("objective")),
            ("constraints", setup.get("constraints")),
            ("success_criterion", setup.get("success_criterion")),
            ("assumptions", assumptions),
        ]
    )
    return {
        "candidate_id": str(row.get("family_id") or row.get("candidate_id") or row.get("representative_variant_id")),
        "domain": "bandits",
        "title": _json_text(row.get("family_title") or row.get("representative_title") or row.get("title")),
        "problem_statement": _json_text(row.get("family_problem_statement") or row.get("representative_problem_statement") or row.get("problem_statement")),
        "motivation_or_abstract": _json_text(row.get("proposal_style_abstract") or row.get("abstract_or_motivation")),
        "proposed_direction": proposed,
        "expected_contribution": contribution,
        "evaluation_plan": evaluation,
        "risks_or_caveats": risks,
        "source_context_or_grounding": source,
        "formal_problem_statement": _json_text(formal.get("formal_problem_statement")),
        "assumptions_or_problem_setup": setup_text,
        "ambiguity_or_missing_definitions": _json_text(formal.get("ambiguity_flags")),
    }


def _normalize_sgha_direct(row: dict[str, Any]) -> dict[str, Any]:
    proposed = _join_labeled_fields(
        [
            ("core_setting", row.get("core_setting")),
            ("core_assumption_or_failure", row.get("core_assumption_or_failure")),
            ("core_objective", row.get("core_objective")),
        ]
    )
    contribution = _join_labeled_fields(
        [
            ("possible_theorem_target", row.get("possible_theorem_target")),
            ("possible_algorithmic_target", row.get("possible_algorithmic_target")),
            ("possible_empirical_target", row.get("possible_empirical_target")),
        ]
    )
    evaluation = _join_labeled_fields(
        [
            ("possible_theorem_target", row.get("possible_theorem_target")),
            ("possible_algorithmic_target", row.get("possible_algorithmic_target")),
            ("possible_empirical_target", row.get("possible_empirical_target")),
            ("falsification_condition", row.get("falsification_condition")),
            ("recommendation", row.get("recommendation")),
        ]
    )
    source = _join_labeled_fields(
        [
            ("supporting_papers", row.get("supporting_papers")),
            ("source_verified_gap_id", row.get("source_verified_gap_id")),
            ("verification_provenance", row.get("verification_provenance")),
            ("verification_agents_present", row.get("verification_agents_present")),
            ("traceability_path", row.get("traceability_path")),
        ]
    )
    setup = _join_labeled_fields(
        [
            ("core_setting", row.get("core_setting")),
            ("core_assumption_or_failure", row.get("core_assumption_or_failure")),
            ("core_objective", row.get("core_objective")),
            ("verification_summary", row.get("verification_summary")),
        ]
    )
    return {
        "candidate_id": str(row.get("formulation_id") or row.get("candidate_id")),
        "domain": "bandits",
        "title": _json_text(row.get("direct_title") or row.get("title")),
        "problem_statement": _json_text(row.get("direct_problem_statement") or row.get("problem_statement")),
        "motivation_or_abstract": _json_text(row.get("proposal_style_abstract") or row.get("motivation_or_abstract")),
        "proposed_direction": proposed,
        "expected_contribution": contribution,
        "evaluation_plan": evaluation,
        "risks_or_caveats": _json_text(row.get("main_risk")),
        "source_context_or_grounding": source,
        "formal_problem_statement": NOT_PROVIDED,
        "assumptions_or_problem_setup": setup,
        "ambiguity_or_missing_definitions": NOT_PROVIDED,
    }


def _normalize_sgha_ambition(row: dict[str, Any]) -> dict[str, Any]:
    proposed = _join_labeled_fields(
        [
            ("core_setting", row.get("core_setting")),
            ("broader_problem_class", row.get("broader_problem_class")),
            ("assumption_shift", row.get("assumption_shift")),
            ("boundary_or_failure_regime", row.get("boundary_or_failure_regime")),
            ("constructive_or_explanatory_target", row.get("constructive_or_explanatory_target")),
            ("why_not_just_validation", row.get("why_not_just_validation")),
        ]
    )
    contribution = _join_labeled_fields(
        [
            ("theorem_target", row.get("theorem_target")),
            ("algorithmic_target", row.get("algorithmic_target")),
            ("empirical_target", row.get("empirical_target")),
            ("contribution_type", row.get("contribution_type")),
            ("why_not_incremental", row.get("why_not_incremental")),
        ]
    )
    evaluation = _join_labeled_fields(
        [
            ("theorem_target", row.get("theorem_target")),
            ("algorithmic_target", row.get("algorithmic_target")),
            ("empirical_target", row.get("empirical_target")),
            ("falsification_condition", row.get("falsification_condition")),
        ]
    )
    risks = _join_labeled_fields(
        [
            ("main_risk", row.get("main_risk")),
            ("incrementality_risk", row.get("incrementality_risk")),
            ("critic_fake_ambition_risk", row.get("critic_fake_ambition_risk")),
            ("critic_reason", row.get("critic_reason")),
        ]
    )
    source = _join_labeled_fields(
        [
            ("supporting_papers", row.get("supporting_papers")),
            ("source_verified_gap_id", row.get("source_verified_gap_id")),
            ("source_formulation_id", row.get("source_formulation_id")),
            ("critic_supported_by_source", row.get("critic_supported_by_source")),
            ("traceability_path", row.get("traceability_path")),
        ]
    )
    setup = _join_labeled_fields(
        [
            ("core_setting", row.get("core_setting")),
            ("core_assumption_or_failure", row.get("core_assumption_or_failure")),
            ("core_objective", row.get("core_objective")),
            ("method_class_scope", row.get("method_class_scope")),
            ("named_method_dependency", row.get("named_method_dependency")),
        ]
    )
    return {
        "candidate_id": str(row.get("variant_id") or row.get("candidate_id")),
        "domain": "bandits",
        "title": _json_text(row.get("title")),
        "problem_statement": _json_text(row.get("problem_statement")),
        "motivation_or_abstract": _json_text(row.get("proposal_style_abstract")),
        "proposed_direction": proposed,
        "expected_contribution": contribution,
        "evaluation_plan": evaluation,
        "risks_or_caveats": risks,
        "source_context_or_grounding": source,
        "formal_problem_statement": NOT_PROVIDED,
        "assumptions_or_problem_setup": setup,
        "ambiguity_or_missing_definitions": NOT_PROVIDED,
    }


def _normalize_sgha_legacy_evolution(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": str(row.get("candidate_id") or row.get("hypothesis_id") or row.get("id")),
        "domain": "bandits",
        "title": _json_text(row.get("title")),
        "problem_statement": _json_text(row.get("problem_statement")),
        "motivation_or_abstract": _json_text(row.get("abstract_or_motivation") or row.get("motivation_or_abstract")),
        "proposed_direction": _json_text(row.get("proposed_direction")),
        "expected_contribution": _json_text(row.get("expected_contribution")),
        "evaluation_plan": _json_text(row.get("evaluation_or_validation_plan") or row.get("evaluation_plan")),
        "risks_or_caveats": _json_text(row.get("risks_or_caveats")),
        "source_context_or_grounding": _json_text(row.get("supporting_papers_or_context") or row.get("source_context_or_grounding")),
        "formal_problem_statement": _json_text(row.get("formal_problem_statement")),
        "assumptions_or_problem_setup": _json_text(row.get("assumptions_or_problem_setup")),
        "ambiguity_or_missing_definitions": _json_text(row.get("ambiguity_or_missing_definitions")),
    }


def _normalize_simple_or_rag_idea(row: dict[str, Any]) -> dict[str, Any]:
    source = _join_labeled_fields(
        [
            ("top_source_papers_or_context_items", row.get("top_source_papers_or_context_items")),
            ("retrieved_context_ids", row.get("retrieved_context_ids")),
            ("source_context_used", _safe_source_context(row.get("source_context_used"))),
        ]
    )
    return {
        "candidate_id": str(row.get("idea_id") or row.get("candidate_id")),
        "domain": "bandits",
        "title": _json_text(row.get("title")),
        "problem_statement": _json_text(row.get("problem_statement")),
        "motivation_or_abstract": _json_text(row.get("motivation")),
        "proposed_direction": _json_text(row.get("proposed_method_or_direction")),
        "expected_contribution": _json_text(row.get("expected_contribution")),
        "evaluation_plan": _json_text(row.get("evaluation_plan")),
        "risks_or_caveats": _json_text(row.get("risks_or_limitations")),
        "source_context_or_grounding": source,
        "formal_problem_statement": NOT_PROVIDED,
        "assumptions_or_problem_setup": NOT_PROVIDED,
        "ambiguity_or_missing_definitions": NOT_PROVIDED,
    }


def _normalize_native_ai_scientist_idea(row: dict[str, Any]) -> dict[str, Any]:
    source = _join_labeled_fields(
        [
            ("related_work", row.get("Related Work")),
            ("source_context_used", _safe_source_context(row.get("source_context_used"))),
        ]
    )
    return {
        "candidate_id": str(row.get("idea_id") or row.get("Name") or row.get("candidate_id")),
        "domain": "bandits",
        "title": _json_text(row.get("Title") or row.get("title")),
        "problem_statement": _json_text(row.get("Short Hypothesis") or row.get("problem_statement")),
        "motivation_or_abstract": _json_text(row.get("Abstract") or row.get("motivation")),
        "proposed_direction": _json_text(row.get("Abstract") or row.get("proposed_method_or_direction")),
        "expected_contribution": NOT_PROVIDED,
        "evaluation_plan": _json_text(row.get("Experiments") or row.get("evaluation_plan")),
        "risks_or_caveats": _json_text(row.get("Risk Factors and Limitations") or row.get("risks_or_limitations")),
        "source_context_or_grounding": source,
        "formal_problem_statement": NOT_PROVIDED,
        "assumptions_or_problem_setup": NOT_PROVIDED,
        "ambiguity_or_missing_definitions": NOT_PROVIDED,
    }


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise JudgeError(f"Required packet source not found: {path}")
    return read_jsonl(path)


def _ensure_common_schema(row: dict[str, Any]) -> dict[str, Any]:
    out = {key: _json_text(row.get(key)) for key in CALIBRATED_PACKET_FIELDS}
    out["domain"] = row.get("domain") or "bandits"
    return _sanitize_candidate_for_blinding(out)


def _packet_text_has_forbidden_method_labels(row: dict[str, Any]) -> list[str]:
    text = json.dumps(row, ensure_ascii=False)
    labels = labels_found_in_prompt(text)
    if re.search(r"(?<![A-Za-z0-9_\-])baselines?(?![A-Za-z0-9_\-])", text, re.IGNORECASE):
        labels.append("baseline")
    return sorted(set(labels))


def build_calibrated_bandits_packet(
    *,
    repair_namespace: Path,
    output_dir: Path,
    sgha_family_json: Path,
    random_seed: int = 20260721,
    num_per_method: int = 3,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_paths = {
        "SGHA_FULL": sgha_family_json,
        "SIMPLE_QWEN": repair_namespace / "baselines" / "simple_qwen" / "bandits" / "baseline_ideas.jsonl",
        "QWEN_RAG": repair_namespace / "baselines" / "qwen_rag" / "bandits" / "baseline_ideas.jsonl",
        "NATIVE_AI_SCIENTIST_V2": repair_namespace
        / "native_ai_scientist_v2_ideation_baseline"
        / "outputs"
        / "bandits"
        / "ai_scientist_native_ideas.jsonl",
    }
    sgha_rows = [_normalize_sgha_family(row) for row in _load_family_rows(source_paths["SGHA_FULL"])[:num_per_method]]
    simple_rows = [_normalize_simple_or_rag_idea(row) for row in _load_jsonl_rows(source_paths["SIMPLE_QWEN"])[:num_per_method]]
    rag_rows = [_normalize_simple_or_rag_idea(row) for row in _load_jsonl_rows(source_paths["QWEN_RAG"])[:num_per_method]]
    native_rows = [_normalize_native_ai_scientist_idea(row) for row in _load_jsonl_rows(source_paths["NATIVE_AI_SCIENTIST_V2"])[:num_per_method]]

    method_rows = {
        "SGHA_FULL": sgha_rows,
        "SIMPLE_QWEN": simple_rows,
        "QWEN_RAG": rag_rows,
        "NATIVE_AI_SCIENTIST_V2": native_rows,
    }
    for method, rows in method_rows.items():
        if len(rows) != num_per_method:
            raise JudgeError(f"Expected {num_per_method} rows for {method}, found {len(rows)}")

    unshuffled: list[tuple[str, dict[str, Any]]] = []
    for method, rows in method_rows.items():
        for row in rows:
            unshuffled.append((method, _ensure_common_schema(row)))

    rng = random.Random(random_seed)
    shuffled = list(unshuffled)
    rng.shuffle(shuffled)

    blinded_rows: list[dict[str, Any]] = []
    unblinded_rows: list[dict[str, Any]] = []
    blinding_key: list[dict[str, Any]] = []
    label_findings: list[dict[str, Any]] = []
    not_provided_counts: dict[str, int] = {}
    preserved = {
        "sgha_formal_problem_statement": 0,
        "sgha_source_grounding": 0,
        "sgha_ambiguity_flags": 0,
        "baseline_formal_not_provided": 0,
        "baseline_ambiguity_not_provided": 0,
    }
    for index, (method, row) in enumerate(shuffled, start=1):
        blinded_id = f"Candidate {index}"
        original_id = str(row["candidate_id"])
        blinded = dict(row)
        blinded["candidate_id"] = blinded_id
        labels = _packet_text_has_forbidden_method_labels(blinded)
        if labels:
            label_findings.append({"candidate_id": blinded_id, "labels": labels})
        blinded_rows.append(blinded)
        unblinded_rows.append(dict(blinded))
        blinding_key.append(
            {
                "blinded_candidate_id": blinded_id,
                "candidate_id": original_id,
                "method_hidden_label": method,
                "title": row.get("title"),
            }
        )
        for field in CALIBRATED_PACKET_FIELDS:
            if str(blinded.get(field, "")).strip().lower() == NOT_PROVIDED:
                not_provided_counts[field] = not_provided_counts.get(field, 0) + 1
        if method == "SGHA_FULL":
            if _field_is_provided(blinded.get("formal_problem_statement")):
                preserved["sgha_formal_problem_statement"] += 1
            if _field_is_provided(blinded.get("source_context_or_grounding")):
                preserved["sgha_source_grounding"] += 1
            if _field_is_provided(blinded.get("ambiguity_or_missing_definitions")):
                preserved["sgha_ambiguity_flags"] += 1
        else:
            if str(blinded.get("formal_problem_statement", "")).strip().lower() == NOT_PROVIDED:
                preserved["baseline_formal_not_provided"] += 1
            if str(blinded.get("ambiguity_or_missing_definitions", "")).strip().lower() == NOT_PROVIDED:
                preserved["baseline_ambiguity_not_provided"] += 1

    if label_findings:
        raise JudgeError(f"Blinded calibrated packet contains forbidden method labels: {label_findings}")

    write_jsonl(output_dir / "bandits_candidates_blinded.jsonl", blinded_rows)
    write_jsonl(output_dir / "bandits_candidates_unblinded.jsonl", unblinded_rows)
    (output_dir / "bandits_blinding_key.json").write_text(json.dumps(blinding_key, indent=2), encoding="utf-8")
    audit = {
        "created_at": utc_now_iso(),
        "repair_namespace": str(repair_namespace),
        "output_dir": str(output_dir),
        "random_seed": random_seed,
        "num_per_method": num_per_method,
        "candidate_count": len(blinded_rows),
        "source_paths": {key: str(value) for key, value in source_paths.items()},
        "method_counts": {method: len(rows) for method, rows in method_rows.items()},
        "common_schema_fields": list(CALIBRATED_PACKET_FIELDS),
        "not_provided_counts": not_provided_counts,
        "preservation_checks": preserved,
        "method_label_findings_in_blinded_packet": label_findings,
        "method_labels_stored_only_in_blinding_key": True,
    }
    (output_dir / "candidate_packet_build_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    lines = [
        "# Calibrated Bandits Candidate Packet Build Audit",
        "",
        f"- created_at: {audit['created_at']}",
        f"- candidate count: {len(blinded_rows)}",
        f"- random seed: {random_seed}",
        f"- forbidden method labels in blinded packet: {len(label_findings)}",
        f"- method labels stored only in blinding key: {audit['method_labels_stored_only_in_blinding_key']}",
        "",
        "## Method Counts",
        "",
    ]
    for method, count in audit["method_counts"].items():
        lines.append(f"- {method}: {count}")
    lines.extend(["", "## Preservation Checks", ""])
    for key, value in preserved.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Not Provided Counts", ""])
    for key in CALIBRATED_PACKET_FIELDS:
        lines.append(f"- {key}: {not_provided_counts.get(key, 0)}")
    lines.extend(["", "## Source Paths", ""])
    for key, value in audit["source_paths"].items():
        lines.append(f"- {key}: `{value}`")
    (output_dir / "candidate_packet_build_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return audit


def create_calibration_sentinels(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = [
        {
            "candidate_id": "sentinel_weak_generic",
            "domain": "calibration",
            "title": "Use machine learning to improve scientific discovery",
            "problem_statement": "Develop better ML methods for science by making them more robust and useful.",
            "motivation_or_abstract": "Many scientific problems are difficult, so better machine learning could help.",
            "proposed_direction": "Explore a broad framework for robust AI systems.",
            "expected_contribution": "A generally useful improvement.",
            "evaluation_plan": NOT_PROVIDED,
            "risks_or_caveats": "The direction is broad and underspecified.",
            "source_context_or_grounding": NOT_PROVIDED,
            "formal_problem_statement": NOT_PROVIDED,
            "assumptions_or_problem_setup": NOT_PROVIDED,
            "ambiguity_or_missing_definitions": "The task, variables, assumptions, objective, and evaluation plan are not defined.",
        },
        {
            "candidate_id": "sentinel_term_soup",
            "domain": "calibration",
            "title": "Causal Quantum Federated Diffusion Graph World Models for Fair Multimodal RL",
            "problem_statement": "Combine causal inference, quantum kernels, federated optimization, diffusion models, graph neural networks, world models, fairness, and multimodal reinforcement learning into one unified framework.",
            "motivation_or_abstract": "These topics are all important and appear in modern ML.",
            "proposed_direction": "Build an all-in-one model that handles every setting and proves broad generalization.",
            "expected_contribution": "A universal framework.",
            "evaluation_plan": "Try several datasets if available.",
            "risks_or_caveats": "The scope is overloaded.",
            "source_context_or_grounding": "Generic reference to modern ML topics.",
            "formal_problem_statement": NOT_PROVIDED,
            "assumptions_or_problem_setup": "Several unrelated settings are mentioned without a single formal setup.",
            "ambiguity_or_missing_definitions": "The variables, data model, objective, and measurement process are not coherent.",
            "term_soup_flag": True,
        },
        {
            "candidate_id": "sentinel_clear_incremental",
            "domain": "calibration",
            "title": "Apply a Standard Robust Estimator to Noisy Offline Policy Evaluation",
            "problem_statement": "Evaluate whether an existing robust mean estimator improves offline policy evaluation when rewards contain outliers.",
            "motivation_or_abstract": "Source item arxiv:2401.00001 ('Offline Policy Evaluation Under Heavy-Tailed Rewards') reports outlier-sensitive value estimates. Source item arxiv:2401.00002 ('Median-of-Means Estimation') gives a standard robust estimator.",
            "proposed_direction": "Adapt the standard estimator to the offline evaluation pipeline and compare it to ordinary averaging.",
            "expected_contribution": "A practical but mostly incremental robustness check.",
            "evaluation_plan": "Run benchmark comparisons across synthetic reward-noise settings and report estimation error.",
            "risks_or_caveats": "This may be an application of a known method rather than a new research problem.",
            "source_context_or_grounding": "arxiv:2401.00001: offline policy evaluation under heavy-tailed rewards; arxiv:2401.00002: median-of-means robust estimation. The candidate is grounded in these two provided source items but mostly applies an existing estimator to an existing evaluation setting.",
            "formal_problem_statement": "Let D be logged trajectories and r be noisy rewards; estimate V(pi) under outlier contamination.",
            "assumptions_or_problem_setup": "Assume logged trajectories are fixed and a fraction epsilon of rewards are contaminated.",
            "ambiguity_or_missing_definitions": "The contamination model and policy class need tightening.",
        },
        {
            "candidate_id": "sentinel_strong_grounded_formal",
            "domain": "calibration",
            "title": "Identifiability Boundary for Offline Evaluation Under Confounded Logging",
            "problem_statement": "Characterize when an offline policy value is identifiable from logged bandit data if the logging policy depends on an unobserved confounder that also affects rewards.",
            "motivation_or_abstract": "Source item arxiv:2402.10001 ('Logged Bandit Evaluation With Observed Propensities') gives consistent inverse-propensity estimators when behavior propensities are observed. Source item openreview:confounded-bandits-2025 ('Latent Confounding Breaks Off-Policy Evaluation') constructs indistinguishable logged datasets with different target-policy values. The provided gap is the exact boundary between identifiable and non-identifiable offline value estimation.",
            "proposed_direction": "Prove necessary and sufficient graphical or conditional-independence conditions for identifying V(pi), and derive a diagnostic test for violations.",
            "expected_contribution": "A sharp theorem separating identifiable from impossible offline evaluation regimes, plus a concrete diagnostic for source-paper follow-up.",
            "evaluation_plan": "Theorem: construct two latent-confounded environments P and Q with identical observed distribution over (X,A,Y) but different V(pi) when the graphical condition fails. Positive result: prove identifiability under the stated exclusion/overlap condition. Empirical check: simulate the two source-item environments and report diagnostic false-positive/false-negative rates.",
            "risks_or_caveats": "The graphical assumptions may be too strong for some applications.",
            "source_context_or_grounding": "Concrete source trail: arxiv:2402.10001 supports the observed-propensity reference estimator; openreview:confounded-bandits-2025 supports the latent-confounding failure mode; source_verified_gaps: gap:calibration_identifiability links those two source items to the proposed identifiability boundary.",
            "formal_problem_statement": "Let X be context, A an action, Y a reward, Z an unobserved confounder, pi_b(a|x,z) a logging policy, and pi(a|x) a target policy. Given n logged samples (X_i,A_i,Y_i) drawn from pi_b with Z unobserved, determine necessary and sufficient graphical/overlap conditions under which V(pi)=E[Y(pi(X))] is identifiable from the observed distribution P(X,A,Y).",
            "assumptions_or_problem_setup": "Observed variables are X,A,Y; latent variable Z affects both A and Y; pi_b may depend on (X,Z); pi depends only on X; rewards follow Y=f(X,A,Z,epsilon); overlap requires pi(a|x)>0 only where observed actions have support; objective is to identify V(pi) or prove non-identifiability.",
            "ambiguity_or_missing_definitions": "The exact graph family and overlap strength still need human choice, but variables, observation model, objective, and theorem target are explicit.",
        },
    ]
    expected = {
        "sentinel_weak_generic": {
            "max": {
                "evidence_auditability_reviewer.evidence_grounding_10": 4,
                "formalization_reviewer.formalizability_10": 5,
                "scientific_merit_reviewer.research_priority_10": 5,
            }
        },
        "sentinel_term_soup": {
            "max": {
                "evidence_auditability_reviewer.low_term_soup_10": 4,
                "scientific_merit_reviewer.clarity_specificity_10": 6,
                "scientific_merit_reviewer.research_priority_10": 6,
            }
        },
        "sentinel_clear_incremental": {
            "min": {
                "scientific_merit_reviewer.feasibility_10": 6,
                "scientific_merit_reviewer.actionability_10": 6,
            },
            "max": {
                "scientific_merit_reviewer.novelty_potential_10": 6,
                "scientific_merit_reviewer.research_priority_10": 7,
            },
        },
        "sentinel_strong_grounded_formal": {
            "min": {
                "evidence_auditability_reviewer.evidence_grounding_10": 7,
                "formalization_reviewer.formalizability_10": 7,
                "evidence_auditability_reviewer.auditability_10": 7,
                "scientific_merit_reviewer.research_priority_10": 7,
            }
        },
    }
    write_jsonl(output_dir / "calibration_candidates.jsonl", candidates)
    (output_dir / "expected_score_ranges.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    lines = [
        "# Calibration Sentinels",
        "",
        "These synthetic blinded candidates are for judge calibration only, not paper results.",
        "",
        "| candidate_id | intended behavior |",
        "|---|---|",
        "| sentinel_weak_generic | Should not receive high evidence, formalizability, or research-priority scores. |",
        "| sentinel_term_soup | Should be penalized for over-composition and weak priority. |",
        "| sentinel_clear_incremental | Should be feasible/actionable but not top-priority or highly novel. |",
        "| sentinel_strong_grounded_formal | Should score high on evidence, formalizability, auditability, and priority. |",
    ]
    (output_dir / "calibration_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "candidate_file": str(output_dir / "calibration_candidates.jsonl"),
        "expected_ranges": str(output_dir / "expected_score_ranges.json"),
        "candidate_count": len(candidates),
    }


def create_formulation_quality_calibration_sentinels(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = [
        {
            "candidate_id": "weak_generic_no_formalization",
            "domain": "calibration",
            "title": "Use Better Machine Learning for Science",
            "problem_statement": "Develop better machine learning systems for scientific discovery.",
            "motivation_or_abstract": "Science is hard and ML can help.",
            "proposed_direction": "Explore better models.",
            "expected_contribution": "A useful improvement.",
            "evaluation_plan": NOT_PROVIDED,
            "risks_or_caveats": "The direction is broad.",
            "source_context_or_grounding": NOT_PROVIDED,
            "formal_problem_statement": NOT_PROVIDED,
            "assumptions_or_problem_setup": NOT_PROVIDED,
            "ambiguity_or_missing_definitions": NOT_PROVIDED,
        },
        {
            "candidate_id": "polished_but_underformalized",
            "domain": "calibration",
            "title": "A Unified Framework for Adaptive Scientific Learning",
            "problem_statement": "This project proposes an elegant framework for adaptive learning systems that can transform scientific workflows by dynamically integrating evidence and uncertainty.",
            "motivation_or_abstract": "The proposal is fluent and appealing, but it does not define variables, assumptions, an objective, or a concrete observation model.",
            "proposed_direction": "Develop a general framework and demonstrate its usefulness.",
            "expected_contribution": "A broad conceptual contribution.",
            "evaluation_plan": "Evaluate on future benchmarks when available.",
            "risks_or_caveats": "The formulation may remain too abstract.",
            "source_context_or_grounding": "Generic reference to scientific workflows.",
            "formal_problem_statement": NOT_PROVIDED,
            "assumptions_or_problem_setup": NOT_PROVIDED,
            "ambiguity_or_missing_definitions": NOT_PROVIDED,
        },
        {
            "candidate_id": "term_soup_overcomposed",
            "domain": "calibration",
            "title": "Causal Federated Quantum Diffusion Graph World Models for Fair Multimodal Reinforcement Learning",
            "problem_statement": "Combine causal inference, federated learning, quantum kernels, diffusion models, graph neural networks, world models, fairness, multimodal reasoning, and reinforcement learning into a single framework.",
            "motivation_or_abstract": "All of these areas are important and could interact.",
            "proposed_direction": "Build one model that handles all settings.",
            "expected_contribution": "A universal framework.",
            "evaluation_plan": "Try several datasets.",
            "risks_or_caveats": "The scope is overloaded.",
            "source_context_or_grounding": "Generic reference to many modern ML topics.",
            "formal_problem_statement": NOT_PROVIDED,
            "assumptions_or_problem_setup": "Many settings are mentioned without one coherent setup.",
            "ambiguity_or_missing_definitions": "Variables, data model, objective, and measurement process are not coherent.",
        },
        {
            "candidate_id": "strong_formal_grounded_problem",
            "domain": "calibration",
            "title": "Identifiability Boundary for Offline Bandit Evaluation Under Latent Confounding",
            "problem_statement": "Characterize when a target policy value is identifiable from logged bandit data if the logging policy depends on an unobserved confounder that also affects rewards.",
            "motivation_or_abstract": "Source item arxiv:2402.10001 gives consistent inverse-propensity estimators with observed propensities. Source item openreview:confounded-bandits-2025 constructs indistinguishable logged datasets with different target-policy values under latent confounding.",
            "proposed_direction": "Prove necessary and sufficient graphical or conditional-independence conditions for identifying V(pi), and derive a diagnostic for violations.",
            "expected_contribution": "A theorem separating identifiable from non-identifiable offline evaluation regimes plus a concrete diagnostic.",
            "evaluation_plan": "Construct two latent-confounded environments P and Q with identical observed distribution over (X,A,Y) but different V(pi) when the condition fails; prove identifiability under the positive condition; simulate diagnostic error rates.",
            "risks_or_caveats": "The graph family and overlap condition may be too strong.",
            "source_context_or_grounding": "arxiv:2402.10001 supports the observed-propensity estimator; openreview:confounded-bandits-2025 supports the latent-confounding failure mode.",
            "formal_problem_statement": "Let X be context, A an action, Y a reward, Z an unobserved confounder, pi_b(a|x,z) a logging policy, and pi(a|x) a target policy. Given logged samples (X_i,A_i,Y_i), determine conditions under which V(pi)=E[Y(pi(X))] is identifiable from P(X,A,Y).",
            "assumptions_or_problem_setup": "Observed variables are X,A,Y; latent Z affects A and Y; pi_b may depend on X,Z; target pi depends on X; rewards follow Y=f(X,A,Z,epsilon); overlap constrains target actions to observed support.",
            "ambiguity_or_missing_definitions": "The graph family and overlap strength still need human choice, but variables, observation model, objective, and theorem target are explicit.",
        },
    ]
    expected = {
        "weak_generic_no_formalization": {
            "max": {
                "well_posedness_0_to_10": 4,
                "source_grounded_specificity_0_to_10": 4,
                "overall_formulation_quality_0_to_10": 5,
            }
        },
        "polished_but_underformalized": {
            "max": {
                "well_posedness_0_to_10": 6,
                "overall_formulation_quality_0_to_10": 6,
            }
        },
        "term_soup_overcomposed": {
            "max": {
                "scope_control_0_to_10": 4,
                "technical_sharpness_0_to_10": 5,
                "overall_formulation_quality_0_to_10": 6,
            }
        },
        "strong_formal_grounded_problem": {
            "min": {
                "well_posedness_0_to_10": 7,
                "technical_sharpness_0_to_10": 7,
                "source_grounded_specificity_0_to_10": 7,
                "overall_formulation_quality_0_to_10": 7,
            }
        },
    }
    write_jsonl(output_dir / "formulation_quality_sentinels.jsonl", candidates)
    (output_dir / "formulation_quality_expected_ranges.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    return {
        "candidate_file": str(output_dir / "formulation_quality_sentinels.jsonl"),
        "expected_ranges": str(output_dir / "formulation_quality_expected_ranges.json"),
        "candidate_count": len(candidates),
    }


def validate_formulation_quality_calibration(scores: list[dict[str, Any]], expected_ranges: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_id = {str(row.get("candidate_id")): row for row in scores}
    checks: list[dict[str, Any]] = []
    for candidate_id, rules in expected_ranges.items():
        row = rows_by_id.get(candidate_id)
        for kind, comparators in rules.items():
            if kind not in {"min", "max"} or not isinstance(comparators, dict):
                continue
            for key, expected in comparators.items():
                observed = row.get("scores", {}).get(key) if row else None
                if observed is None:
                    passed = False
                elif kind == "min":
                    passed = observed >= int(expected)
                else:
                    passed = observed <= int(expected)
                checks.append(
                    {
                        "candidate_id": candidate_id,
                        "criterion": key,
                        "check": kind,
                        "expected": int(expected),
                        "observed": observed,
                        "passed": passed,
                    }
                )
    return checks


def create_formulation_only_calibration_sentinels(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = [
        {
            "candidate_id": "vague_proposal_with_good_plan",
            "domain": "calibration",
            "title": "A Practical Benchmark Suite for Better Scientific Learning",
            "problem_statement": "Build a useful benchmark suite for improving scientific machine learning systems.",
            "motivation_or_abstract": "The candidate has a polished plan with datasets, leaderboards, and evaluation protocols, but it does not define a research problem, variables, assumptions, or a failure boundary.",
            "formal_problem_statement": NOT_PROVIDED,
            "assumptions_or_problem_setup": NOT_PROVIDED,
            "ambiguity_or_missing_definitions": "Scientific learning system, benchmark target, success metric, and problem class are undefined.",
            "source_context_or_grounding": "Generic context only; no concrete source paper or gap is named.",
        },
        {
            "candidate_id": "formal_but_unactionable_problem",
            "domain": "calibration",
            "title": "Identifiability of Policy Value Under Latent Logging Confounding",
            "problem_statement": "Determine when a target policy value is identifiable from logged bandit data when the logging policy depends on an unobserved confounder that also affects rewards.",
            "motivation_or_abstract": "The candidate is not a full project plan, but it is a clean research-problem formulation with explicit objects and a boundary question.",
            "formal_problem_statement": "Let X be context, A an observed action, Y a reward, Z an unobserved confounder, pi_b(a|x,z) a logging policy, and pi(a|x) a target policy. Given samples of (X,A,Y), characterize conditions under which V(pi)=E[Y(pi(X))] is identifiable from P(X,A,Y).",
            "assumptions_or_problem_setup": "Observed X,A,Y; latent Z affects A and Y; the target policy depends on X; candidate assumptions are graph restrictions and overlap.",
            "ambiguity_or_missing_definitions": "The graph family and overlap strength need human definition.",
            "source_context_or_grounding": "Source item A motivates standard observed-propensity off-policy evaluation; source item B motivates latent-confounding failure.",
        },
        {
            "candidate_id": "term_soup_formulation",
            "domain": "calibration",
            "title": "Causal Federated Quantum Diffusion Graph World Models for Fair Multimodal Reinforcement Learning",
            "problem_statement": "Unify causal inference, federated learning, quantum kernels, diffusion models, graph neural networks, world models, fairness, multimodal reasoning, and reinforcement learning into one formulation.",
            "motivation_or_abstract": "Many modern ML concepts are named, but the central object and problem boundary are unclear.",
            "formal_problem_statement": NOT_PROVIDED,
            "assumptions_or_problem_setup": "Many settings are mentioned without one coherent setup.",
            "ambiguity_or_missing_definitions": "Variables, data model, objective, measurement process, and relationships among concepts are undefined.",
            "source_context_or_grounding": "Generic references to modern ML topics; no concrete source trail.",
        },
        {
            "candidate_id": "strong_source_grounded_formulation",
            "domain": "calibration",
            "title": "Robust Regret Bounds for Heavy-Tailed Bandits With Unknown Tail Index",
            "problem_statement": "In stochastic multi-armed bandits with heavy-tailed rewards, characterize minimax regret when the learner does not know the tail index and cannot assume sub-Gaussian concentration.",
            "motivation_or_abstract": "Source paper A gives robust estimators under known moment assumptions, while source paper B shows sub-Gaussian UCB-style confidence intervals fail under heavy tails. The formulation isolates the missing adaptive-tail-index boundary.",
            "formal_problem_statement": "Let K arms have reward distributions P_i with finite (1+alpha)-moment for unknown alpha in (0,1]. A policy observes bandit feedback Y_t from chosen arm A_t. Characterize the minimax regret rate R_T over this distribution class and whether an adaptive policy can match the oracle-alpha rate without knowing alpha.",
            "assumptions_or_problem_setup": "Finite K, horizon T, stochastic bandit feedback, unknown tail index alpha, bounded (1+alpha)-moment constants, no sub-Gaussian tails.",
            "ambiguity_or_missing_definitions": "Moment constant knowledge and whether alpha is arm-specific need human definition.",
            "source_context_or_grounding": "source: paper-A on robust heavy-tailed estimators; source: paper-B on sub-Gaussian confidence failure; gap: adaptive minimax rate without known tail index.",
        },
    ]
    expected = {
        "vague_proposal_with_good_plan": {
            "max": {
                "problem_definition_clarity_10": 5,
                "well_posedness_10": 5,
                "overall_formulation_quality_10": 6,
            }
        },
        "formal_but_unactionable_problem": {
            "min": {
                "well_posedness_10": 7,
                "formalizability_10": 7,
                "overall_formulation_quality_10": 7,
            }
        },
        "term_soup_formulation": {
            "max": {
                "scope_control_10": 4,
                "technical_specificity_10": 5,
                "overall_formulation_quality_10": 6,
            }
        },
        "strong_source_grounded_formulation": {
            "min": {
                "problem_definition_clarity_10": 7,
                "assumption_boundary_clarity_10": 7,
                "source_grounded_specificity_10": 7,
                "overall_formulation_quality_10": 7,
            }
        },
    }
    write_jsonl(output_dir / "formulation_only_sentinels.jsonl", candidates)
    (output_dir / "expected_ranges.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    return {
        "candidate_file": str(output_dir / "formulation_only_sentinels.jsonl"),
        "expected_ranges": str(output_dir / "expected_ranges.json"),
        "candidate_count": len(candidates),
    }


def create_personalized_calibration_sentinels(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_context = (
        "Profile: Example researcher. Artifact-supported themes: probabilistic graphical models, "
        "variational inference, Bayesian nonparametrics, and optimization. Seed titles include "
        "An Introduction to Variational Methods for Graphical Models and Hierarchical Dirichlet Processes. "
        "The profile context is primarily theory/statistical ML."
    )
    candidates = [
        {
            "candidate_id": "generic_good_ml_problem_for_profile",
            "domain": "calibration",
            "profile": "Example Researcher",
            "profile_context": profile_context,
            "title": "Better Benchmarks for Robust Machine Learning",
            "problem_statement": "Construct a benchmark for robust machine learning algorithms under distribution shift.",
            "motivation_or_abstract": "The idea is technically coherent and plausible but could apply to many ML researchers.",
            "formal_problem_statement": "Let D_train and D_test be distributions and evaluate algorithms under distribution shift.",
            "assumptions_or_problem_setup": "Supervised learning with train/test shift and a fixed benchmark suite.",
            "ambiguity_or_missing_definitions": "Robustness metric and shift family need definition.",
            "source_context_or_grounding": "Generic ML context; no profile-specific source trail.",
            "supporting_papers": "not provided",
            "profile_alignment_evidence": "generic; could apply to many researchers and is not profile-specific.",
        },
        {
            "candidate_id": "name_dropping_off_profile_problem",
            "domain": "calibration",
            "profile": "Example Researcher",
            "profile_context": profile_context,
            "title": "Variational Quantum Vision Transformers for Robotics",
            "problem_statement": "Use the profile's name to motivate a robotics vision-transformer system with quantum optimization.",
            "motivation_or_abstract": "The text name-drops variational ideas but does not connect to the provided profile themes.",
            "formal_problem_statement": "not provided",
            "assumptions_or_problem_setup": "not provided",
            "ambiguity_or_missing_definitions": "Robotics task, quantum component, data, objective, and profile connection are undefined.",
            "source_context_or_grounding": "not provided",
            "supporting_papers": "not provided",
            "profile_alignment_evidence": "name-dropping; off-profile relative to provided context.",
        },
        {
            "candidate_id": "profile_aligned_but_vague_problem",
            "domain": "calibration",
            "profile": "Example Researcher",
            "profile_context": profile_context,
            "title": "Rethinking Variational Inference for Modern Models",
            "problem_statement": "Study how variational inference should change for modern probabilistic models.",
            "motivation_or_abstract": "The topic aligns with the profile context, but the problem is broad and lacks a precise setting.",
            "formal_problem_statement": "not provided",
            "assumptions_or_problem_setup": "not provided",
            "ambiguity_or_missing_definitions": "Model class, variational family, objective, observations, and success criterion are undefined.",
            "source_context_or_grounding": "Profile context mentions variational methods and graphical models.",
            "supporting_papers": "An Introduction to Variational Methods for Graphical Models",
            "profile_alignment_evidence": "Matches provided profile themes of variational inference and graphical models.",
        },
        {
            "candidate_id": "strong_profile_aligned_formulation",
            "domain": "calibration",
            "profile": "Example Researcher",
            "profile_context": profile_context,
            "title": "Identifiability Boundaries for Hierarchical Variational Topic Models",
            "problem_statement": "In hierarchical topic models, characterize when a variational approximation preserves identifiable latent topic structure versus collapsing distinct hierarchy levels.",
            "motivation_or_abstract": "The provided profile context includes variational graphical models, hierarchical Bayesian models, and topic models. The candidate narrows these themes into a concrete identifiability boundary question.",
            "formal_problem_statement": "Let documents x_1:n be generated by a hierarchical latent topic model with latent tree z and variational family q_phi(z). Characterize conditions on the hierarchy, likelihood, and variational family under which optimizing ELBO(q_phi) identifies the same latent hierarchy as maximum likelihood up to label symmetries.",
            "assumptions_or_problem_setup": "Observed documents, latent hierarchical topics, variational family restrictions, ELBO objective, and identifiability up to label symmetry.",
            "ambiguity_or_missing_definitions": "Exact hierarchy class, separability assumptions, and acceptable equivalence relation need human definition.",
            "source_context_or_grounding": "Seed themes: variational methods for graphical models, hierarchical Dirichlet processes, latent Dirichlet allocation.",
            "supporting_papers": "An Introduction to Variational Methods for Graphical Models; Hierarchical Dirichlet Processes; Latent Dirichlet Allocation",
            "profile_alignment_evidence": "Directly connects the provided profile's variational inference, graphical models, Bayesian nonparametrics, and topic-model themes to a new formal identifiability problem.",
        },
    ]
    expected = {
        "generic_good_ml_problem_for_profile": {
            "max": {
                "profile_specificity_10": 5,
                "personalization_overall_10": 6,
            }
        },
        "name_dropping_off_profile_problem": {
            "max": {
                "profile_alignment_10": 5,
                "personalization_overall_10": 5,
            }
        },
        "profile_aligned_but_vague_problem": {
            "min": {
                "profile_alignment_10": 6,
            },
            "max": {
                "overall_formulation_quality_10": 6,
            },
        },
        "strong_profile_aligned_formulation": {
            "min": {
                "profile_alignment_10": 7,
                "profile_specificity_10": 7,
                "overall_formulation_quality_10": 7,
                "personalization_overall_10": 7,
            }
        },
    }
    write_jsonl(output_dir / "personalized_sentinels.jsonl", candidates)
    (output_dir / "expected_ranges.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    return {
        "candidate_file": str(output_dir / "personalized_sentinels.jsonl"),
        "expected_ranges": str(output_dir / "expected_ranges.json"),
        "candidate_count": len(candidates),
    }


def _formulation_only_average(row: dict[str, Any]) -> float:
    scores = row.get("scores", {})
    values = [scores.get(key) for key in FORMULATION_ONLY_CRITERIA]
    numeric = [float(value) for value in values if isinstance(value, int) and not isinstance(value, bool)]
    return sum(numeric) / len(numeric) if numeric else 0.0


def _formulation_only_all_high_count(scores: list[dict[str, Any]], threshold: int = 8) -> int:
    count = 0
    for row in scores:
        values = [
            value
            for value in row.get("scores", {}).values()
            if isinstance(value, int) and not isinstance(value, bool)
        ]
        if values and all(value >= threshold for value in values):
            count += 1
    return count


def validate_formulation_only_calibration(scores: list[dict[str, Any]], expected_ranges: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_id = {str(row.get("candidate_id")): row for row in scores}
    checks: list[dict[str, Any]] = []
    for candidate_id, rules in expected_ranges.items():
        row = rows_by_id.get(candidate_id)
        for kind, comparators in rules.items():
            if kind not in {"min", "max"} or not isinstance(comparators, dict):
                continue
            for key, expected in comparators.items():
                observed = row.get("scores", {}).get(key) if row else None
                if observed is None:
                    passed = False
                elif kind == "min":
                    passed = observed >= int(expected)
                else:
                    passed = observed <= int(expected)
                checks.append(
                    {
                        "candidate_id": candidate_id,
                        "criterion": key,
                        "check": kind,
                        "expected": int(expected),
                        "observed": observed,
                        "passed": passed,
                    }
                )
    formal = rows_by_id.get("formal_but_unactionable_problem")
    vague = rows_by_id.get("vague_proposal_with_good_plan")
    soup = rows_by_id.get("term_soup_formulation")
    strong = rows_by_id.get("strong_source_grounded_formulation")
    checks.append(
        {
            "candidate_id": "relative_ordering",
            "criterion": "average_score",
            "check": "formal_but_unactionable_beats_vague_with_good_plan",
            "expected": "formal_but_unactionable_problem > vague_proposal_with_good_plan",
            "observed": {"formal": _formulation_only_average(formal or {}), "vague": _formulation_only_average(vague or {})},
            "passed": bool(formal and vague and _formulation_only_average(formal) > _formulation_only_average(vague)),
        }
    )
    checks.append(
        {
            "candidate_id": "relative_ordering",
            "criterion": "scope_control_10",
            "check": "term_soup_penalized",
            "expected": "term_soup_formulation scope_control_10 <= 4",
            "observed": soup.get("scores", {}).get("scope_control_10") if soup else None,
            "passed": bool(soup and soup.get("scores", {}).get("scope_control_10", 10) <= 4),
        }
    )
    checks.append(
        {
            "candidate_id": "relative_ordering",
            "criterion": "average_score",
            "check": "strong_source_grounded_scores_high",
            "expected": "strong_source_grounded_formulation >= 7 average",
            "observed": _formulation_only_average(strong or {}),
            "passed": bool(strong and _formulation_only_average(strong) >= 7),
        }
    )
    checks.append(
        {
            "candidate_id": "ceiling_check",
            "criterion": "all_high_count",
            "check": "no_batchwide_all_high_ceiling",
            "expected": f"< {len(scores)}",
            "observed": _formulation_only_all_high_count(scores),
            "passed": _formulation_only_all_high_count(scores) < len(scores),
        }
    )
    return checks


def _personalized_average(row: dict[str, Any], keys: tuple[str, ...] = PERSONALIZED_FORMULATION_CRITERIA) -> float:
    scores = row.get("scores", {})
    values = [scores.get(key) for key in keys]
    numeric = [float(value) for value in values if isinstance(value, int) and not isinstance(value, bool)]
    return sum(numeric) / len(numeric) if numeric else 0.0


def validate_personalized_calibration(scores: list[dict[str, Any]], expected_ranges: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_id = {str(row.get("candidate_id")): row for row in scores}
    checks: list[dict[str, Any]] = []
    for candidate_id, rules in expected_ranges.items():
        row = rows_by_id.get(candidate_id)
        for kind, comparators in rules.items():
            if kind not in {"min", "max"} or not isinstance(comparators, dict):
                continue
            for key, expected in comparators.items():
                observed = row.get("scores", {}).get(key) if row else None
                if observed is None:
                    passed = False
                elif kind == "min":
                    passed = observed >= int(expected)
                else:
                    passed = observed <= int(expected)
                checks.append(
                    {
                        "candidate_id": candidate_id,
                        "criterion": key,
                        "check": kind,
                        "expected": int(expected),
                        "observed": observed,
                        "passed": passed,
                    }
                )
    generic = rows_by_id.get("generic_good_ml_problem_for_profile")
    name_drop = rows_by_id.get("name_dropping_off_profile_problem")
    aligned_vague = rows_by_id.get("profile_aligned_but_vague_problem")
    strong = rows_by_id.get("strong_profile_aligned_formulation")
    checks.append(
        {
            "candidate_id": "relative_ordering",
            "criterion": "personalization_overall_10",
            "check": "strong_profile_aligned_beats_generic_good",
            "expected": "strong_profile_aligned_formulation > generic_good_ml_problem_for_profile",
            "observed": {
                "strong": strong.get("scores", {}).get("personalization_overall_10") if strong else None,
                "generic": generic.get("scores", {}).get("personalization_overall_10") if generic else None,
            },
            "passed": bool(strong and generic and strong.get("scores", {}).get("personalization_overall_10", -1) > generic.get("scores", {}).get("personalization_overall_10", 10)),
        }
    )
    checks.append(
        {
            "candidate_id": "relative_ordering",
            "criterion": "personalization_overall_10",
            "check": "name_dropping_off_profile_penalized",
            "expected": "name_dropping_off_profile_problem personalization_overall_10 <= 5",
            "observed": name_drop.get("scores", {}).get("personalization_overall_10") if name_drop else None,
            "passed": bool(name_drop and name_drop.get("scores", {}).get("personalization_overall_10", 10) <= 5),
        }
    )
    checks.append(
        {
            "candidate_id": "relative_ordering",
            "criterion": "alignment_vs_formulation",
            "check": "profile_aligned_but_vague_alignment_exceeds_formulation",
            "expected": "profile_alignment_10 > overall_formulation_quality_10",
            "observed": {
                "profile_alignment_10": aligned_vague.get("scores", {}).get("profile_alignment_10") if aligned_vague else None,
                "overall_formulation_quality_10": aligned_vague.get("scores", {}).get("overall_formulation_quality_10") if aligned_vague else None,
            },
            "passed": bool(aligned_vague and aligned_vague.get("scores", {}).get("profile_alignment_10", -1) > aligned_vague.get("scores", {}).get("overall_formulation_quality_10", 10)),
        }
    )
    checks.append(
        {
            "candidate_id": "ceiling_check",
            "criterion": "all_high_count",
            "check": "no_all_high_ceiling",
            "expected": f"< {len(scores)}",
            "observed": _formulation_only_all_high_count(scores),
            "passed": _formulation_only_all_high_count(scores) < len(scores),
        }
    )
    checks.append(
        {
            "candidate_id": "cap_check",
            "criterion": "cap_violations",
            "check": "no_major_cap_violations",
            "expected": 0,
            "observed": sum(len(row.get("cap_violations", [])) for row in scores),
            "passed": sum(len(row.get("cap_violations", [])) for row in scores) == 0,
        }
    )
    return checks


def create_prism_idea_quality_calibration_sentinels(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = [
        {
            "candidate_id": "weak_generic_idea",
            "domain": "calibration",
            "title": "Use AI to Improve Scientific Discovery",
            "problem_statement": "AI could help scientists discover new things faster.",
            "motivation_or_abstract": "Scientific discovery is important and AI is powerful.",
            "proposed_direction": "Develop a general AI system for better science.",
            "expected_contribution": "Better scientific results.",
            "evaluation_plan": NOT_PROVIDED,
            "risks_or_caveats": "The idea is very broad.",
            "source_context_or_grounding": NOT_PROVIDED,
            "formal_problem_statement": NOT_PROVIDED,
            "assumptions_or_problem_setup": NOT_PROVIDED,
            "ambiguity_or_missing_definitions": "The scientific domain, task, metrics, and evidence trail are undefined.",
        },
        {
            "candidate_id": "feasible_incremental_idea",
            "domain": "calibration",
            "title": "Benchmark Existing Robust Bandit Algorithms Under Mild Reward Noise",
            "problem_statement": "Compare three known robust bandit algorithms on a small suite of stochastic reward distributions with slightly heavier tails than the original papers considered.",
            "motivation_or_abstract": "The provided context mentions robust bandits and heavy-tailed rewards. A modest benchmark could clarify when existing algorithms degrade.",
            "proposed_direction": "Run a controlled empirical benchmark using existing implementations and report regret curves as tail parameters vary.",
            "expected_contribution": "A useful but incremental empirical comparison.",
            "evaluation_plan": "Implement the algorithms, sweep tail parameters, and compare regret and confidence interval coverage.",
            "risks_or_caveats": "This is likely incremental unless it reveals a sharper boundary or motivates a new estimator.",
            "source_context_or_grounding": "Grounded in the provided robust-bandit/heavy-tail context, but not tied to a precise verified gap.",
            "formal_problem_statement": NOT_PROVIDED,
            "assumptions_or_problem_setup": "Finite-arm stochastic bandit, known algorithm set, controlled reward distributions.",
            "ambiguity_or_missing_definitions": "The exact benchmark distributions and algorithms need to be specified.",
        },
        {
            "candidate_id": "term_soup_idea",
            "domain": "calibration",
            "title": "Causal Federated Quantum Diffusion Bandits With Conformal World Models",
            "problem_statement": "Unify causal inference, federated learning, quantum optimization, diffusion policies, conformal prediction, and world models for bandit reasoning.",
            "motivation_or_abstract": "Many modern ML ideas are important and could interact.",
            "proposed_direction": "Create a universal framework combining these tools.",
            "expected_contribution": "A broad new paradigm.",
            "evaluation_plan": "Try many datasets and prove many theorems.",
            "risks_or_caveats": "The concepts are loosely connected and the scope is uncontrolled.",
            "source_context_or_grounding": "Mentions several terms but does not tie them to concrete source evidence.",
            "formal_problem_statement": NOT_PROVIDED,
            "assumptions_or_problem_setup": NOT_PROVIDED,
            "ambiguity_or_missing_definitions": "Most core terms and relationships are undefined.",
        },
        {
            "candidate_id": "strong_grounded_research_problem",
            "domain": "calibration",
            "title": "Identifiability Limits for Off-Policy Bandit Evaluation With Latent Confounding",
            "problem_statement": "In logged contextual bandit data, standard off-policy evaluation assumes the logging policy is conditionally independent of latent reward confounders. The problem is to characterize when the target policy value is identifiable from observed logs when that assumption fails.",
            "motivation_or_abstract": "The provided context includes source papers on off-policy bandit evaluation and latent-confounding failures. The proposal narrows this into an identifiability question with a clear failure boundary.",
            "proposed_direction": "Define a causal bandit data-generating process, prove necessary/sufficient identifiability conditions under observed covariates and overlap, and derive a diagnostic for non-identifiable regimes.",
            "expected_contribution": "A source-grounded theoretical boundary plus an actionable diagnostic for when off-policy estimates should not be trusted.",
            "evaluation_plan": "Prove identifiability/lower-bound results, then simulate confounded logging policies to test whether the diagnostic predicts estimator failure.",
            "risks_or_caveats": "The exact causal graph family and overlap assumptions require human definition; the result may be negative for broad graph classes.",
            "source_context_or_grounding": "source: paper-A on off-policy bandit evaluation; source: paper-B on latent confounding; gap: independence assumption fails under unobserved confounders.",
            "formal_problem_statement": "Let X be context, A action, Y reward, Z latent confounder, pi_b(a|x,z) logging policy, and pi(a|x) target policy. Given n samples of (X,A,Y), determine when V(pi)=E[Y(pi(X))] is identifiable from P(X,A,Y).",
            "assumptions_or_problem_setup": "Observed X,A,Y; latent Z affects A and Y; target policy depends on X; overlap and graph restrictions are candidate assumptions.",
            "ambiguity_or_missing_definitions": "Graph family, overlap strength, and target policy class need explicit selection.",
        },
    ]
    expected = {
        "weak_generic_idea": {
            "max": {
                "novelty_originality_10": 4,
                "groundedness_10": 4,
                "traceability_auditability_10": 4,
            },
            "action_not": ["READ_FIRST"],
        },
        "feasible_incremental_idea": {
            "min": {
                "feasibility_10": 6,
                "actionability_10": 6,
            },
            "max": {
                "novelty_originality_10": 6,
            },
            "action_in": ["PROMISING_NEEDS_REFINEMENT", "NEEDS_REFRAMING"],
        },
        "term_soup_idea": {
            "max": {
                "clarity_coherence_10": 5,
                "non_redundancy_scope_control_10": 4,
            },
            "action_not": ["READ_FIRST"],
        },
        "strong_grounded_research_problem": {
            "min": {
                "clarity_coherence_10": 6,
                "groundedness_10": 6,
                "traceability_auditability_10": 6,
                "potential_impact_10": 6,
            },
            "action_in": ["READ_FIRST", "PROMISING_NEEDS_REFINEMENT"],
        },
    }
    write_jsonl(output_dir / "prism_idea_quality_sentinels.jsonl", candidates)
    (output_dir / "prism_idea_quality_expected_ranges.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    (output_dir / "README.md").write_text(
        "# PRISM / LiveIdeaBench-Style Calibration Sentinels\n\n"
        "These synthetic sentinels calibrate idea-quality scoring with relative ordering checks and a few broad range checks.\n",
        encoding="utf-8",
    )
    return {
        "candidate_file": str(output_dir / "prism_idea_quality_sentinels.jsonl"),
        "expected_ranges": str(output_dir / "prism_idea_quality_expected_ranges.json"),
        "candidate_count": len(candidates),
    }


def _prism_average(row: dict[str, Any]) -> float:
    scores = row.get("scores", {})
    values = [scores.get(key) for key in PRISM_IDEA_QUALITY_CRITERIA]
    numeric = [float(value) for value in values if isinstance(value, int) and not isinstance(value, bool)]
    return sum(numeric) / len(numeric) if numeric else 0.0


def validate_prism_idea_quality_calibration(scores: list[dict[str, Any]], expected_ranges: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_id = {str(row.get("candidate_id")): row for row in scores}
    checks: list[dict[str, Any]] = []
    for candidate_id, rules in expected_ranges.items():
        row = rows_by_id.get(candidate_id)
        for kind, comparators in rules.items():
            if kind in {"min", "max"} and isinstance(comparators, dict):
                for key, expected in comparators.items():
                    observed = row.get("scores", {}).get(key) if row else None
                    if observed is None:
                        passed = False
                    elif kind == "min":
                        passed = observed >= int(expected)
                    else:
                        passed = observed <= int(expected)
                    checks.append(
                        {
                            "candidate_id": candidate_id,
                            "criterion": key,
                            "check": kind,
                            "expected": int(expected),
                            "observed": observed,
                            "passed": passed,
                        }
                    )
            elif kind == "action_in":
                observed = row.get("recommended_action") if row else None
                checks.append(
                    {
                        "candidate_id": candidate_id,
                        "criterion": "recommended_action",
                        "check": "in",
                        "expected": comparators,
                        "observed": observed,
                        "passed": observed in set(comparators or []),
                    }
                )
            elif kind == "action_not":
                observed = row.get("recommended_action") if row else None
                checks.append(
                    {
                        "candidate_id": candidate_id,
                        "criterion": "recommended_action",
                        "check": "not_in",
                        "expected": comparators,
                        "observed": observed,
                        "passed": observed not in set(comparators or []),
                    }
                )

    strong = rows_by_id.get("strong_grounded_research_problem")
    weak = rows_by_id.get("weak_generic_idea")
    soup = rows_by_id.get("term_soup_idea")
    incremental = rows_by_id.get("feasible_incremental_idea")
    checks.append(
        {
            "candidate_id": "relative_ordering",
            "criterion": "average_score",
            "check": "strong_gt_weak",
            "expected": "strong_grounded_research_problem > weak_generic_idea",
            "observed": {"strong": _prism_average(strong or {}), "weak": _prism_average(weak or {})},
            "passed": bool(strong and weak and _prism_average(strong) > _prism_average(weak)),
        }
    )
    checks.append(
        {
            "candidate_id": "relative_ordering",
            "criterion": "average_score",
            "check": "strong_gt_term_soup",
            "expected": "strong_grounded_research_problem > term_soup_idea",
            "observed": {"strong": _prism_average(strong or {}), "term_soup": _prism_average(soup or {})},
            "passed": bool(strong and soup and _prism_average(strong) > _prism_average(soup)),
        }
    )
    checks.append(
        {
            "candidate_id": "relative_ordering",
            "criterion": "non_redundancy_scope_control_10",
            "check": "term_soup_scope_penalized_vs_strong",
            "expected": "term_soup_idea < strong_grounded_research_problem",
            "observed": {
                "term_soup": soup.get("scores", {}).get("non_redundancy_scope_control_10") if soup else None,
                "strong": strong.get("scores", {}).get("non_redundancy_scope_control_10") if strong else None,
            },
            "passed": bool(
                soup
                and strong
                and soup.get("scores", {}).get("non_redundancy_scope_control_10", 0)
                < strong.get("scores", {}).get("non_redundancy_scope_control_10", 0)
            ),
        }
    )
    checks.append(
        {
            "candidate_id": "relative_ordering",
            "criterion": "novelty_originality_10",
            "check": "feasible_incremental_not_high_novelty",
            "expected": "feasible_incremental_idea novelty <= strong_grounded_research_problem novelty",
            "observed": {
                "incremental": incremental.get("scores", {}).get("novelty_originality_10") if incremental else None,
                "strong": strong.get("scores", {}).get("novelty_originality_10") if strong else None,
            },
            "passed": bool(
                incremental
                and strong
                and incremental.get("scores", {}).get("novelty_originality_10", 10)
                <= strong.get("scores", {}).get("novelty_originality_10", 0)
            ),
        }
    )
    return checks


def _role_score_value(row: dict[str, Any], dotted: str) -> int | None:
    role_id, score_key = dotted.split(".", 1)
    value = row.get("role_scores", {}).get(role_id, {}).get(score_key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def validate_expected_score_ranges(scores: list[dict[str, Any]], expected_ranges: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_id = {str(row.get("candidate_id")): row for row in scores}
    checks: list[dict[str, Any]] = []
    for candidate_id, rules in expected_ranges.items():
        row = rows_by_id.get(candidate_id)
        for kind, comparators in rules.items():
            if kind not in {"min", "max"} or not isinstance(comparators, dict):
                continue
            for dotted_key, expected in comparators.items():
                observed = _role_score_value(row or {}, dotted_key) if row else None
                if observed is None:
                    passed = False
                elif kind == "min":
                    passed = observed >= int(expected)
                else:
                    passed = observed <= int(expected)
                checks.append(
                    {
                        "candidate_id": candidate_id,
                        "criterion": dotted_key,
                        "check": kind,
                        "expected": int(expected),
                        "observed": observed,
                        "passed": passed,
                    }
                )
    return checks


def _all_high_role_score_count(scores: list[dict[str, Any]], threshold: int = 8) -> int:
    count = 0
    for row in scores:
        values = [
            value
            for role_record in row.get("role_scores", {}).values()
            for key, value in role_record.items()
            if key.endswith("_10") and isinstance(value, int)
        ]
        if values and all(value >= threshold for value in values):
            count += 1
    return count


def write_calibration_live_report(output_dir: Path) -> dict[str, Any]:
    scores = read_jsonl(output_dir / "scores_blinded.jsonl") if (output_dir / "scores_blinded.jsonl").exists() else []
    parse_errors = read_jsonl(output_dir / "parse_errors.jsonl") if (output_dir / "parse_errors.jsonl").exists() else []
    metadata = json.loads((output_dir / "judge_run_metadata.json").read_text(encoding="utf-8")) if (output_dir / "judge_run_metadata.json").exists() else {}
    expected_path = output_dir / "expected_score_ranges.json"
    if not expected_path.exists():
        raise JudgeError(f"Missing expected score ranges: {expected_path}")
    expected_ranges = json.loads(expected_path.read_text(encoding="utf-8"))
    checks = validate_expected_score_ranges(scores, expected_ranges)
    cap_violation_count = sum(len(row.get("cap_violations", [])) for row in scores)
    invalid_role_count = sum(len(row.get("invalid_roles", [])) for row in scores)
    all_high_count = _all_high_role_score_count(scores)
    expected_pass = all(row["passed"] for row in checks)
    calibration_passed = bool(scores) and len(scores) == 4 and not parse_errors and cap_violation_count == 0 and invalid_role_count == 0 and expected_pass and all_high_count == 0
    report = {
        "calibration_passed": calibration_passed,
        "model": metadata.get("model"),
        "candidate_count": len(scores),
        "parse_error_count": len(parse_errors),
        "cap_violation_count": cap_violation_count,
        "invalid_role_count": invalid_role_count,
        "all_high_candidate_count": all_high_count,
        "expected_range_checks": checks,
    }
    (output_dir / "calibration_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Calibration Live Report",
        "",
        f"- model: `{metadata.get('model')}`",
        f"- candidates scored: {len(scores)}",
        f"- parse errors: {len(parse_errors)}",
        f"- cap violations: {cap_violation_count}",
        f"- invalid roles: {invalid_role_count}",
        f"- all-high ceiling candidates: {all_high_count}",
        f"- expected ranges passed: {expected_pass}",
        f"- calibration passed: {calibration_passed}",
        "",
        "## Expected Range Checks",
        "",
        "| candidate | criterion | check | expected | observed | passed |",
        "|---|---|---|---:|---:|---|",
    ]
    for check in checks:
        lines.append(
            f"| {check['candidate_id']} | {check['criterion']} | {check['check']} | {check['expected']} | {check['observed']} | {check['passed']} |"
        )
    lines.extend(["", "## Notes", "", "- No weighted composite score was computed.", "- No pairwise preference was requested.", "- These sentinels are synthetic calibration inputs only."])
    (output_dir / "CALIBRATION_LIVE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_role_based_all_domain_candidate_packets(
    *,
    config: dict[str, Any] | None = None,
    config_path: Path | None = None,
    repair_namespace: Path,
    output_dir: Path,
    random_seed: int = 20260722,
    num_per_method: int | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir = output_dir / "candidate_packets"
    dry_run_dir = output_dir / "dry_run"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    dry_run_dir.mkdir(parents=True, exist_ok=True)
    pool_rows, source_paths = _load_four_way_method_candidates(repair_namespace)
    selected: list[dict[str, Any]] = []
    count_audit: list[dict[str, Any]] = []
    count_errors: list[dict[str, Any]] = []
    for domain in FOUR_WAY_DOMAINS:
        expected = OUTPUT_MATCHED_COUNTS_BY_DOMAIN[domain]
        for method in FOUR_WAY_METHODS:
            pool = [row for row in pool_rows if row.get("domain") == domain and row.get("method") == method]
            source_path = source_paths.get(f"{domain}::{method}")
            count_audit.append(
                {
                    "domain": domain,
                    "method": method,
                    "expected": expected,
                    "available": len(pool),
                    "selected": len(pool) if len(pool) == expected else 0,
                    "source_path": str(source_path) if source_path else "missing",
                    "selected_candidate_ids": [str(row.get("candidate_id")) for row in pool] if len(pool) == expected else [],
                }
            )
            if len(pool) != expected:
                count_errors.append(
                    {
                        "domain": domain,
                        "method": method,
                        "expected": expected,
                        "available": len(pool),
                        "missing": max(expected - len(pool), 0),
                        "extra": max(len(pool) - expected, 0),
                        "source_path": str(source_path) if source_path else "missing",
                    }
                )
            else:
                selected.extend(pool)
    if count_errors:
        details = "; ".join(
            f"{row['domain']}/{row['method']}: expected {row['expected']}, available {row['available']}, source {row['source_path']}"
            for row in count_errors
        )
        raise JudgeError(f"All-candidate packet count validation failed: {details}")

    rng = random.Random(random_seed)
    shuffled = list(selected)
    rng.shuffle(shuffled)
    blinded_rows: list[dict[str, Any]] = []
    unblinded_rows: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    label_findings: list[dict[str, Any]] = []
    not_provided_counts: dict[str, int] = {}
    preservation_checks = {
        "sgha_formal_problem_statement": 0,
        "sgha_source_grounding": 0,
        "sgha_ambiguity_flags": 0,
        "baseline_formal_not_provided": 0,
        "baseline_assumptions_not_provided": 0,
        "baseline_ambiguity_not_provided": 0,
    }
    for index, row in enumerate(shuffled, start=1):
        blinded_id = f"Candidate {index:03d}"
        blinded = {key: row.get(key, NOT_PROVIDED) for key in CALIBRATED_PACKET_FIELDS}
        blinded["candidate_id"] = blinded_id
        blinded["domain"] = row.get("domain")
        blinded = _sanitize_candidate_for_blinding(blinded)
        labels = _packet_text_has_forbidden_method_labels(blinded)
        if labels:
            label_findings.append({"candidate_id": blinded_id, "labels": labels})
        blinded_rows.append(blinded)
        unblinded = {key: row.get(key, NOT_PROVIDED) for key in CALIBRATED_PACKET_FIELDS}
        unblinded["candidate_id"] = row.get("candidate_id")
        unblinded["blinded_candidate_id"] = blinded_id
        unblinded["domain"] = row.get("domain")
        unblinded["method"] = row.get("method")
        unblinded_rows.append(unblinded)
        key_rows.append(
            {
                "blinded_candidate_id": blinded_id,
                "candidate_id": row.get("candidate_id"),
                "method_hidden_label": row.get("method"),
                "domain": row.get("domain"),
                "title": row.get("title"),
            }
        )
        for field in CALIBRATED_PACKET_FIELDS:
            if str(blinded.get(field, "")).strip().lower() == NOT_PROVIDED:
                not_provided_counts[field] = not_provided_counts.get(field, 0) + 1
        if row.get("method") == "SGHA_FULL":
            if _field_is_provided(blinded.get("formal_problem_statement")):
                preservation_checks["sgha_formal_problem_statement"] += 1
            if _field_is_provided(blinded.get("source_context_or_grounding")):
                preservation_checks["sgha_source_grounding"] += 1
            if _field_is_provided(blinded.get("ambiguity_or_missing_definitions")):
                preservation_checks["sgha_ambiguity_flags"] += 1
        else:
            if str(blinded.get("formal_problem_statement", "")).strip().lower() == NOT_PROVIDED:
                preservation_checks["baseline_formal_not_provided"] += 1
            if str(blinded.get("assumptions_or_problem_setup", "")).strip().lower() == NOT_PROVIDED:
                preservation_checks["baseline_assumptions_not_provided"] += 1
            if str(blinded.get("ambiguity_or_missing_definitions", "")).strip().lower() == NOT_PROVIDED:
                preservation_checks["baseline_ambiguity_not_provided"] += 1
    if label_findings:
        raise JudgeError(f"Role-based all-domain blinded packet contains forbidden method labels: {label_findings[:5]}")

    write_jsonl(candidate_dir / "all_candidates_blinded.jsonl", blinded_rows)
    write_jsonl(candidate_dir / "all_candidates_unblinded.jsonl", unblinded_rows)
    (candidate_dir / "blinding_key.json").write_text(json.dumps(key_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    method_counts = {method: sum(1 for row in selected if row.get("method") == method) for method in FOUR_WAY_METHODS}
    domain_counts = {domain: sum(1 for row in selected if row.get("domain") == domain) for domain in FOUR_WAY_DOMAINS}
    domain_method_counts = {
        f"{domain}::{method}": sum(1 for row in selected if row.get("domain") == domain and row.get("method") == method)
        for domain in FOUR_WAY_DOMAINS
        for method in FOUR_WAY_METHODS
    }
    expected_total = sum(OUTPUT_MATCHED_COUNTS_BY_DOMAIN.values()) * len(FOUR_WAY_METHODS)
    expected_method_total = sum(OUTPUT_MATCHED_COUNTS_BY_DOMAIN.values())
    audit = {
        "created_at": utc_now_iso(),
        "repair_namespace": str(repair_namespace),
        "output_dir": str(output_dir),
        "candidate_packet_dir": str(candidate_dir),
        "random_seed": random_seed,
        "deprecated_num_per_method_argument_ignored": num_per_method,
        "domains": list(FOUR_WAY_DOMAINS),
        "methods": list(FOUR_WAY_METHODS),
        "expected_counts_by_domain_per_method": dict(OUTPUT_MATCHED_COUNTS_BY_DOMAIN),
        "expected_candidates_per_method": expected_method_total,
        "expected_candidate_count": expected_total,
        "candidate_count": len(blinded_rows),
        "candidate_count_matches_expected": len(blinded_rows) == expected_total,
        "method_counts": method_counts,
        "method_counts_match_expected": all(count == expected_method_total for count in method_counts.values()),
        "domain_counts": domain_counts,
        "domain_counts_match_expected": all(domain_counts[domain] == OUTPUT_MATCHED_COUNTS_BY_DOMAIN[domain] * len(FOUR_WAY_METHODS) for domain in FOUR_WAY_DOMAINS),
        "domain_method_counts": domain_method_counts,
        "count_audit": count_audit,
        "source_paths": {key: str(value) for key, value in source_paths.items()},
        "common_schema_fields": list(CALIBRATED_PACKET_FIELDS),
        "not_provided_counts": not_provided_counts,
        "preservation_checks": preservation_checks,
        "method_label_findings_in_blinded_packet": label_findings,
        "method_labels_stored_only_in_blinding_key": True,
        "pairwise_comparison": False,
        "weighted_composite_score": False,
        "real_candidate_scoring_run": False,
    }
    (candidate_dir / "candidate_packet_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    lines = [
        "# All-Candidate Packet Audit",
        "",
        f"- candidate count: {len(blinded_rows)}",
        f"- expected candidate count: {audit['expected_candidate_count']}",
        f"- candidate count matches expected: {audit['candidate_count_matches_expected']}",
        f"- candidates per method expected: {expected_method_total}",
        f"- method counts match expected: {audit['method_counts_match_expected']}",
        f"- domain counts match expected: {audit['domain_counts_match_expected']}",
        f"- method labels in blinded packet: {len(label_findings)}",
        f"- method labels stored only in blinding key: {audit['method_labels_stored_only_in_blinding_key']}",
        f"- pairwise comparison: False",
        f"- weighted composite score: False",
        f"- live scoring run: False",
        "",
        "## Counts By Method",
        "",
        "| method | expected | selected |",
        "|---|---:|---:|",
    ]
    for method in FOUR_WAY_METHODS:
        lines.append(f"| {method} | {expected_method_total} | {method_counts[method]} |")
    lines.extend(
        [
            "",
            "## Counts By Domain",
            "",
            "| domain | expected | selected |",
            "|---|---:|---:|",
        ]
    )
    for domain in FOUR_WAY_DOMAINS:
        lines.append(f"| {domain} | {OUTPUT_MATCHED_COUNTS_BY_DOMAIN[domain] * len(FOUR_WAY_METHODS)} | {domain_counts[domain]} |")
    lines.extend(
        [
            "",
            "## Counts By Domain And Method",
            "",
            "| domain | method | expected | available | selected | source path |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for row in count_audit:
        lines.append(
            f"| {row['domain']} | {row['method']} | {row['expected']} | {row['available']} | {row['selected']} | `{row['source_path']}` |"
        )
    lines.extend(["", "## Preservation Checks", ""])
    for key, value in preservation_checks.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Missing-Field Counts", ""])
    for key in CALIBRATED_PACKET_FIELDS:
        lines.append(f"- {key}: {not_provided_counts.get(key, 0)}")
    (candidate_dir / "candidate_packet_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    dry_run_result: dict[str, Any] | None = None
    if config is not None and config_path is not None:
        dry_run_result = run_role_based_scoring(
            config=config,
            config_path=config_path,
            candidate_file=candidate_dir / "all_candidates_blinded.jsonl",
            output_dir=dry_run_dir,
            run_name="all_candidates_role_based_10pt_dry_run",
            domain=None,
            dry_run=True,
            no_network=True,
            force=True,
        )
        _write_all_candidate_dry_run_validation_report(
            dry_run_dir / "dry_run_validation_report.md",
            audit=audit,
            dry_run_result=dry_run_result,
            config=config,
        )

    _write_all_candidate_packet_report(output_dir / "ALL_CANDIDATE_PACKET_REPORT.md", audit=audit, dry_run_result=dry_run_result)
    _write_role_based_live_commands(
        output_dir / "RUN_LIVE_ROLE_BASED_JUDGE_COMMANDS.md",
        packet_dir=output_dir,
        candidate_file=candidate_dir / "all_candidates_blinded.jsonl",
    )
    _write_role_based_aggregation_plan(output_dir / "AGGREGATION_PLAN.md", audit=audit)
    return audit


def _write_all_candidate_dry_run_validation_report(
    path: Path,
    *,
    audit: dict[str, Any],
    dry_run_result: dict[str, Any],
    config: dict[str, Any],
) -> None:
    metadata = dry_run_result.get("metadata", {})
    manifest = dry_run_result.get("manifest", {})
    candidates_parse = metadata.get("mode") == "dry_run" and metadata.get("network_used") is False
    cap_rules_available = bool(config.get("evaluation", {}).get("enforce_cap_rules", False))
    labels_hidden = not audit.get("method_label_findings_in_blinded_packet")
    no_weighted = bool(manifest.get("no_weighted_composite")) and metadata.get("weighted_composite_computed") is False
    no_pairwise = manifest.get("pairwise_preferences_requested") is False and metadata.get("pairwise_enabled") is False
    lines = [
        "# Dry-Run Validation Report",
        "",
        f"- scoring mode: `{metadata.get('scoring_mode')}`",
        f"- configured model: `{metadata.get('model')}`",
        f"- dry-run network used: {metadata.get('network_used')}",
        f"- candidates parsed/planned: {manifest.get('planned_candidate_count')}",
        f"- roles planned: {len(manifest.get('roles', []))}",
        f"- role calls planned: {manifest.get('planned_role_count')}",
        f"- method labels hidden in prompts: {labels_hidden}",
        f"- blinding key read during scoring dry-run: {manifest.get('blinding_key_read_during_scoring')}",
        f"- cap validation rules available: {cap_rules_available}",
        f"- no weighted composite: {no_weighted}",
        f"- pairwise disabled: {no_pairwise}",
        f"- all 60 candidates parse: {candidates_parse and manifest.get('planned_candidate_count') == 60}",
        "",
        "## Notes",
        "",
        "- This was a no-network prompt/packet validation run only.",
        "- The blinding key remains outside the dry-run scoring directory.",
        "- No OpenRouter calls, pairwise comparisons, or weighted composite scores were run.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_all_candidate_packet_report(path: Path, *, audit: dict[str, Any], dry_run_result: dict[str, Any] | None) -> None:
    ready = (
        bool(audit.get("candidate_count_matches_expected"))
        and bool(audit.get("method_counts_match_expected"))
        and bool(audit.get("domain_counts_match_expected"))
        and not audit.get("method_label_findings_in_blinded_packet")
        and (dry_run_result is not None)
    )
    dry_manifest = dry_run_result.get("manifest", {}) if dry_run_result else {}
    lines = [
        "# All-Candidate Role-Based Judge Packet Report",
        "",
        f"- packet directory: `{audit.get('output_dir')}`",
        f"- candidate packet directory: `{audit.get('candidate_packet_dir')}`",
        f"- total candidates: {audit.get('candidate_count')}",
        f"- expected candidates: {audit.get('expected_candidate_count')}",
        f"- ready for live scoring: {ready}",
        f"- live scoring run: False",
        f"- pairwise comparison: False",
        f"- weighted composite score: False",
        "",
        "## Candidates Per Method",
        "",
        "| method | candidates |",
        "|---|---:|",
    ]
    for method in FOUR_WAY_METHODS:
        lines.append(f"| {method} | {audit.get('method_counts', {}).get(method, 0)} |")
    lines.extend(
        [
            "",
            "## Candidates Per Domain",
            "",
            "| domain | candidates |",
            "|---|---:|",
        ]
    )
    for domain in FOUR_WAY_DOMAINS:
        lines.append(f"| {domain} | {audit.get('domain_counts', {}).get(domain, 0)} |")
    lines.extend(
        [
            "",
            "## Packet Files",
            "",
            "- `candidate_packets/all_candidates_unblinded.jsonl`",
            "- `candidate_packets/all_candidates_blinded.jsonl`",
            "- `candidate_packets/blinding_key.json`",
            "- `candidate_packets/candidate_packet_audit.md`",
            "",
            "## Dry-Run Validation",
            "",
            f"- dry-run candidate count: {dry_manifest.get('planned_candidate_count', 'not run')}",
            f"- dry-run role calls planned: {dry_manifest.get('planned_role_count', 'not run')}",
            f"- blinding key read during scoring dry-run: {dry_manifest.get('blinding_key_read_during_scoring', 'not run')}",
            f"- method label findings in prompts: {len(dry_manifest.get('method_label_findings_in_prompts', [])) if dry_manifest else 'not run'}",
            "",
            "## Source Paths",
            "",
        ]
    )
    for key, value in audit.get("source_paths", {}).items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_role_based_live_commands(path: Path, *, packet_dir: Path, candidate_file: Path) -> None:
    live_dir = packet_dir / "live_role_based_results"
    key_source = packet_dir / "candidate_packets" / "blinding_key.json"
    key_dest = live_dir / "all_candidates_blinding_key.json"
    repo_root = Path(__file__).resolve().parents[1]
    lines = [
        "# Run Live Role-Based Judge Commands",
        "",
        "Run these only after deciding to launch the live OpenRouter evaluation.",
        "",
        "```bash",
        f"cd {repo_root}",
        "# Optional: source a local file that exports OPENROUTER_API_KEY.",
        f"mkdir -p {live_dir}",
        f"cp {key_source} {key_dest}",
        "python scripts/run_llm_judge_openrouter.py \\",
        "  --config configs/judging/openrouter_llm_judge.yaml \\",
        f"  --candidate-file {candidate_file} \\",
        f"  --output-dir {live_dir} \\",
        "  --run-name all_domains_role_based_10pt \\",
        "  --scoring-mode role_based_10pt \\",
        "  --resume",
        "```",
        "",
        "Then postprocess/unblind after live scoring completes:",
        "",
        "```bash",
        f"cd {repo_root}",
        "python scripts/run_llm_judge_openrouter.py \\",
        "  --config configs/judging/openrouter_llm_judge.yaml \\",
        f"  --output-dir {live_dir} \\",
        "  --postprocess-unblind",
        "```",
        "",
        "No pairwise preference or weighted composite score is part of this command sequence.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_role_based_aggregation_plan(path: Path, *, audit: dict[str, Any]) -> None:
    lines = [
        "# Aggregation Plan",
        "",
        "This plan is for post-scoring descriptive analysis of the all-candidate role-based judge outputs.",
        "",
        "## Aggregates",
        "",
        "- Micro-average over all candidates by method: average each criterion across the 15 candidates per method.",
        "- Macro-average over domains by method: average per-domain method means so the 6-candidate uncertainty domain does not dominate.",
        "- Per-role scores: report scientific merit, formalization, and evidence/auditability role criteria separately.",
        "- Method means and standard errors: report mean and standard error for each criterion, method, and role.",
        "- Domain-normalized means: treat each domain as one unit before averaging across domains.",
        "",
        "## Constraints",
        "",
        "- Do not compute a weighted composite score.",
        "- Do not run or report pairwise preference as part of this primary evaluation.",
        "- Treat results as descriptive, not statistically significant.",
        "",
        "## Candidate Counts",
        "",
        "| domain | candidates per method | total candidates |",
        "|---|---:|---:|",
    ]
    for domain in FOUR_WAY_DOMAINS:
        per_method = OUTPUT_MATCHED_COUNTS_BY_DOMAIN[domain]
        lines.append(f"| {domain} | {per_method} | {per_method * len(FOUR_WAY_METHODS)} |")
    lines.extend(["", "## Method Totals", ""])
    for method in FOUR_WAY_METHODS:
        lines.append(f"- {method}: {audit.get('method_counts', {}).get(method, 0)} candidates")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ensure_pairwise_pool_schema(row: dict[str, Any], source_pool: str) -> dict[str, Any]:
    out = {key: _json_text(row.get(key)) for key in CALIBRATED_PACKET_FIELDS}
    out["domain"] = row.get("domain") or "bandits"
    out["source_pool"] = source_pool
    return out


def _selection_score(row: dict[str, Any]) -> float:
    score = 0.0
    for field, weight in (
        ("problem_statement", 4.0),
        ("evaluation_plan", 3.0),
        ("source_context_or_grounding", 3.0),
        ("formal_problem_statement", 2.0),
        ("assumptions_or_problem_setup", 1.5),
        ("risks_or_caveats", 1.0),
    ):
        if _field_is_provided(row.get(field)):
            score += weight
    text = json.dumps(row, ensure_ascii=False).lower()
    if "read_first" in text or "strong_candidate" in text:
        score += 4.0
    if "drop" in text or "deprioritize" in text:
        score -= 5.0
    for key in ("coherence_score", "specificity_score", "feasibility_score", "ambition_score"):
        try:
            score += float(row.get(key, 0))
        except (TypeError, ValueError):
            pass
    grand_terms = len(re.findall(r"\b(fundamental|phase transition|impossibility|boundary|robust|causal|unified|framework)\b", text))
    if grand_terms > 14:
        score -= 1.5
    if len(text) > 16000:
        score -= 1.0
    return score


def _select_pool_candidates(rows: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    if len(rows) <= limit:
        return rows
    ranked = sorted(
        enumerate(rows),
        key=lambda item: (
            -_selection_score(item[1]),
            str(item[1].get("title", "")),
            item[0],
        ),
    )
    selected: list[dict[str, Any]] = []
    seen_title_roots: set[str] = set()
    for _, row in ranked:
        root = re.sub(r"[^a-z0-9]+", " ", str(row.get("title", "")).lower()).strip()[:80]
        if root and root in seen_title_roots and len(selected) < len(ranked) - 1:
            continue
        selected.append(row)
        if root:
            seen_title_roots.add(root)
        if len(selected) == limit:
            return selected
    return [row for _, row in ranked[:limit]]


def _strip_pairwise_blinded_candidate(row: dict[str, Any], blinded_id: str) -> dict[str, Any]:
    blinded = {key: row.get(key, NOT_PROVIDED) for key in CALIBRATED_PACKET_FIELDS}
    blinded["candidate_id"] = blinded_id
    return _sanitize_candidate_for_blinding(blinded)


def _write_pool_summary(path: Path, pool_rows: dict[str, list[dict[str, Any]]], source_paths: dict[str, Path]) -> None:
    lines = [
        "# Bandits Pairwise Candidate Pool Summary",
        "",
        "| source pool | candidates | source path |",
        "|---|---:|---|",
    ]
    for pool in PAIRWISE_SOURCE_POOLS:
        if pool not in pool_rows:
            continue
        lines.append(f"| {pool} | {len(pool_rows[pool])} | `{source_paths.get(pool, Path('missing'))}` |")
    lines.extend(["", "## Notes", "", "- Missing fields are recorded as `not provided`.", "- Method labels are retained only in unblinded pool files and blinding keys, not in judge packets."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_selection_audit(path: Path, selected: dict[str, list[dict[str, Any]]], pool_rows: dict[str, list[dict[str, Any]]]) -> None:
    lines = [
        "# Bandits Pairwise Selection Audit",
        "",
        "Selection used deterministic metadata and completeness heuristics only; no LLM selected candidates.",
        "",
        "| source pool | available | selected | selected candidate IDs |",
        "|---|---:|---:|---|",
    ]
    for pool in PAIRWISE_SOURCE_POOLS:
        if pool not in pool_rows:
            continue
        ids = "; ".join(str(row.get("candidate_id")) for row in selected.get(pool, []))
        lines.append(f"| {pool} | {len(pool_rows[pool])} | {len(selected.get(pool, []))} | {ids} |")
    lines.extend(
        [
            "",
            "## Heuristic",
            "",
            "Candidates were ranked by presence of a nonempty problem statement, evaluation plan, source/context grounding, formal fields, assumptions/setup, risks/caveats, available internal quality labels/scores, and a light penalty for very overloaded wording.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_best_bandits_pairwise_trial(
    *,
    repair_namespace: Path,
    output_dir: Path,
    sgha_bandits_run_dir: Path,
    random_seed: int = 20260721,
    num_per_pool: int = 3,
    include_legacy: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_pools_dir = output_dir / "candidate_pools"
    selected_dir = output_dir / "selected_candidates"
    packets_dir = output_dir / "pairwise_packets"
    results_dir = output_dir / "pairwise_results"
    for path in (candidate_pools_dir, selected_dir, packets_dir, results_dir):
        path.mkdir(parents=True, exist_ok=True)

    source_paths = {
        "SGHA_FINAL_FAMILY": sgha_bandits_run_dir / "final_sgha_family_report" / "final_project_families.json",
        "SGHA_DIRECT": sgha_bandits_run_dir / "stage7_direct_formulations" / "direct_formulations.jsonl",
        "SGHA_AMBITION_FINAL": sgha_bandits_run_dir / "stage8_ambition_expansion" / "ambition_expanded_final_formulations.jsonl",
        "SIMPLE_QWEN": repair_namespace / "baselines" / "simple_qwen" / "bandits" / "baseline_ideas.jsonl",
        "QWEN_RAG": repair_namespace / "baselines" / "qwen_rag" / "bandits" / "baseline_ideas.jsonl",
        "NATIVE_AI_SCIENTIST_V2": repair_namespace / "native_ai_scientist_v2_ideation_baseline" / "outputs" / "bandits" / "ai_scientist_native_ideas.jsonl",
        "SGHA_LEGACY_EVOLUTION": sgha_bandits_run_dir / "comparisons" / "normalized" / "sgha_evolution_candidates.jsonl",
    }

    pool_rows: dict[str, list[dict[str, Any]]] = {
        "SGHA_FINAL_FAMILY": [_ensure_pairwise_pool_schema(_normalize_sgha_family(row), "SGHA_FINAL_FAMILY") for row in _load_family_rows(source_paths["SGHA_FINAL_FAMILY"])],
        "SGHA_DIRECT": [_ensure_pairwise_pool_schema(_normalize_sgha_direct(row), "SGHA_DIRECT") for row in _load_jsonl_rows(source_paths["SGHA_DIRECT"])],
        "SGHA_AMBITION_FINAL": [_ensure_pairwise_pool_schema(_normalize_sgha_ambition(row), "SGHA_AMBITION_FINAL") for row in _load_jsonl_rows(source_paths["SGHA_AMBITION_FINAL"])],
        "SIMPLE_QWEN": [_ensure_pairwise_pool_schema(_normalize_simple_or_rag_idea(row), "SIMPLE_QWEN") for row in _load_jsonl_rows(source_paths["SIMPLE_QWEN"])],
        "QWEN_RAG": [_ensure_pairwise_pool_schema(_normalize_simple_or_rag_idea(row), "QWEN_RAG") for row in _load_jsonl_rows(source_paths["QWEN_RAG"])],
        "NATIVE_AI_SCIENTIST_V2": [_ensure_pairwise_pool_schema(_normalize_native_ai_scientist_idea(row), "NATIVE_AI_SCIENTIST_V2") for row in _load_jsonl_rows(source_paths["NATIVE_AI_SCIENTIST_V2"])],
    }
    legacy_status = "not_requested"
    if include_legacy:
        legacy_path = source_paths["SGHA_LEGACY_EVOLUTION"]
        if legacy_path.exists():
            pool_rows["SGHA_LEGACY_EVOLUTION"] = [
                _ensure_pairwise_pool_schema(_normalize_sgha_legacy_evolution(row), "SGHA_LEGACY_EVOLUTION")
                for row in _load_jsonl_rows(legacy_path)
            ]
            legacy_status = "included"
        else:
            legacy_status = f"missing: {legacy_path}"

    all_rows: list[dict[str, Any]] = []
    for pool in PAIRWISE_SOURCE_POOLS:
        for row in pool_rows.get(pool, []):
            all_rows.append(row)
    write_jsonl(candidate_pools_dir / "bandits_all_candidates_unblinded.jsonl", all_rows)
    _write_pool_summary(candidate_pools_dir / "bandits_candidate_pool_summary.md", pool_rows, source_paths)

    selected: dict[str, list[dict[str, Any]]] = {
        pool: _select_pool_candidates(rows, limit=num_per_pool)
        for pool, rows in pool_rows.items()
    }
    selected_rows = [row for pool in PAIRWISE_SOURCE_POOLS for row in selected.get(pool, [])]
    write_jsonl(selected_dir / "bandits_selected_candidates_unblinded.jsonl", selected_rows)
    _write_selection_audit(selected_dir / "selection_audit.md", selected, pool_rows)

    comparisons: list[tuple[str, dict[str, Any], dict[str, Any], str]] = []
    final_rows = selected.get("SGHA_FINAL_FAMILY", [])
    for target_pool in ("SIMPLE_QWEN", "QWEN_RAG", "NATIVE_AI_SCIENTIST_V2"):
        for family in final_rows:
            for other in selected.get(target_pool, []):
                comparisons.append((f"SGHA_FINAL_FAMILY_vs_{target_pool}", family, other, "primary"))
    for target_pool in ("SGHA_DIRECT", "SGHA_AMBITION_FINAL"):
        for family in final_rows:
            for other in selected.get(target_pool, []):
                comparisons.append((f"SGHA_FINAL_FAMILY_vs_{target_pool}", family, other, "secondary"))
    if "SGHA_LEGACY_EVOLUTION" in selected:
        for family in final_rows:
            for other in selected.get("SGHA_LEGACY_EVOLUTION", []):
                comparisons.append(("SGHA_FINAL_FAMILY_vs_SGHA_LEGACY_EVOLUTION", family, other, "optional_legacy"))

    rng = random.Random(random_seed)
    schedule_rows: list[dict[str, Any]] = []
    blinded_rows: list[dict[str, Any]] = []
    blinding_key: list[dict[str, Any]] = []
    label_findings: list[dict[str, Any]] = []
    for index, (comparison_group, left, right, comparison_type) in enumerate(comparisons, start=1):
        pair_id = f"bandits_pair_{index:03d}"
        swap = rng.random() < 0.5
        side_a = right if swap else left
        side_b = left if swap else right
        blinded_a = _strip_pairwise_blinded_candidate(side_a, "Candidate A")
        blinded_b = _strip_pairwise_blinded_candidate(side_b, "Candidate B")
        for side_label, blinded in (("A", blinded_a), ("B", blinded_b)):
            labels = _packet_text_has_forbidden_method_labels(blinded)
            if labels:
                label_findings.append({"pair_id": pair_id, "side": side_label, "labels": labels})
        schedule_rows.append(
            {
                "pair_id": pair_id,
                "domain": "bandits",
                "comparison_group": comparison_group,
                "comparison_type": comparison_type,
                "left_pool": left.get("source_pool"),
                "left_candidate_id": left.get("candidate_id"),
                "right_pool": right.get("source_pool"),
                "right_candidate_id": right.get("candidate_id"),
                "candidate_a_pool": side_a.get("source_pool"),
                "candidate_a_id": side_a.get("candidate_id"),
                "candidate_b_pool": side_b.get("source_pool"),
                "candidate_b_id": side_b.get("candidate_id"),
                "ab_order_swapped": swap,
            }
        )
        blinded_rows.append({"pair_id": pair_id, "domain": "bandits", "candidate_a": blinded_a, "candidate_b": blinded_b})
        blinding_key.append(
            {
                "pair_id": pair_id,
                "comparison_group": comparison_group,
                "comparison_type": comparison_type,
                "left_pool": left.get("source_pool"),
                "left_candidate_id": left.get("candidate_id"),
                "left_title": left.get("title"),
                "right_pool": right.get("source_pool"),
                "right_candidate_id": right.get("candidate_id"),
                "right_title": right.get("title"),
                "candidate_a_pool": side_a.get("source_pool"),
                "candidate_a_original_id": side_a.get("candidate_id"),
                "candidate_a_title": side_a.get("title"),
                "candidate_b_pool": side_b.get("source_pool"),
                "candidate_b_original_id": side_b.get("candidate_id"),
                "candidate_b_title": side_b.get("title"),
                "ab_order_swapped": swap,
            }
        )
    if label_findings:
        raise JudgeError(f"Blinded pairwise packet contains forbidden method labels: {label_findings[:5]}")

    write_jsonl(packets_dir / "pairwise_schedule_unblinded.jsonl", schedule_rows)
    write_jsonl(packets_dir / "pairwise_pairs_blinded.jsonl", blinded_rows)
    (packets_dir / "pairwise_blinding_key.json").write_text(json.dumps(blinding_key, indent=2), encoding="utf-8")
    audit = {
        "created_at": utc_now_iso(),
        "repair_namespace": str(repair_namespace),
        "sgha_bandits_run_dir": str(sgha_bandits_run_dir),
        "output_dir": str(output_dir),
        "random_seed": random_seed,
        "num_per_pool": num_per_pool,
        "legacy_status": legacy_status,
        "pool_counts": {pool: len(rows) for pool, rows in pool_rows.items()},
        "selected_counts": {pool: len(rows) for pool, rows in selected.items()},
        "pair_count": len(blinded_rows),
        "comparison_group_counts": {group: sum(1 for row in schedule_rows if row["comparison_group"] == group) for group in sorted({row["comparison_group"] for row in schedule_rows})},
        "method_label_findings_in_blinded_packet": label_findings,
        "a_b_order_randomized": any(row["ab_order_swapped"] for row in schedule_rows) and any(not row["ab_order_swapped"] for row in schedule_rows),
        "source_paths": {key: str(value) for key, value in source_paths.items()},
    }
    (packets_dir / "pairwise_packet_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    lines = [
        "# Pairwise Packet Audit",
        "",
        f"- created_at: {audit['created_at']}",
        f"- pair count: {audit['pair_count']}",
        f"- random seed: {random_seed}",
        f"- A/B order randomized: {audit['a_b_order_randomized']}",
        f"- forbidden method labels in blinded packet: {len(label_findings)}",
        f"- legacy evolution: {legacy_status}",
        "",
        "## Selected Counts",
        "",
    ]
    for pool, count in audit["selected_counts"].items():
        lines.append(f"- {pool}: {count}")
    lines.extend(["", "## Comparison Groups", ""])
    for group, count in audit["comparison_group_counts"].items():
        lines.append(f"- {group}: {count}")
    (packets_dir / "pairwise_packet_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "PAIRWISE_BANDITS_REPORT.md").write_text(
        "# Pairwise Bandits Report\n\n"
        "Pairwise packets have been built but live judging has not been postprocessed yet.\n",
        encoding="utf-8",
    )
    return audit


def _sgha_family_paths_for_domains(repair_namespace: Path) -> dict[str, Path]:
    paper_sgha_root = repair_namespace.parent
    return {
        "bandits": paper_sgha_root / "domain_batch_downstream_full_comparison_20260713_033820" / "runs" / "bandits" / "final_sgha_family_report" / "final_project_families.json",
        "in_context_learning": paper_sgha_root / "domain_batch_downstream_full_comparison_20260713_033820" / "runs" / "in_context_learning" / "final_sgha_family_report" / "final_project_families.json",
        "reasoning_models_test_time_compute": paper_sgha_root / "domain_batch_downstream_full_comparison_20260713_033820" / "runs" / "reasoning_models_test_time_compute" / "final_sgha_family_report" / "final_project_families.json",
        "offline_reinforcement_learning_arxiv": paper_sgha_root / "domain_batch_two_more_topics_comparison_20260714_022034" / "runs" / "offline_reinforcement_learning_arxiv" / "final_sgha_family_report" / "final_project_families.json",
        "uncertainty_calibration_conformal_prediction_arxiv": paper_sgha_root / "domain_batch_two_more_topics_comparison_20260714_022034" / "runs" / "uncertainty_calibration_conformal_prediction_arxiv" / "final_sgha_family_report" / "final_project_families.json",
    }


def _ensure_four_way_schema(row: dict[str, Any], *, domain: str, method: str) -> dict[str, Any]:
    out = {key: _json_text(row.get(key)) for key in CALIBRATED_PACKET_FIELDS}
    out["domain"] = domain
    out["method"] = method
    return out


def _load_four_way_method_candidates(repair_namespace: Path) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    sgha_paths = _sgha_family_paths_for_domains(repair_namespace)
    source_paths: dict[str, Path] = {}
    rows: list[dict[str, Any]] = []
    for domain in FOUR_WAY_DOMAINS:
        source_paths[f"{domain}::SGHA_FULL"] = sgha_paths[domain]
        families = _load_family_rows(sgha_paths[domain])
        for row in families:
            normalized = _normalize_sgha_family(row)
            rows.append(_ensure_four_way_schema(normalized, domain=domain, method="SGHA_FULL"))

        simple_path = repair_namespace / "baselines" / "simple_qwen" / domain / "baseline_ideas.jsonl"
        source_paths[f"{domain}::SIMPLE_QWEN"] = simple_path
        for row in _load_jsonl_rows(simple_path):
            rows.append(_ensure_four_way_schema(_normalize_simple_or_rag_idea(row), domain=domain, method="SIMPLE_QWEN"))

        rag_path = repair_namespace / "baselines" / "qwen_rag" / domain / "baseline_ideas.jsonl"
        source_paths[f"{domain}::QWEN_RAG"] = rag_path
        for row in _load_jsonl_rows(rag_path):
            rows.append(_ensure_four_way_schema(_normalize_simple_or_rag_idea(row), domain=domain, method="QWEN_RAG"))

        native_path = repair_namespace / "native_ai_scientist_v2_ideation_baseline" / "outputs" / domain / "ai_scientist_native_ideas.jsonl"
        source_paths[f"{domain}::NATIVE_AI_SCIENTIST_V2"] = native_path
        for row in _load_jsonl_rows(native_path):
            rows.append(_ensure_four_way_schema(_normalize_native_ai_scientist_idea(row), domain=domain, method="NATIVE_AI_SCIENTIST_V2"))
    return rows, source_paths


def _candidate_for_selection_prompt(candidate: dict[str, Any]) -> str:
    fields = [
        ("candidate_id", candidate.get("candidate_id")),
        ("title", candidate.get("title")),
        ("problem_statement", candidate.get("problem_statement")),
        ("motivation_or_abstract", candidate.get("motivation_or_abstract")),
        ("expected_contribution", candidate.get("expected_contribution")),
        ("evaluation_plan", candidate.get("evaluation_plan")),
        ("risks_or_caveats", candidate.get("risks_or_caveats")),
        ("source_context_or_grounding", candidate.get("source_context_or_grounding")),
        ("formal_problem_statement", candidate.get("formal_problem_statement")),
        ("assumptions_or_problem_setup", candidate.get("assumptions_or_problem_setup")),
        ("ambiguity_or_missing_definitions", candidate.get("ambiguity_or_missing_definitions")),
    ]
    parts = []
    for label, value in fields:
        text = _json_text(value)
        if len(text) > 2200:
            text = text[:2200] + " ... [truncated for selection]"
        parts.append(f"- {label}: {text}")
    return "\n".join(parts)


def build_best_candidate_selection_prompt(domain: str, method: str, candidates: list[dict[str, Any]]) -> str:
    blocks = []
    for candidate in candidates:
        blocks.append(_candidate_for_selection_prompt(candidate))
    return f"""You are a strict senior research reviewer selecting the strongest candidate within one method/domain pool.
This is selection only; do not compare methods.
Choose the candidate most worth serious source-paper reading.
Consider clarity/specificity, significance, novelty potential from provided text only, feasibility, evidence/source grounding, formalizability, actionability, low term-soup risk, and pursuit priority.
Do not use external knowledge.
Do not compute numeric scores or weighted composite scores.

Domain: {domain}
Method bookkeeping label: {method}

Return valid JSON only:
{{
  "domain": "{domain}",
  "method": "{method}",
  "selected_candidate_id": "...",
  "selection_reason": "...",
  "confidence": "LOW | MEDIUM | HIGH"
}}

CANDIDATES:

{chr(10).join(blocks)}
"""


def _validate_selection_response(value: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {str(candidate.get("candidate_id")) for candidate in candidates}
    selected = str(value.get("selected_candidate_id"))
    if selected not in ids:
        raise JudgeError(f"Selection chose unknown candidate_id: {selected}")
    if value.get("confidence") not in {"LOW", "MEDIUM", "HIGH"}:
        raise JudgeError(f"Invalid selection confidence: {value.get('confidence')}")
    if not str(value.get("selection_reason", "")).strip():
        raise JudgeError("selection_reason is required")
    return {
        "selected_candidate_id": selected,
        "selection_reason": str(value.get("selection_reason")),
        "confidence": str(value.get("confidence")),
    }


def _deterministic_select(candidates: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    selected = sorted(candidates, key=lambda row: (-_selection_score(row), len(str(row.get("title", ""))), str(row.get("candidate_id"))))[0]
    return selected, "deterministic fallback: completeness/source/formal/evaluation heuristic"


def _write_four_way_pool_summary(path: Path, rows: list[dict[str, Any]], source_paths: dict[str, Path]) -> None:
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        counts[(str(row.get("domain")), str(row.get("method")))] = counts.get((str(row.get("domain")), str(row.get("method"))), 0) + 1
    lines = [
        "# Best-of-Method 4-Way Candidate Pool Summary",
        "",
        "| domain | method | candidates | source path |",
        "|---|---|---:|---|",
    ]
    for domain in FOUR_WAY_DOMAINS:
        for method in FOUR_WAY_METHODS:
            lines.append(f"| {domain} | {method} | {counts.get((domain, method), 0)} | `{source_paths.get(f'{domain}::{method}', Path('missing'))}` |")
    lines.append("")
    lines.append("Missing fields are recorded as `not provided`; baseline formal problem fields are not fabricated.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def select_best_four_way_candidates(
    *,
    config: dict[str, Any],
    candidates: list[dict[str, Any]],
    output_dir: Path,
    use_llm: bool,
) -> list[dict[str, Any]]:
    selection_dir = output_dir / "selection"
    raw_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    api_key_env = str(config["judge"].get("api_key_env", "OPENROUTER_API_KEY"))
    llm_available = use_llm and bool(os.environ.get(api_key_env))
    for domain in FOUR_WAY_DOMAINS:
        for method in FOUR_WAY_METHODS:
            pool = [row for row in candidates if row.get("domain") == domain and row.get("method") == method]
            if not pool:
                raise JudgeError(f"No candidates found for {domain}/{method}")
            selection_method = "single_candidate"
            if len(pool) == 1:
                selected = pool[0]
                reason = "only candidate in method/domain pool"
                confidence = "HIGH"
            elif llm_available:
                prompt = build_best_candidate_selection_prompt(domain, method, pool)
                try:
                    response_text, response_meta = call_openrouter(config, prompt)
                    raw_rows.append({"domain": domain, "method": method, "raw_response": response_text, "metadata": response_meta})
                    parsed = _validate_selection_response(parse_model_json(response_text), pool)
                    selected = next(row for row in pool if str(row.get("candidate_id")) == parsed["selected_candidate_id"])
                    reason = parsed["selection_reason"]
                    confidence = parsed["confidence"]
                    selection_method = "openrouter_llm"
                except Exception as exc:
                    selected, reason = _deterministic_select(pool)
                    reason = f"{reason}; LLM selection failed: {exc}"
                    confidence = "LOW"
                    selection_method = "deterministic_fallback_after_llm_error"
                    error_rows.append({"domain": domain, "method": method, "error": str(exc)})
            else:
                selected, reason = _deterministic_select(pool)
                confidence = "MEDIUM"
                selection_method = "deterministic_fallback_no_api_key"
            row = dict(selected)
            row["selection_method"] = selection_method
            row["selection_reason"] = reason
            row["selection_confidence"] = confidence
            selected_rows.append(row)
    write_jsonl(selection_dir / "raw_selection_responses.jsonl", raw_rows)
    write_jsonl(selection_dir / "selection_errors.jsonl", error_rows)
    write_jsonl(selection_dir / "selected_best_candidates_unblinded.jsonl", selected_rows)
    lines = [
        "# Best-of-Method Selection Audit",
        "",
        f"- OpenRouter selection available: {llm_available}",
        f"- raw selection responses: {len(raw_rows)}",
        f"- selection errors/fallbacks: {len(error_rows)}",
        "",
        "| domain | method | selected candidate | selection method | title |",
        "|---|---|---|---|---|",
    ]
    for row in selected_rows:
        lines.append(f"| {row['domain']} | {row['method']} | `{row['candidate_id']}` | {row['selection_method']} | {row['title']} |")
    (selection_dir / "selection_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return selected_rows


def build_best_of_method_4way_trial(
    *,
    config: dict[str, Any],
    repair_namespace: Path,
    output_dir: Path,
    random_seed: int = 20260721,
    use_llm_selection: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for rel in ("candidate_pools", "selection", "four_way_packets", "judge_results"):
        (output_dir / rel).mkdir(parents=True, exist_ok=True)
    pool_rows, source_paths = _load_four_way_method_candidates(repair_namespace)
    write_jsonl(output_dir / "candidate_pools" / "all_candidates_unblinded.jsonl", pool_rows)
    _write_four_way_pool_summary(output_dir / "candidate_pools" / "candidate_pool_summary.md", pool_rows, source_paths)
    selected_rows = select_best_four_way_candidates(config=config, candidates=pool_rows, output_dir=output_dir, use_llm=use_llm_selection)

    rng = random.Random(random_seed)
    packet_audits = []
    for domain in FOUR_WAY_DOMAINS:
        domain_rows = [row for row in selected_rows if row.get("domain") == domain]
        if len(domain_rows) != 4:
            raise JudgeError(f"Expected 4 selected candidates for {domain}, found {len(domain_rows)}")
        shuffled = list(domain_rows)
        rng.shuffle(shuffled)
        blinded_candidates = []
        key_rows = []
        label_findings: list[dict[str, Any]] = []
        for index, row in enumerate(shuffled, start=1):
            blinded_id = f"Candidate {index}"
            blinded = {key: row.get(key, NOT_PROVIDED) for key in CALIBRATED_PACKET_FIELDS}
            blinded["candidate_id"] = blinded_id
            blinded["domain"] = domain
            blinded = _sanitize_candidate_for_blinding(blinded)
            labels = _packet_text_has_forbidden_method_labels(blinded)
            if labels:
                label_findings.append({"candidate_id": blinded_id, "labels": labels})
            blinded_candidates.append(blinded)
            key_rows.append(
                {
                    "domain": domain,
                    "blinded_candidate_id": blinded_id,
                    "candidate_id": row.get("candidate_id"),
                    "method": row.get("method"),
                    "title": row.get("title"),
                    "selection_method": row.get("selection_method"),
                    "selection_reason": row.get("selection_reason"),
                }
            )
        if label_findings:
            raise JudgeError(f"Blinded 4-way packet for {domain} contains method labels: {label_findings}")
        packet = {"domain": domain, "candidates": blinded_candidates}
        packet_path = output_dir / "four_way_packets" / f"{domain}_4way_blinded.json"
        key_path = output_dir / "four_way_packets" / f"{domain}_4way_blinding_key.json"
        packet_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
        key_path.write_text(json.dumps(key_rows, indent=2, ensure_ascii=False), encoding="utf-8")
        packet_audits.append({"domain": domain, "packet_path": str(packet_path), "key_path": str(key_path), "label_findings": label_findings, "candidate_order": [row["method"] for row in shuffled]})

    audit = {
        "created_at": utc_now_iso(),
        "repair_namespace": str(repair_namespace),
        "output_dir": str(output_dir),
        "random_seed": random_seed,
        "domains": list(FOUR_WAY_DOMAINS),
        "methods": list(FOUR_WAY_METHODS),
        "pool_count": len(pool_rows),
        "selected_count": len(selected_rows),
        "packet_count": len(packet_audits),
        "source_paths": {key: str(value) for key, value in source_paths.items()},
        "packets": packet_audits,
    }
    (output_dir / "four_way_packets" / "four_way_packet_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    lines = [
        "# Best-of-Method 4-Way Packet Audit",
        "",
        f"- created_at: {audit['created_at']}",
        f"- domains: {len(FOUR_WAY_DOMAINS)}",
        f"- methods per domain: {len(FOUR_WAY_METHODS)}",
        f"- selected candidates: {len(selected_rows)}",
        f"- packet count: {len(packet_audits)}",
        "",
        "| domain | blinded order methods stored in key only |",
        "|---|---|",
    ]
    for item in packet_audits:
        lines.append(f"| {item['domain']} | {'; '.join(item['candidate_order'])} |")
    (output_dir / "four_way_packets" / "four_way_packet_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "BEST_OF_METHOD_4WAY_REPORT.md").write_text(
        "# Best-of-Method 4-Way Report\n\nPackets built; judge results pending.\n",
        encoding="utf-8",
    )
    return audit


def _candidate_score_rows(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    ids = rubric_ids(config)
    for row in rows:
        out.append({"domain": row.get("domain"), "method": row.get("candidate_a_method"), **{key: row.get("candidate_a_scores", {}).get(key) for key in ids}})
        out.append({"domain": row.get("domain"), "method": row.get("candidate_b_method"), **{key: row.get("candidate_b_scores", {}).get(key) for key in ids}})
    return out


def write_group_averages(path: Path, rows: list[dict[str, Any]], config: dict[str, Any], group_key: str) -> None:
    ids = rubric_ids(config)
    candidate_rows = _candidate_score_rows(rows, config)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in candidate_rows:
        grouped.setdefault(str(row.get(group_key, "UNKNOWN")), []).append(row)
    fieldnames = [group_key, "n"] + [f"mean_{key}" for key in ids]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group, group_rows in sorted(grouped.items()):
            out = {group_key: group, "n": len(group_rows)}
            for key in ids:
                vals = [float(r[key]) for r in group_rows if isinstance(r.get(key), int)]
                out[f"mean_{key}"] = round(sum(vals) / len(vals), 4) if vals else ""
            writer.writerow(out)


def write_pairwise_preferences(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "comparison_id",
        "domain",
        "candidate_a_method",
        "candidate_b_method",
        "pairwise_preference",
        "preferred_method",
        "confidence",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            preference = row.get("pairwise_preference")
            if preference == "CANDIDATE_A":
                preferred = row.get("candidate_a_method")
            elif preference == "CANDIDATE_B":
                preferred = row.get("candidate_b_method")
            else:
                preferred = preference
            writer.writerow(
                {
                    "comparison_id": row.get("comparison_id"),
                    "domain": row.get("domain"),
                    "candidate_a_method": row.get("candidate_a_method"),
                    "candidate_b_method": row.get("candidate_b_method"),
                    "pairwise_preference": preference,
                    "preferred_method": preferred,
                    "confidence": row.get("confidence"),
                }
            )


def parse_domains(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--comparison-root", type=Path)
    parser.add_argument("--candidate-file", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-name", default="openrouter_llm_judge")
    parser.add_argument("--scoring-mode", choices=["independent", "pairwise", "pairwise_preference", "four_way_ranked", ROLE_BASED_MODE, FORMULATION_QUALITY_MODE, FORMULATION_ONLY_MODE, PERSONALIZED_FORMULATION_MODE, PRISM_IDEA_QUALITY_MODE])
    parser.add_argument("--domain")
    parser.add_argument("--domains")
    parser.add_argument("--baseline-name")
    parser.add_argument("--max-pairs", type=int)
    parser.add_argument("--build-calibrated-bandits-packet", action="store_true")
    parser.add_argument("--build-best-bandits-pairwise-trial", action="store_true")
    parser.add_argument("--build-best-of-method-4way-trial", action="store_true")
    parser.add_argument("--create-calibration-sentinels", action="store_true")
    parser.add_argument("--create-formulation-quality-sentinels", action="store_true")
    parser.add_argument("--create-formulation-only-sentinels", action="store_true")
    parser.add_argument("--create-personalized-sentinels", action="store_true")
    parser.add_argument("--create-prism-idea-quality-sentinels", action="store_true")
    parser.add_argument("--write-calibration-report", action="store_true")
    parser.add_argument("--build-role-based-all-domain-packets", action="store_true")
    parser.add_argument("--postprocess-formulation-quality", action="store_true")
    parser.add_argument("--postprocess-formulation-only", action="store_true")
    parser.add_argument("--postprocess-personalized-formulation", action="store_true")
    parser.add_argument("--postprocess-prism-idea-quality", action="store_true")
    parser.add_argument("--batch-calibrated", action="store_true")
    parser.add_argument("--repair-namespace", type=Path)
    parser.add_argument("--sgha-family-json", type=Path)
    parser.add_argument("--sgha-bandits-run-dir", type=Path)
    parser.add_argument("--pairwise-packet-file", type=Path)
    parser.add_argument("--four-way-packet-dir", type=Path)
    parser.add_argument("--blinding-key-file", type=Path)
    parser.add_argument("--postprocess-output-dir", type=Path)
    parser.add_argument("--blank-scoring-sheet", type=Path)
    parser.add_argument("--random-seed", type=int, default=20260721)
    parser.add_argument("--num-per-method", type=int, default=3)
    parser.add_argument("--num-per-pool", type=int, default=3)
    parser.add_argument("--no-legacy", action="store_true")
    parser.add_argument("--no-llm-selection", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-response")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--postprocess-unblind", action="store_true")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        scoring_mode = args.scoring_mode or config.get("evaluation", {}).get("scoring_mode", "pairwise")
        config.setdefault("evaluation", {})["scoring_mode"] = scoring_mode
        if scoring_mode in {"independent", "four_way_ranked", ROLE_BASED_MODE, FORMULATION_QUALITY_MODE, FORMULATION_ONLY_MODE, PERSONALIZED_FORMULATION_MODE, PRISM_IDEA_QUALITY_MODE}:
            config.setdefault("pairwise", {})["enabled"] = False
        if scoring_mode == "pairwise_preference":
            config.setdefault("pairwise", {})["enabled"] = True
        if args.create_calibration_sentinels:
            create_calibration_sentinels(args.output_dir)
        elif args.create_formulation_quality_sentinels:
            create_formulation_quality_calibration_sentinels(args.output_dir)
        elif args.create_formulation_only_sentinels:
            create_formulation_only_calibration_sentinels(args.output_dir)
        elif args.create_personalized_sentinels:
            create_personalized_calibration_sentinels(args.output_dir)
        elif args.create_prism_idea_quality_sentinels:
            create_prism_idea_quality_calibration_sentinels(args.output_dir)
        elif args.write_calibration_report:
            write_calibration_live_report(args.output_dir)
        elif args.build_role_based_all_domain_packets:
            if args.repair_namespace is None:
                raise JudgeError("--repair-namespace is required with --build-role-based-all-domain-packets")
            build_role_based_all_domain_candidate_packets(
                config=config,
                config_path=args.config,
                repair_namespace=args.repair_namespace,
                output_dir=args.output_dir,
                random_seed=args.random_seed,
                num_per_method=args.num_per_method,
            )
        elif args.build_calibrated_bandits_packet:
            if args.repair_namespace is None:
                raise JudgeError("--repair-namespace is required with --build-calibrated-bandits-packet")
            if args.sgha_family_json is None:
                raise JudgeError("--sgha-family-json is required with --build-calibrated-bandits-packet")
            build_calibrated_bandits_packet(
                repair_namespace=args.repair_namespace,
                output_dir=args.output_dir,
                sgha_family_json=args.sgha_family_json,
                random_seed=args.random_seed,
                num_per_method=args.num_per_method,
            )
        elif args.build_best_bandits_pairwise_trial:
            if args.repair_namespace is None:
                raise JudgeError("--repair-namespace is required with --build-best-bandits-pairwise-trial")
            if args.sgha_bandits_run_dir is None:
                raise JudgeError("--sgha-bandits-run-dir is required with --build-best-bandits-pairwise-trial")
            build_best_bandits_pairwise_trial(
                repair_namespace=args.repair_namespace,
                output_dir=args.output_dir,
                sgha_bandits_run_dir=args.sgha_bandits_run_dir,
                random_seed=args.random_seed,
                num_per_pool=args.num_per_pool,
                include_legacy=not args.no_legacy,
            )
        elif args.build_best_of_method_4way_trial:
            if args.repair_namespace is None:
                raise JudgeError("--repair-namespace is required with --build-best-of-method-4way-trial")
            build_best_of_method_4way_trial(
                config=config,
                repair_namespace=args.repair_namespace,
                output_dir=args.output_dir,
                random_seed=args.random_seed,
                use_llm_selection=not args.no_llm_selection,
            )
        elif args.postprocess_formulation_quality:
            if args.blinding_key_file is None:
                raise JudgeError("--blinding-key-file is required with --postprocess-formulation-quality")
            postprocess_unblind_formulation_quality(
                scoring_dir=args.output_dir,
                postprocess_dir=args.postprocess_output_dir or args.output_dir / "postprocess",
                blinding_key_file=args.blinding_key_file,
                blank_scoring_sheet=args.blank_scoring_sheet,
            )
        elif args.postprocess_formulation_only:
            if args.blinding_key_file is None:
                raise JudgeError("--blinding-key-file is required with --postprocess-formulation-only")
            postprocess_unblind_formulation_only(
                scoring_dir=args.output_dir,
                postprocess_dir=args.postprocess_output_dir or args.output_dir / "postprocess",
                blinding_key_file=args.blinding_key_file,
            )
        elif args.postprocess_personalized_formulation:
            if args.blinding_key_file is None:
                raise JudgeError("--blinding-key-file is required with --postprocess-personalized-formulation")
            postprocess_unblind_personalized_formulation(
                scoring_dir=args.output_dir,
                postprocess_dir=args.postprocess_output_dir or args.output_dir / "postprocess",
                blinding_key_file=args.blinding_key_file,
            )
        elif args.postprocess_prism_idea_quality:
            if args.blinding_key_file is None:
                raise JudgeError("--blinding-key-file is required with --postprocess-prism-idea-quality")
            postprocess_unblind_prism_idea_quality(
                scoring_dir=args.output_dir,
                postprocess_dir=args.postprocess_output_dir or args.output_dir / "postprocess",
                blinding_key_file=args.blinding_key_file,
            )
        elif args.postprocess_unblind:
            postprocess_unblind(config=config, output_dir=args.output_dir)
        else:
            if scoring_mode == "independent":
                if args.candidate_file is None:
                    raise JudgeError("--candidate-file is required for independent scoring")
                if args.batch_calibrated:
                    run_batch_calibrated_independent_scoring(
                        config=config,
                        config_path=args.config,
                        candidate_file=args.candidate_file,
                        output_dir=args.output_dir,
                        run_name=args.run_name,
                        domain=args.domain,
                        dry_run=args.dry_run,
                        mock_response=args.mock_response,
                        no_network=args.no_network,
                        resume=args.resume,
                        force=args.force,
                    )
                else:
                    run_independent_scoring(
                        config=config,
                        config_path=args.config,
                        candidate_file=args.candidate_file,
                        output_dir=args.output_dir,
                        run_name=args.run_name,
                        domain=args.domain,
                        dry_run=args.dry_run,
                        mock_response=args.mock_response,
                        no_network=args.no_network,
                        resume=args.resume,
                    force=args.force,
                )
            elif scoring_mode == FORMULATION_QUALITY_MODE:
                if args.candidate_file is None:
                    raise JudgeError("--candidate-file is required for formulation_quality_10pt scoring")
                run_formulation_quality_scoring(
                    config=config,
                    config_path=args.config,
                    candidate_file=args.candidate_file,
                    output_dir=args.output_dir,
                    run_name=args.run_name,
                    domain=args.domain,
                    dry_run=args.dry_run,
                    mock_response=args.mock_response,
                    no_network=args.no_network,
                    resume=args.resume,
                    force=args.force,
                )
            elif scoring_mode == FORMULATION_ONLY_MODE:
                if args.candidate_file is None:
                    raise JudgeError("--candidate-file is required for formulation_only_10pt scoring")
                run_formulation_only_scoring(
                    config=config,
                    config_path=args.config,
                    candidate_file=args.candidate_file,
                    output_dir=args.output_dir,
                    run_name=args.run_name,
                    domain=args.domain,
                    dry_run=args.dry_run,
                    mock_response=args.mock_response,
                    no_network=args.no_network,
                    resume=args.resume,
                    force=args.force,
                )
            elif scoring_mode == PERSONALIZED_FORMULATION_MODE:
                if args.candidate_file is None:
                    raise JudgeError("--candidate-file is required for personalized_formulation_10pt scoring")
                run_personalized_formulation_scoring(
                    config=config,
                    config_path=args.config,
                    candidate_file=args.candidate_file,
                    output_dir=args.output_dir,
                    run_name=args.run_name,
                    domain=args.domain,
                    dry_run=args.dry_run,
                    mock_response=args.mock_response,
                    no_network=args.no_network,
                    resume=args.resume,
                    force=args.force,
                )
            elif scoring_mode == PRISM_IDEA_QUALITY_MODE:
                if args.candidate_file is None:
                    raise JudgeError("--candidate-file is required for prism_idea_quality_10pt scoring")
                run_prism_idea_quality_scoring(
                    config=config,
                    config_path=args.config,
                    candidate_file=args.candidate_file,
                    output_dir=args.output_dir,
                    run_name=args.run_name,
                    domain=args.domain,
                    dry_run=args.dry_run,
                    mock_response=args.mock_response,
                    no_network=args.no_network,
                    resume=args.resume,
                    force=args.force,
                )
            elif scoring_mode == ROLE_BASED_MODE:
                if args.candidate_file is None:
                    raise JudgeError("--candidate-file is required for role_based_10pt scoring")
                run_role_based_scoring(
                    config=config,
                    config_path=args.config,
                    candidate_file=args.candidate_file,
                    output_dir=args.output_dir,
                    run_name=args.run_name,
                    domain=args.domain,
                    dry_run=args.dry_run,
                    mock_response=args.mock_response,
                    no_network=args.no_network,
                    resume=args.resume,
                    force=args.force,
                )
            elif scoring_mode == "four_way_ranked":
                if args.four_way_packet_dir is None:
                    raise JudgeError("--four-way-packet-dir is required for four_way_ranked scoring")
                run_four_way_ranked_scoring(
                    config=config,
                    config_path=args.config,
                    packet_dir=args.four_way_packet_dir,
                    output_dir=args.output_dir,
                    run_name=args.run_name,
                    dry_run=args.dry_run,
                    mock_response=args.mock_response,
                    no_network=args.no_network,
                    resume=args.resume,
                    force=args.force,
                )
            elif scoring_mode == "pairwise_preference":
                if args.pairwise_packet_file is None:
                    raise JudgeError("--pairwise-packet-file is required for pairwise_preference scoring")
                run_pairwise_preference_scoring(
                    config=config,
                    config_path=args.config,
                    pairwise_packet_file=args.pairwise_packet_file,
                    output_dir=args.output_dir,
                    run_name=args.run_name,
                    dry_run=args.dry_run,
                    mock_response=args.mock_response,
                    no_network=args.no_network,
                    resume=args.resume,
                    force=args.force,
                )
            else:
                if args.comparison_root is None:
                    raise JudgeError("--comparison-root is required unless --postprocess-unblind is used")
                run_scoring(
                    config=config,
                    config_path=args.config,
                    comparison_root=args.comparison_root,
                    output_dir=args.output_dir,
                    run_name=args.run_name,
                    domains=parse_domains(args.domains),
                    baseline_name=args.baseline_name,
                    max_pairs=args.max_pairs,
                    dry_run=args.dry_run,
                    mock_response=args.mock_response,
                    no_network=args.no_network,
                    resume=args.resume,
                    force=args.force,
                )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
