from __future__ import annotations

import json
from typing import Any

from .extraction_schemas import EXTRACTION_SCHEMA_JSON
from .utils import to_jsonable


def extraction_prompt(paper_id: str, title: str, text: str, max_chars: int = 28000) -> str:
    # Take first 20k + last 8k to capture intro AND conclusion/future-work sections
    if len(text) <= max_chars:
        clipped = text
    else:
        head = text[:20000]
        tail = text[-(max_chars - 20000):]
        clipped = head + "\n\n[... middle section omitted for length ...]\n\n" + tail

    example = json.dumps({
        "paper_id": paper_id,
        "claims": ["main claim of THIS paper (not prior work)"],
        "limitations": ["limitation the AUTHORS acknowledge about their own method"],
        "failure_conditions": ["specific condition where THIS paper's method fails or degrades"],
        "contradictions_or_tensions": ["explicit tension with prior work: 'unlike X which assumes Y, we show Z'"],
        "future_work": ["open problem or future direction explicitly stated by the authors"],
        "methods": ["specific algorithm name from paper"],
        "assumptions": ["assumption THIS method makes, e.g. sub-Gaussian noise, known horizon T"],
        "tasks": ["specific task, e.g. stochastic linear bandit, contextual dueling bandit"],
        "datasets": ["dataset name"],
        "metrics": ["cumulative regret", "sample complexity"],
        "results": ["key result with specific bound or number"],
        "tuples": [
            {
                "subject": "AlgorithmName",
                "relation": "fails_under",
                "object": "non-realizable reward function",
                "evidence_text": "exact verbatim words from the paper text",
                "section": "Analysis",
                "confidence": 0.85,
                "claim_type": "failure",
                "polarity": "negative",
                "condition": "when realizability assumption is violated",
                "task": "stochastic linear bandit",
                "dataset": "",
                "model": "",
                "metric": "cumulative regret",
                "direction": "worsens",
                "evidence_type": "theoretical",
                "strength": "strong",
                "source_span": "exact verbatim phrase from paper, non-empty",
                "subject_scope": "own_method",
                "resolved_by_paper": False,
                "in_related_work": False,
            },
            {
                "subject": "PriorAlgorithmName",
                "relation": "limited_by",
                "object": "finite action set",
                "evidence_text": "exact verbatim words from the paper text",
                "section": "Introduction",
                "confidence": 0.75,
                "claim_type": "limitation",
                "polarity": "negative",
                "condition": "",
                "task": "",
                "dataset": "",
                "model": "",
                "metric": "",
                "direction": "unknown",
                "evidence_type": "citation",
                "strength": "moderate",
                "source_span": "exact verbatim phrase from paper, non-empty",
                "subject_scope": "prior_work",
                "resolved_by_paper": True,
                "in_related_work": True,
            },
        ],
    }, indent=2)

    return f"""You are a scientific information extractor. Read the paper below and extract structured information as JSON.

IMPORTANT: Do NOT return a schema or template. Return a JSON object with REAL extracted content from this specific paper.

Output keys:
  paper_id           — set to "{paper_id}"
  claims             — up to 5 main claims of THIS paper (not prior work)
  limitations        — up to 5 limitations the authors acknowledge about their OWN method
  failure_conditions — up to 5 conditions where THIS paper's method fails or degrades
                       ONLY include failures of the paper's own method, not prior work failures
                       DISTINGUISH from assumptions: a failure is what happens WHEN an assumption is VIOLATED
                       BAD: "The method assumes sub-Gaussian noise" → this is an assumption, not a failure
                       GOOD: "Performance degrades when noise is not sub-Gaussian" → this is a failure
  contradictions_or_tensions — up to 5 explicit tensions with prior work.
                       Look for: "unlike X", "in contrast to", "X assumes Y but", "prior work fails to"
                       These are REQUIRED if the paper argues against prior assumptions
  future_work        — up to 5 open problems or future directions explicitly stated by the authors.
                       Look for: "future work", "open problem", "beyond scope", "we leave", "remains open"
                       These are the most valuable for gap detection — DO NOT skip them
  methods            — up to 6 specific named algorithms or techniques from this paper
  assumptions        — up to 5 assumptions THIS method requires (e.g., sub-Gaussian noise, known T, IID)
  tasks              — up to 5 SPECIFIC tasks. Include the bandit/RL type AND the setting.
                       GOOD: "stochastic linear bandit", "contextual dueling bandit with adversarial feedback", "fixed-budget best arm identification"
                       BAD: "regret minimization", "optimization", "learning", "bandits", "reinforcement learning"
  datasets           — up to 5 dataset names
  metrics            — up to 4 evaluation metrics
  results            — up to 4 key results with specific bounds or numbers
  tuples             — up to 15 structured claim tuples (see below)

For each tuple:
  subject        — specific named entity (algorithm, model name). NEVER generic: "Method", "Algorithm", "Our approach"
  relation       — MUST be one of: evaluated_on, improves_over, fails_under, assumes,
                   contradicts, uses_dataset, measured_by, limited_by, addresses, not_addressed_by
  object         — target entity (condition, dataset, metric, other method)
  evidence_text  — EXACT verbatim copy from the paper text (under 150 chars). NO paraphrasing.
  section        — paper section where this appears
  confidence     — 0.90–1.0: explicitly stated; 0.70–0.89: strongly implied; 0.50–0.69: inferred
  claim_type     — method | result | limitation | assumption | comparison | failure | hypothesis | evaluation | unknown
  polarity       — positive | negative | neutral | mixed | unknown
                   RULE: improves_over → positive. fails_under/limited_by → negative. assumes → neutral.
  condition      — REQUIRED when claim only holds in a specific regime or setting. Empty only if truly unconditional.
  task           — specific task name (not generic)
  dataset        — dataset name if applicable
  model          — model name if applicable
  metric         — metric name if applicable
  direction      — improves | worsens | no_change | unknown (for theoretical results: improves=tighter bound)
  evidence_type  — empirical | theoretical | ablation | qualitative | assumption | citation | benchmark | unknown
  strength       — strong | moderate | weak | unknown
  source_span    — EXACT verbatim phrase from paper (under 80 chars, MUST be non-empty)
  subject_scope  — CRITICAL: own_method | prior_work | general
                   own_method: subject is this paper's contribution
                   prior_work: subject is a prior/baseline method being discussed or critiqued
                   general: applies to a class of methods or the field broadly
  resolved_by_paper — true if this paper proposes a solution to this limitation/failure, false otherwise
  in_related_work   — true if this quote comes from the Related Work or Introduction discussing prior work

PRIORITIZE extracting (in order):
1. not_addressed_by tuples — explicit open problems, out-of-scope statements, future work
2. fails_under and limited_by for OWN method (subject_scope=own_method, resolved_by_paper=false)
3. Key assumptions of the own method that are unrealistic in practice
4. contradictions_or_tensions — what prior work gets wrong that this paper addresses
5. improves_over — specific quantitative comparisons with prior methods
6. DO NOT extract evaluated_on/uses_dataset/measured_by tuples unless they have both metric and dataset filled

Example output format:
{example}

Rules:
- Keep each string under 120 characters.
- Extract at least 5 tuples if the paper has sufficient content.
- subject MUST be a specific named entity. NEVER use: "Method", "Model", "Algorithm", "Approach", "System", "Technique", "The method", "The model", "Algorithm 1", "Existing algorithms", "Baseline", "Prior work", "Our method", "The proposed method"
- direction: exactly one of improves/worsens/no_change/unknown. Never use synonyms.
- For theoretical results: direction=improves means tighter/better bound, worsens means looser/worse.
- ANTI-HALLUCINATION: evidence_text and source_span MUST appear verbatim in the paper text. Do NOT paraphrase. If you cannot find the exact words, omit the tuple entirely.
- Do NOT conflate assumptions with failures. An assumption is what the method requires. A failure is what happens when conditions break.
- If a limitation is stated in Related Work and this paper resolves it: subject_scope=prior_work, resolved_by_paper=true, in_related_work=true.
- If a limitation is stated about this paper's own method: subject_scope=own_method, resolved_by_paper=false.
- REGIME-CONDITIONAL FAILURES: If the paper shows the method SUCCEEDS in regime A but FAILS in regime B, create TWO tuples — one improves_over with condition=regime_A, one fails_under with condition=regime_B. NEVER merge into one unconditional failure. Example: "matches lower bound in high-privacy regime, loose in low-privacy regime" → two tuples, NOT one failure.
- resolved_by_paper=true ONLY for prior_work subjects. NEVER set resolved_by_paper=true for own_method subjects.

Paper title: {title}
Paper ID: {paper_id}

Paper text:
{clipped}
"""


def resolution_extraction_prompt(paper_id: str, title: str, text: str, max_chars: int = 28000) -> str:
    if len(text) <= max_chars:
        text_clipped = text
    else:
        head = text[:20000]
        tail = text[-(max_chars - 20000):]
        text_clipped = head + "\n\n[... middle section omitted for length ...]\n\n" + tail

    return f"""You are a scientific information extractor. Your ONLY task is to find explicit claims that this paper's contribution addresses, relaxes, removes, resolves, or handles a prior limitation, assumption, or failure condition.

Paper ID: {paper_id}
Title: {title}

Text:
{text_clipped}

Extract resolution records ONLY where this paper EXPLICITLY claims to address, relax, resolve, remove, or handle something from prior work.

DO NOT extract:
- Papers that merely mention a limitation
- Citations to related work without resolution claims
- Metric improvements without explaining what limitation is addressed
- Future work suggestions
- Evaluations under a setting without claiming to handle a prior failure

For each genuine resolution claim, output a JSON object with ALL of the following fields.
Every field is required. Do not omit any field, especially confidence.

{{
  "method": "name of algorithm/theorem/result from THIS paper",
  "resolution_relation": "addresses_limitation | relaxes_assumption | handles_failure_condition | resolves_failure_condition | partially_addresses | improves_under_condition",
  "target_problem": "the specific problem/assumption/failure being addressed",
  "target_problem_type": "assumption | limitation | failure_condition | benchmark_gap | unclear",
  "addressed_condition": "the specific condition or setting where prior methods failed",
  "prior_work_or_baseline": "name of prior method or assumption being addressed, if mentioned",
  "scope": "the specific setting where the resolution applies",
  "claim_strength": "full | partial | empirical_only | theoretical_only | unclear",
  "evidence_text": "VERBATIM text from paper that explicitly states the resolution claim",
  "section": "section name",
  "confidence": 0.90
}}

confidence is required and must be a number between 0.0 and 1.0.
Use these guidelines: 0.90-1.0 = paper explicitly states the claim; 0.70-0.89 = claim is strongly implied; 0.50-0.69 = inferred but uncertain.
If you cannot assign at least 0.50 confidence, omit the record entirely.
Do NOT omit the confidence field from any record you include.

Return JSON: {{"resolutions": [...]}}
Return empty list if no genuine resolution claims found.
"""


def counterevidence_classifier_prompt(
    gap_label: str,
    gap_type: str,
    gap_evidence: str,
    resolution_method: str,
    target_problem: str,
    addressed_condition: str,
    scope: str,
    evidence_text: str,
    prior_work_or_baseline: str,
) -> str:
    return f"""You are a research gap analyst. Determine whether the resolution claim addresses the research gap described below.
Judge ONLY from the evidence provided. Do NOT use external memory or training data.

Gap:
  Label: {gap_label}
  Type: {gap_type}
  Evidence: {gap_evidence[:500]}

Resolution claim:
  Method: {resolution_method}
  Claim: {target_problem}
  Addressed condition: {addressed_condition}
  Scope: {scope}
  Evidence: {evidence_text[:500]}
  Prior work addressed: {prior_work_or_baseline}

Classify the relationship:
- "fully_addresses": resolution completely solves the gap within a matching scope
- "partially_addresses": resolution addresses a subset of the gap or a related but narrower setting
- "relaxes_assumption": resolution removes or weakens the assumption that creates the gap
- "handles_failure_condition": resolution handles the specific condition where prior methods fail
- "related_but_not_solution": resolution is in the same area but does not solve the gap
- "unrelated": no meaningful relationship
- "unclear": insufficient evidence to judge

Return a SINGLE concise JSON object ONLY. No markdown, no code fences, no prose before or
after. Do NOT restate the evidence. Keep "why" to one short sentence (<= 30 words) and
"remaining_gap_scope" to one short phrase (<= 20 words).
{{"label": "...", "confidence": 0.0-1.0, "scope_match": "full|partial|mismatch|unclear", "why": "...", "remaining_gap_scope": "...", "should_create_counterevidence_edge": true/false}}
"""


def reconciliation_prompt(subject: str, relation: str, object_: str, source_span: str, text: str, max_chars: int = 16000) -> str:
    if len(text) <= max_chars:
        clipped = text
    else:
        clipped = text[:12000] + "\n\n[... middle omitted ...]\n\n" + text[-(max_chars - 12000):]

    return f"""You are verifying a specific extracted claim about a research paper.

The claim below was extracted as a failure or limitation of the paper's own method.
Your job: determine whether this failure is CONDITIONAL (only holds in specific regimes/settings)
or UNCONDITIONAL (always holds regardless of conditions).

Extracted tuple:
  subject:     {subject}
  relation:    {relation}
  object:      {object_}
  source_span: "{source_span}"

Instructions:
1. Find the source_span in the paper and read its full surrounding context (2-3 paragraphs).
2. Check if the paper ALSO shows that the method SUCCEEDS in a different regime or condition.
3. If yes: the failure is conditional — identify the specific condition under which it fails.
4. If no: the failure is unconditional.

Return ONLY valid JSON with exactly these keys:
{{
  "is_conditional": true or false,
  "condition": "exact condition under which the failure holds, e.g. 'low-privacy regime only (ε large)' — empty string if unconditional",
  "contrasting_success": "description of when/how the method succeeds if conditional — empty string if unconditional",
  "reasoning": "one sentence explaining your conclusion"
}}

Paper text:
{clipped}
"""


def gap_explanation_prompt(gap: dict[str, Any]) -> str:
    return f"""Explain why this detected graph motif is a research gap.
Return ONLY JSON with keys: gap, target, scope, mechanism, supporting_evidence, counterevidence, traceability_path, novelty_score, feasibility_score, impact_score, overall_score.
Say "insufficient evidence" when evidence is weak.

Candidate motif:
{json.dumps(to_jsonable(gap), indent=2)}
"""


def verification_prompt(agent_name: str, gap: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    roles = {
        "support_agent": "You support the hypothesis. Find evidence that this gap is recurring, important, and not already solved.",
        "skeptic_agent": "You challenge the hypothesis. Find counterevidence, papers that already solve this gap, or reasons the framing is weak.",
        "feasibility_agent": "You assess feasibility. Evaluate whether this gap can be studied: available datasets, benchmarks, code, and experimental protocols.",
        "mechanism_agent": "You propose mechanisms. Identify plausible causal or mechanistic explanations for why this gap exists.",
        "critic": "You review conservatively. Score this gap on all dimensions and identify the main weakness.",
    }
    return f"""{roles.get(agent_name, agent_name)}

Return ONLY valid JSON with EXACTLY these keys. All score values must be floats between 0.0 and 1.0.

{{
  "gap_id": "<copy from gap>",
  "agent_name": "{agent_name}",
  "summary": "<one sentence assessment>",
  "evidence": [{{"paper_id": "...", "evidence_text": "..."}}],
  "counterevidence": [{{"paper_id": "...", "evidence_text": "..."}}],
  "citations": ["paper_id_1", "paper_id_2"],
  "confidence": <float 0.0-1.0 representing your overall confidence that this is a real gap>,
  "failure_modes": ["<reason this gap framing might fail>"],
  "scores": {{
    "evidence_support": <float 0.0-1.0, how well supported by evidence>,
    "novelty": <float 0.0-1.0, how novel vs. already-solved>,
    "feasibility": <float 0.0-1.0, how experimentally feasible>,
    "specificity": <float 0.0-1.0, how specific and actionable the gap statement is>,
    "scope_validity": <float 0.0-1.0, how valid the claimed scope is>
  }}
}}

Gap to assess:
{json.dumps(to_jsonable(gap), indent=2)}

Retrieved evidence from papers:
{json.dumps(to_jsonable(evidence), indent=2)}
"""


def evolution_prompt(operator: str, candidates: list[dict[str, Any]]) -> str:
    return f"""Apply evolutionary operator "{operator}" to the candidate research problems.
Return ONLY JSON with keys: problem_statement, gap, target, scope, mechanism, supporting_evidence, counterevidence, traceability_path, novelty_score, feasibility_score, impact_score.
Keep all claims traceable to paper IDs and evidence snippets.
Say "insufficient evidence" where evidence is absent.

Candidates:
{json.dumps(to_jsonable(candidates), indent=2)}
"""


def final_hypothesis_prompt(candidate: dict[str, Any]) -> str:
    return f"""Write a final auditable research-problem hypothesis from this candidate.
Return ONLY JSON with keys matching the candidate plus problem_statement.
Do not invent citations; cite only paper IDs already present.

Candidate:
{json.dumps(to_jsonable(candidate), indent=2)}
"""


def deep_review_prompt(payload: dict) -> str:
    """Critical reviewer prompt: judge whether a hypothesis is genuinely meaningful.

    `payload` carries problem_statement, motif, gap descriptions, counterevidence_status,
    remaining_gap_scope, supporting/counterevidence papers + evidence snippets,
    verification summary, and traceability summary.
    """
    import json as _json
    return f"""You are a skeptical senior research reviewer for the technical field the hypothesis belongs to (infer the field from the evidence below; do NOT assume a specific field). Judge ONLY from the evidence provided below. Do NOT use outside knowledge to invent support; you MAY use general domain knowledge to flag that something is already solved or impossible.

Your job is to decide whether this is a MEANINGFUL research hypothesis or whether it should be rejected. Reject freely. Do NOT make weak hypotheses sound strong.

Hypothesis and evidence:
{_json.dumps(payload, indent=2)[:6000]}

Answer these checks:
1. Is the remaining gap real, or does the counterevidence essentially solve it?
2. Does any supporting/counterevidence paper PROVE the target is impossible (look for: impossible, lower bound, cannot achieve, no algorithm can, minimax lower bound, Omega(, impossibility, intractable, NP-hard, rules out, unavoidable)? If the hypothesis asks to beat such a bound under the SAME assumptions, it must be DROP_IMPOSSIBLE.
3. Is the hypothesis asking to overcome a proven lower bound?
4. Is it specific enough to state a concrete theorem, algorithm, or experiment?
5. Is it merely generic or LLM-phrased boilerplate (e.g. "distributed/blockchain/consensus" filler with no concrete mechanism)?
6. Is it off-domain (outside the technical field of its own supporting evidence/corpus)?
7. Is it supported by only one paper with thin evidence?
8. What single condition would falsify it?

Choose exactly one review_label:
- STRONG_CANDIDATE: specific, evidence-backed, real open gap, concrete next step.
- POSSIBLE_WITH_REWRITE: real core but needs re-scoping/de-genericizing.
- WEAK_AFTER_READING: evidence too thin to judge meaningful.
- DROP_GENERIC: vague/boilerplate, no concrete mechanism.
- DROP_ALREADY_SOLVED: counterevidence or known results essentially solve it.
- DROP_IMPOSSIBLE: asks to beat a proven impossibility/lower bound.
- DROP_ARTIFICIAL_SCOPE: remaining_gap_scope is empty/artificial ("None identified; covered").
- DROP_OFF_DOMAIN: outside the technical field of its own supporting evidence/corpus.
- DROP_DUPLICATE: same idea as another hypothesis.
- DROP_TOO_SINGLE_PAPER_FRAGILE: rests on one paper with weak/ambiguous evidence.

Return ONLY this JSON:
{{
  "review_label": "<one label>",
  "deep_review_score": 0.0-1.0,
  "evidence_strength": 0.0-1.0,
  "remaining_gap_realness": 0.0-1.0,
  "counterevidence_risk": 0.0-1.0,
  "impossibility_risk": 0.0-1.0,
  "already_solved_risk": 0.0-1.0,
  "specificity": 0.0-1.0,
  "feasibility": 0.0-1.0,
  "project_concreteness": 0.0-1.0,
  "novelty_risk": "low|medium|high",
  "main_reason": "one sentence",
  "falsification_condition": "one sentence",
  "clean_rewrite": "one precise academic sentence",
  "recommended_next_step": "one sentence"
}}"""


def axis_induction_prompt(node_labels_by_type: dict, top_gaps: list, counterevidence_summaries: list, paper_titles: list | None = None) -> str:
    """Domain-NEUTRAL: induce reusable formulation axes from corpus structure.
    Must not assume any specific research domain."""
    import json as _json
    payload = {
        "node_labels_by_type": {k: v[:30] for k, v in node_labels_by_type.items()},
        "top_gaps": top_gaps[:25],
        "counterevidence_summaries": counterevidence_summaries[:15],
        "paper_titles": (paper_titles or [])[:30],
    }
    return f"""You are analyzing a research-paper corpus's structural graph to extract REUSABLE problem-formulation axes. You do NOT know the domain in advance; infer everything from the data below.

Do NOT solve any research problem. Extract reusable axes only: method/system families, settings/contexts, objectives, assumptions that could be relaxed, failure modes, comparators/baselines, evaluation targets, and deployment constraints.

Corpus data:
{_json.dumps(payload, indent=2)[:6000]}

Return ONLY this JSON (each a list of short phrases drawn from the data, not invented):
{{
  "method_families": [],
  "settings": [],
  "objectives": [],
  "assumptions_to_relax": [],
  "failure_modes": [],
  "comparators": [],
  "evaluation_targets": [],
  "constraints": [],
  "deployment_contexts": [],
  "notes": []
}}"""


def formulation_generation_prompt(gap: dict, axes: dict, max_formulations: int = 8) -> str:
    """Domain-NEUTRAL: enumerate distinct formal problem formulations for one gap."""
    import json as _json
    return f"""You are a research methodologist. Given ONE structural gap and corpus-inferred formulation axes, enumerate {max_formulations} DISTINCT, concrete problem formulations. Do not solve them; specify them.

Use ONLY the provided gap, its evidence, and the inferred axes. Do not invent domain facts. If the gap is partially addressed in corpus, formulate around the REMAINING open scope, not the solved part. Include at least one conservative and one more ambitious formulation. Do not blindly cross all axes — only combinations the evidence supports.

Gap:
{_json.dumps(gap, indent=2)[:3500]}

Inferred axes:
{_json.dumps(axes, indent=2)[:2500]}

For each formulation specify: setting, the assumption/failure targeted, objective/metric, comparator/baseline, what theorem/algorithm/experiment counts as progress, what counterevidence already covers, why it remains open, and a falsification condition.

Return ONLY JSON: {{"formulations": [
  {{
    "short_name": "...",
    "formulation_question": "...",
    "problem_context": "...",
    "method_or_system_family": "...",
    "input_or_data_setting": "...",
    "environment_or_deployment_setting": "...",
    "feedback_or_observation_model": "...",
    "objective": "...",
    "metric_or_target_quantity": "...",
    "comparator_or_baseline": "...",
    "assumption_relaxed": "...",
    "failure_condition_targeted": "...",
    "resource_or_constraint_dimension": "...",
    "evaluation_protocol": "...",
    "theoretical_target": "...",
    "empirical_target": "...",
    "algorithmic_target": "...",
    "known_counterevidence": "...",
    "why_counterevidence_does_not_solve": "...",
    "formulation_type": "theorem|algorithm|benchmark|empirical_study|lower_bound|impossibility_refinement|system_design|dataset_or_evaluation|measurement_study",
    "falsification_condition": "..."
  }}
]}}"""


def formulation_viability_prompt(formulation: dict, gap_context: dict) -> str:
    """Domain-NEUTRAL: review a single formulation for viability. Judge only from evidence."""
    import json as _json
    return f"""You are a skeptical research reviewer. Judge whether this problem FORMULATION is viable, using ONLY the provided evidence (you may use general knowledge only to flag likely already-solved or impossible results). Reject freely; do not inflate weak formulations.

Formulation:
{_json.dumps(formulation, indent=2)[:3500]}

Gap context (evidence, counterevidence, remaining scope):
{_json.dumps(gap_context, indent=2)[:2500]}

Checks: (1) specific enough to state a theorem/algorithm/benchmark/experiment? (2) already solved by corpus counterevidence? (3) blocked by impossibility/lower-bound evidence? (4) merely a trivial reparameterization? (5) meaningfully distinct? (6) plausible concrete next step? (7) needs external literature check? (8) does remaining_gap_scope define a real problem?

Choose one viability_label:
VIABLE_FORMULATION, POSSIBLE_FORMULATION_WITH_REWRITE, ALREADY_SOLVED_FORMULATION, IMPOSSIBLE_FORMULATION, TRIVIAL_REDUCTION, ARTIFICIAL_SCOPE, TOO_BROAD, TOO_NARROW, OFF_DOMAIN, NEEDS_EXTERNAL_LIT_CHECK, INSUFFICIENT_EVIDENCE.

Return ONLY JSON:
{{"viability_label":"...","viability_score":0.0-1.0,"novelty_risk":"low|medium|high","feasibility":"easy|moderate|hard|very_hard","reason":"one sentence","falsification_condition":"one sentence","likely_existing_literature":"one phrase or none"}}"""


def generate_problem_abstract_prompt(payload: dict, *, min_words: int = 100, max_words: int = 220,
                                     author_context: str = "") -> str:
    """Domain-neutral, proposal-style abstract prompt for a final SGHA problem/hypothesis.

    `payload` carries: problem_statement, short_title, origin_motif_type, gap_description,
    supporting_paper_snippets, counterevidence_snippets, remaining_gap_scope, mechanism,
    feasibility, proposed_contribution_type. `author_context` is a short string only when
    personalization is enabled (empty otherwise).
    """
    import json as _json
    pers = (f"\nAuthor-profile context (personalization is ENABLED): {author_context}\n"
            "Include exactly ONE sentence connecting the problem to this author profile; "
            "do not overstate the fit, and do not use any role words (no mentor/student/advisor).\n"
            if author_context else "")
    return f"""You are writing a PROPOSAL-STYLE abstract for an OPEN research problem. This is a
proposal for work that has NOT been done yet — NOT a paper reporting finished results.

Write {min_words}-{max_words} words. Ground every statement ONLY in the evidence below; invent no
citations and no results.

ALLOWED framing (use this voice): "This project studies...", "The central question is...",
"A possible approach is...", "A successful outcome would provide...", "This would clarify...".
If the evidence is thin, be cautious: "This project would investigate...".

FORBIDDEN unless the supporting evidence already proves it: "We prove...", "We show...",
"Our experiments demonstrate...", "This paper establishes...", or any claim of a completed result.
{pers}
Problem and evidence:
{_json.dumps(payload, indent=2)[:6000]}

Return ONLY this JSON (no markdown):
{{
  "proposal_style_abstract": "<{min_words}-{max_words} word proposal-style abstract>",
  "abstract_generation_rationale": "one sentence on what the abstract is grounded in",
  "abstract_evidence_papers": ["paper_id", "..."],
  "abstract_counterevidence_papers": ["paper_id", "..."]
}}"""


def author_alignment_prompt(payload: dict) -> str:
    """Domain-neutral explanation of how a final problem relates to an author's profile.

    `payload` carries: problem_statement, topic, related_author_papers, related_cited_papers,
    related_citing_papers, graph_evidence_snippets. Author-profile framing only — never role
    words (mentor/student/advisor) and never second-person 'your'.
    """
    import json as _json
    return f"""Explain how the research problem below relates to a scholar/author's body of work,
using ONLY the provided related papers. Use author-profile framing — phrases like "extends the
author's work on X by relaxing assumption Y", "adjacent to papers that cite the author's work on
Z", or "related to, but not solved by, the author's prior paper A".

STRICTLY FORBIDDEN: "your mentor", "your advisor", "your student", "your" + any role, or any
mentor/student/advisor/supervisor terminology. Do not overstate the fit; if the connection is
weak, say so.

Problem and related papers:
{_json.dumps(payload, indent=2)[:5000]}

Return ONLY this JSON:
{{
  "author_alignment_reason": "1-3 sentences, author-profile framing only",
  "related_author_papers": ["paper_id", "..."],
  "related_cited_papers": ["paper_id", "..."],
  "related_citing_papers": ["paper_id", "..."],
  "relationship_to_author_profile": "one short phrase, e.g. 'extends prior work' / 'adjacent to citing work' / 'weakly related'"
}}"""
