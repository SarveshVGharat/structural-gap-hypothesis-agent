from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any

from .gap_detection import load_candidate_gaps
from .gap_objects import CandidateGap, EvolutionCandidate, EvolutionEvent, FinalHypothesis
from .llm_client import LLMClient
from .utils import append_jsonl, bounded, model_dump, read_json, stable_id, write_csv, write_json


def _get_motif_type(c: EvolutionCandidate) -> str:
    # Prefer the structured origin_motif_types (robust across generations)
    if getattr(c, "origin_motif_types", None):
        return c.origin_motif_types[0]
    if "Motif type:" in c.scope:
        return c.scope.split("Motif type:")[1].split(";")[0].strip()
    return ""


def _seed_origin_signature(gap: CandidateGap) -> str:
    """Deterministic, human-readable origin signature for a seed gap."""
    motif = gap.motif_type or "unknown_motif"
    return f"{motif}:{gap.gap_id}"


def _combined_origin_signature(operator_type: str, roots: list[str], gap_ids: list[str], motifs: list[str]) -> str:
    """Deterministic origin signature for combined (crossover/synthesis) candidates."""
    import hashlib
    roots_s = sorted(set(r for r in roots if r))
    gaps_s = sorted(set(g for g in gap_ids if g))
    motifs_s = sorted(set(m for m in motifs if m))
    key = operator_type + "|" + ",".join(roots_s) + "|" + ",".join(gaps_s) + "|" + ",".join(motifs_s)
    short = hashlib.sha1(key.encode()).hexdigest()[:10]
    motif_tag = "+".join(motifs_s) if motifs_s else "unknown"
    return f"synth[{motif_tag}]:{short}"


def _apply_seed_lineage(cand: EvolutionCandidate, gap: CandidateGap) -> None:
    """Populate lineage + counterevidence metadata on a freshly created seed candidate."""
    sig = _seed_origin_signature(gap)
    cand.origin_signature = sig
    cand.primary_origin_signature = sig
    cand.root_origin_signatures = [sig]
    cand.origin_gap_ids = [gap.gap_id]
    cand.origin_motif_types = [gap.motif_type or "unknown_motif"]
    cand.parent_candidate_ids = []
    cand.operator_type = "seed"
    cand.lineage_depth = 0
    cand.lineage_invalid = False
    # Counterevidence metadata (cleaned gaps carry these as pydantic extras)
    extra = getattr(gap, "model_extra", None) or {}
    cand.counterevidence_status = extra.get("counterevidence_status", "") or getattr(gap, "counterevidence_status", "") or ""
    cand.remaining_gap_scope = extra.get("remaining_gap_scope", "") or getattr(gap, "remaining_gap_scope", "") or ""
    cand.counterevidence_papers = extra.get("counterevidence_papers", []) or list(getattr(gap, "counterevidence_papers", []) or [])
    ce_edges = extra.get("counterevidence_edges", []) or list(getattr(gap, "counterevidence_edges", []) or [])
    cand.counterevidence_edges = ce_edges if isinstance(ce_edges, list) else []
    cand.original_gap_description = extra.get("original_gap_description", "") or getattr(gap, "original_gap_description", "") or gap.gap
    cand.downstream_gap_description = extra.get("downstream_gap_description", "") or getattr(gap, "downstream_gap_description", "") or gap.gap


def _load_verified_evolution_gap_ids(ctx: Any) -> tuple[set[str], str]:
    """Return verification-backed gap ids for legacy evolution when available."""
    summary_path = Path(ctx.path("verification", "verification_summary.json"))
    if summary_path.exists():
        data = read_json(summary_path, default={})
        ids: set[str] = set()
        if isinstance(data, dict):
            ids = {str(gid) for gid in data.keys() if str(gid).strip()}
        elif isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    gid = row.get("gap_id") or row.get("id")
                    if gid:
                        ids.add(str(gid))
        return ids, "verification_summary.json"

    survival_path = Path(ctx.path("verification", "gap_survival_scores.csv"))
    if survival_path.exists():
        ids: set[str] = set()
        with survival_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                gid = row.get("gap_id")
                if gid:
                    ids.add(str(gid))
        return ids, "gap_survival_scores.csv"

    return set(), ""


def _inherit_lineage_mutation(child: EvolutionCandidate, parent: EvolutionCandidate) -> None:
    """Mutation/refinement: preserve parent origin, bump depth."""
    child.origin_signature = parent.origin_signature
    child.primary_origin_signature = parent.primary_origin_signature
    child.root_origin_signatures = list(parent.root_origin_signatures)
    child.origin_gap_ids = list(parent.origin_gap_ids)
    child.origin_motif_types = list(parent.origin_motif_types)
    child.parent_candidate_ids = [parent.candidate_id]
    child.operator_type = "mutation"
    child.lineage_depth = parent.lineage_depth + 1
    child.lineage_invalid = parent.lineage_invalid
    child.counterevidence_status = parent.counterevidence_status
    child.remaining_gap_scope = parent.remaining_gap_scope
    child.counterevidence_papers = list(parent.counterevidence_papers)
    child.counterevidence_edges = list(parent.counterevidence_edges)
    child.original_gap_description = parent.original_gap_description
    child.downstream_gap_description = parent.downstream_gap_description


def _inherit_lineage_combine(child: EvolutionCandidate, parents: list[EvolutionCandidate], operator_type: str) -> None:
    """Crossover/synthesis: union parent roots; never collapse to unknown."""
    roots: list[str] = []
    gap_ids: list[str] = []
    motifs: list[str] = []
    for p in parents:
        roots += (p.root_origin_signatures or ([p.origin_signature] if p.origin_signature else []))
        gap_ids += (p.origin_gap_ids or ([p.gap_id] if p.gap_id else []))
        motifs += (p.origin_motif_types or ([_get_motif_type(p)] if _get_motif_type(p) else []))
    roots = sorted(set(r for r in roots if r))
    gap_ids = sorted(set(g for g in gap_ids if g))
    motifs = sorted(set(m for m in motifs if m))
    # Recover roots from gap_ids when parents lack origin signatures
    if not roots and gap_ids:
        roots = sorted(f"recovered:{g}" for g in gap_ids)
    child.root_origin_signatures = roots
    child.origin_gap_ids = gap_ids
    child.origin_motif_types = motifs
    child.parent_candidate_ids = [p.candidate_id for p in parents]
    child.operator_type = operator_type
    child.lineage_depth = max((p.lineage_depth for p in parents), default=0) + 1
    child.lineage_invalid = not roots  # no recoverable origin at all → invalid
    child.origin_signature = _combined_origin_signature(operator_type, roots, gap_ids, motifs)
    child.primary_origin_signature = roots[0] if roots else ""
    # carry counterevidence metadata: prefer any partial/solved status among parents
    statuses = [p.counterevidence_status for p in parents if p.counterevidence_status]
    child.counterevidence_status = statuses[0] if statuses else ""
    rem = [p.remaining_gap_scope for p in parents if p.remaining_gap_scope]
    child.remaining_gap_scope = " | ".join(dict.fromkeys(rem))[:300]
    papers: list[str] = []
    for p in parents: papers += p.counterevidence_papers
    child.counterevidence_papers = sorted(set(papers))
    edges: list[dict] = []
    for p in parents: edges += p.counterevidence_edges
    child.counterevidence_edges = edges
    child.original_gap_description = parents[0].original_gap_description
    child.downstream_gap_description = parents[0].downstream_gap_description


def _find_synthesis_candidates(
    population: list[EvolutionCandidate],
    rng: random.Random,
) -> list[EvolutionCandidate] | None:
    """Pick 2 candidates from different source gap_ids (and preferably different motif types)."""
    # First try: different motif type AND different gap_id
    by_motif: dict[str, list[EvolutionCandidate]] = {}
    for c in population:
        mt = _get_motif_type(c)
        if mt:
            by_motif.setdefault(mt, []).append(c)
    if len(by_motif) >= 2:
        selected_motifs = rng.sample(list(by_motif.keys()), 2)
        c1 = rng.choice(by_motif[selected_motifs[0]])
        # Filter pool for different gap_id to avoid recombining the same pair
        pool2 = [c for c in by_motif[selected_motifs[1]] if c.gap_id != c1.gap_id]
        if pool2:
            return [c1, rng.choice(pool2)]
    # Fallback: any two candidates with different gap_ids
    by_gap: dict[str, list[EvolutionCandidate]] = {}
    for c in population:
        by_gap.setdefault(c.gap_id, []).append(c)
    if len(by_gap) < 2:
        return None
    g1, g2 = rng.sample(list(by_gap.keys()), 2)
    return [rng.choice(by_gap[g1]), rng.choice(by_gap[g2])]


def _synthesize_cross_gap(
    candidates: list[EvolutionCandidate],
    llm: Any,
    topic_description: str,
    generation: int,
) -> tuple[EvolutionCandidate, EvolutionEvent] | None:
    """LLM call: synthesize a non-obvious hypothesis from 2 candidates with different motif types."""
    import sys

    gap_lines = []
    for i, c in enumerate(candidates):
        mt = _get_motif_type(c) or c.scope.split(";")[0].strip()
        gap_lines.append(
            f"Gap {i + 1} (motif: {mt}):\n"
            f"  Description: {c.gap}\n"
            f"  Mechanism: {c.mechanism}\n"
            f"  Target: {c.target}"
        )

    prompt = (
        "You are a senior ML researcher synthesizing novel research hypotheses.\n\n"
        f"Research area: {topic_description[:400]}\n\n"
        "The following structural gaps were detected independently from different paper perspectives:\n\n"
        + "\n\n".join(gap_lines)
        + "\n\n"
        "Your task: write a NOVEL research hypothesis that ONLY emerges from reading BOTH gaps together. "
        "It must identify something that neither gap reveals in isolation.\n\n"
        "Output JSON:\n"
        "{\n"
        '  "hypothesis": "The problem of [X] that [achieves Y] despite [challenge Z].",\n'
        '  "mechanism": "One-sentence explanation of the underlying connection between both gaps.",\n'
        '  "target": "The specific method, system, or phenomenon being targeted."\n'
        "}\n\n"
        "Output only the JSON. No markdown fences."
    )

    try:
        data, _, _, _ = llm.complete_json(
            stage="evolve",
            agent_name="cross_gap_synthesizer",
            prompt=prompt,
            schema_name="cross_gap_synthesis",
        )
        hyp_text = str(data.get("hypothesis", "")).strip().strip('"')
        mechanism = str(data.get("mechanism", "")).strip()
        target = str(data.get("target", "")).strip()
        if not hyp_text or len(hyp_text) < 20:
            return None

        merged_evidence = _dedup_evidence([ev for c in candidates for ev in c.supporting_evidence])
        merged_lineage = [cid for c in candidates for cid in c.lineage] + [c.candidate_id for c in candidates]
        merged_traceability = list({x for c in candidates for x in c.traceability_path})

        child = EvolutionCandidate(
            candidate_id=stable_id("cand", *[c.candidate_id for c in candidates], "synthesis", generation),
            gap_id=candidates[0].gap_id,
            generation=generation,
            problem_statement=hyp_text,
            gap=hyp_text,
            target=target or candidates[0].target,
            scope=f"Cross-gap synthesis (motifs: {', '.join(_get_motif_type(c) or 'unknown' for c in candidates)})",
            mechanism=mechanism or "Cross-motif synthesis: mechanism connecting independent gaps",
            supporting_evidence=merged_evidence,
            counterevidence=[],
            traceability_path=merged_traceability,
            novelty_score=min(1.0, sum(c.novelty_score for c in candidates) / len(candidates) + 0.15),
            feasibility_score=sum(c.feasibility_score for c in candidates) / len(candidates),
            impact_score=min(1.0, sum(c.impact_score for c in candidates) / len(candidates) + 0.10),
            survival_score=max(c.survival_score for c in candidates),
            lineage=merged_lineage,
            operator="cross_gap_synthesis",
        )
        _inherit_lineage_combine(child, candidates, "cross_gap_synthesis")
        # Reflect combined motifs in scope using robust origin tracking
        child.scope = f"Cross-gap synthesis (motifs: {', '.join(child.origin_motif_types) or 'unknown'})"
        event = EvolutionEvent(
            event_id=stable_id("event", child.candidate_id),
            generation=generation,
            operator="cross_gap_synthesis",
            parent_ids=[c.candidate_id for c in candidates],
            child_id=child.candidate_id,
        )
        return child, event
    except Exception as exc:
        print(f"[evolve] cross_gap_synthesis failed: {exc}", file=sys.stderr)
        return None


MUTATIONS = [
    "narrow_scope",
    "broaden_scope",
    "change_target_domain",
    "add_mechanism",
    "strengthen_evidence_requirement",
    "merge_compatible_gaps",
    "scope_narrowing",
    "scope_broadening",
    "mechanism_substitution",
    "failure_condition_swap",
    "evaluation_protocol_generation",
    "contradiction_to_benchmark",
    "limitation_to_method",
]
CROSSOVERS = [
    "combine_mechanism_and_gap",
    "merge_evidence_sets",
    "combine_target_scope",
]


def evolve_hypotheses(ctx: Any, *, generations: int | None = None, population_size: int | None = None) -> list[FinalHypothesis]:
    ctx.stage_start("evolve")
    evo_cfg = ctx.config.get("evolution", {})
    generations = int(generations if generations is not None else evo_cfg.get("generations", 5))
    population_size = int(population_size if population_size is not None else evo_cfg.get("population_size", 20))
    initial_variants_per_gap = int(evo_cfg.get("initial_variants_per_gap", 3))
    immigrants_per_gen = int(evo_cfg.get("random_immigrants_per_generation", 2))
    rng = random.Random(int(evo_cfg.get("random_seed", 13)))
    gaps = load_candidate_gaps(ctx)
    # Defense-in-depth: never let known_solved_in_corpus gaps enter evolution
    _before = len(gaps)
    gaps = [g for g in gaps if getattr(g, "counterevidence_status", "") != "known_solved_in_corpus"]
    if len(gaps) != _before:
        print(f"[evolve] excluded {_before - len(gaps)} known_solved_in_corpus gaps", flush=True)
    verified_ids, verified_source = _load_verified_evolution_gap_ids(ctx)
    gaps_before_verified_filter = len(gaps)
    if verified_source:
        gaps = [g for g in gaps if g.gap_id in verified_ids]
        print(
            f"[evolve] using verification-backed input from {verified_source}: "
            f"{len(gaps)}/{gaps_before_verified_filter} post-novelty gaps",
            flush=True,
        )
    write_json(ctx.path("evolution", "evolution_input_provenance.json"), {
        "input_policy": "verified_gaps" if verified_source else "post_novelty_gaps_no_verification_outputs_found",
        "verification_gap_id_source": verified_source or "",
        "verified_gap_ids_loaded": len(verified_ids),
        "post_novelty_gaps_available": gaps_before_verified_filter,
        "gaps_used_for_evolution": len(gaps),
        "verification_backed_only": bool(verified_source),
    })
    survival = load_survival_scores(ctx.path("verification", "gap_survival_scores.csv"))
    population = initialize_population(gaps, survival, population_size, initial_variants_per_gap=initial_variants_per_gap, rng=rng)
    if len(gaps) < 10:
        import sys
        print(f"[evolution] WARNING: only {len(gaps)} initial gaps — generating {initial_variants_per_gap} variants per gap to expand pool", file=sys.stderr)
    evaluate_population(population, evo_cfg)
    lineage: dict[str, Any] = {c.candidate_id: {"parents": [], "operator": "seed", "generation": 0} for c in population}
    # Archive every candidate ever admitted (seeds + accepted children + immigrants) so the
    # final diversity selection can backfill from distinct-origin seeds that were bred out.
    archive: dict[str, EvolutionCandidate] = {c.candidate_id: c for c in population}
    best_fitness_by_gen: list[float] = []
    write_generation(ctx, 0, population, selected=[], rejected=[])
    # Initialize LLM for cross-gap synthesis (graceful fallback if unavailable)
    _synthesis_llm: Any = None
    try:
        _synthesis_llm = LLMClient(ctx)
    except Exception:
        pass
    _topic_description = _get_topic_description(ctx)
    # Crossover threshold: 0.50 with synthesis (15% synthesis + 35% crossover), 0.35 without
    _crossover_threshold = 0.50 if _synthesis_llm is not None else 0.35
    for generation in range(1, generations + 1):
        population = sorted(population, key=lambda c: c.fitness, reverse=True)
        best_fitness_by_gen.append(population[0].fitness if population else 0.0)
        elite_count = max(1, int(population_size * float(evo_cfg.get("elite_fraction", 0.2))))
        elites = population[:elite_count]
        selected_rows = [model_dump(c) for c in elites]
        for elite in elites:
            append_jsonl(ctx.path("evolution", "selected_candidates.jsonl"), {"generation": generation, "candidate_id": elite.candidate_id, "reason": "elite"})
        children: list[EvolutionCandidate] = []
        rejected: list[dict[str, Any]] = []
        max_attempts = population_size * 30
        attempts = 0
        while len(elites) + len(children) < population_size and population and attempts < max_attempts:
            attempts += 1
            r = rng.random()
            if _synthesis_llm is not None and r < 0.15:
                synthesis_candidates = _find_synthesis_candidates(population, rng)
                result = _synthesize_cross_gap(synthesis_candidates, _synthesis_llm, _topic_description, generation) if synthesis_candidates else None
                if result:
                    child, event = result
                    append_jsonl(ctx.path("evolution", "syntheses.jsonl"), model_dump(event))
                else:
                    # Fall back to mutation when synthesis not possible or failed
                    parent = tournament(population, rng, int(evo_cfg.get("tournament_size", 3)))
                    op = rng.choice(MUTATIONS)
                    child, event = mutate(parent, op, generation)
                    append_jsonl(ctx.path("evolution", "mutations.jsonl"), model_dump(event))
            elif len(population) >= 2 and r < _crossover_threshold:
                p1 = tournament(population, rng, int(evo_cfg.get("tournament_size", 3)))
                # Enforce distinct source gap to prevent cloning the same gap pair
                other_pool = [c for c in population if c.gap_id != p1.gap_id]
                if not other_pool:
                    other_pool = [c for c in population if c.candidate_id != p1.candidate_id]
                p2 = tournament(other_pool, rng, int(evo_cfg.get("tournament_size", 3))) if other_pool else p1
                op = rng.choice(CROSSOVERS)
                child, event = crossover(p1, p2, op, generation)
                append_jsonl(ctx.path("evolution", "crossovers.jsonl"), model_dump(event))
            else:
                parent = tournament(population, rng, int(evo_cfg.get("tournament_size", 3)))
                op = rng.choice(MUTATIONS)
                child, event = mutate(parent, op, generation)
                append_jsonl(ctx.path("evolution", "mutations.jsonl"), model_dump(event))
            if is_duplicate(child, elites + children):
                reason = {"generation": generation, "candidate_id": child.candidate_id, "reason": "duplicate"}
                append_jsonl(ctx.path("evolution", "rejected_candidates.jsonl"), reason)
                rejected.append(reason)
                continue
            children.append(child)
            lineage[child.candidate_id] = {"parents": event.parent_ids, "operator": event.operator, "generation": generation}
        # Inject random immigrants to prevent premature convergence
        immigrants = _make_immigrants(gaps, survival, immigrants_per_gen, generation, rng, elites + children)
        for imm in immigrants:
            lineage[imm.candidate_id] = {"parents": [], "operator": "immigrant", "generation": generation}
        population = (elites + children + immigrants)[:population_size]
        evaluate_population(population, evo_cfg)
        for c in (children + immigrants):
            archive[c.candidate_id] = c
        write_generation(ctx, generation, population, selected=selected_rows, rejected=rejected)
    # Plateau detection logging
    _log_evolution_summary(ctx, best_fitness_by_gen, len(gaps), len(population))
    # Re-evaluate the full archive so fitness (incl. diversity bonus) is comparable, then
    # select the final set from the whole archive — not just the last generation — so
    # diverse-origin candidates that were bred out can still be chosen.
    archive_pool = list(archive.values())
    evaluate_population(archive_pool, evo_cfg)
    final = ranked_final_hypotheses(archive_pool, limit=int(evo_cfg.get("top_k_hypotheses", 20)), cfg=evo_cfg)
    final = _reformulate_hypotheses(ctx, final)
    write_json(ctx.path("evolution", "lineage.json"), lineage)
    write_json(ctx.path("final", "ranked_hypotheses.json"), [model_dump(h) for h in final])
    write_csv(ctx.path("final", "ranked_hypotheses.csv"), [model_dump(h) for h in final])
    ctx.stage_end("evolve", generations=generations, final=len(final))
    return final


def _get_topic_description(ctx: Any) -> str:
    """Resolve the topic description from venue_retrieval config or fall back to run query."""
    # Try venue_retrieval.topic_description from the retrieval config file
    retrieval_config_path = ctx.config.get("retrieval_config_path") or ctx.config.get("retrieval_config")
    if retrieval_config_path:
        from pathlib import Path
        p = Path(retrieval_config_path)
        if not p.is_absolute():
            p = Path(ctx.config.get("code_root", ".")) / p
        if p.exists():
            import yaml as _yaml
            raw = _yaml.safe_load(p.read_text()) or {}
            desc = raw.get("venue_retrieval", {}).get("topic_description", "").strip()
            if desc:
                return desc
    # Fall back to the run-level query
    return str(ctx.config.get("query", "machine learning research")).strip()


def _reformulate_hypotheses(ctx: Any, finals: list[FinalHypothesis]) -> list[FinalHypothesis]:
    """Use LLM to rewrite each hypothesis as a proper research problem statement."""
    try:
        llm = LLMClient(ctx)
    except Exception:
        return finals

    topic_description = _get_topic_description(ctx)

    for hyp in finals:
        evidence_lines = "\n".join(
            f"- [{ev.get('paper_id', '?')}] {ev.get('evidence_text', '')[:200]}"
            for ev in hyp.supporting_evidence[:5]
        ) if hasattr(hyp, 'supporting_evidence') else ""

        # Pull supporting_evidence from the FinalHypothesis if it exists
        papers_str = ", ".join(hyp.supporting_papers[:5]) if hyp.supporting_papers else "unknown"

        prompt = f"""You are a research hypothesis formulator for machine learning.

A structural gap analysis identified the following gap in papers on this topic:
{topic_description[:400]}

Gap found:

Gap description: {hyp.gap}
Target: {hyp.target}
Motif type: {hyp.scope}
Supporting papers: {papers_str}
Mechanism identified: {hyp.mechanism}

Your task: Write a single, precise research problem statement of the form:
"The problem of [designing / understanding / quantifying] [X] that [achieves property Y] despite [challenge / failure condition Z]."

Requirements:
- Be specific about what X is (a method, mechanism, or analysis)
- State Y as a measurable or observable property
- State Z as the specific failure condition or distribution shift revealed in the papers
- Do NOT use vague phrases like "investigate" or "explore"
- The statement should read as a fundable research direction, not a gap label
- Output only the problem statement sentence, nothing else.

Problem statement:"""

        try:
            data, _, _, _ = llm.complete_json(
                stage="evolve",
                agent_name="hypothesis_reformulator",
                prompt=prompt,
                schema_name="problem_statement",
            )
            raw = data.get("items", data.get("problem_statement", data.get("text", "")))
            if isinstance(raw, str) and len(raw) > 20:
                hyp.problem_statement = raw.strip().strip('"')
            elif isinstance(raw, list) and raw:
                hyp.problem_statement = str(raw[0]).strip().strip('"')
        except Exception:
            pass  # keep original template statement

    return finals


def _make_problem_statement(gap: CandidateGap) -> str:
    target = gap.target.strip()
    gap_desc = gap.gap.strip()
    # Avoid redundant "X in the context of X" when target duplicates the gap description
    if not target or target.lower() == gap_desc.lower() or target.lower() in gap_desc.lower():
        scope_hint = gap.scope.split(";")[0].replace("Motif type:", "").strip() if gap.scope else ""
        context = f"within {scope_hint}" if scope_hint else "across the evaluated corpus"
    else:
        context = f"targeting {target}"
    papers_hint = f" (attested in {len(gap.paper_ids)} paper(s))" if gap.paper_ids else ""
    return f"Investigate: {gap_desc} — {context}{papers_hint}."


def initialize_population(
    gaps: list[CandidateGap],
    survival: dict[str, dict[str, float]],
    population_size: int,
    *,
    initial_variants_per_gap: int = 1,
    rng: random.Random | None = None,
) -> list[EvolutionCandidate]:
    if rng is None:
        rng = random.Random(42)
    ranked = sorted(gaps, key=lambda g: survival.get(g.gap_id, {}).get("gap_survival_score", g.overall_score), reverse=True)
    population: list[EvolutionCandidate] = []
    # Generate multiple variants per gap to seed a larger initial pool
    _SEED_MUTATIONS = ["narrow_scope", "broaden_scope", "add_mechanism", "change_target_domain", "evaluation_protocol_generation"]
    for idx, gap in enumerate(ranked):
        if len(population) >= population_size:
            break
        surv = survival.get(gap.gap_id, {}).get("gap_survival_score", gap.overall_score)
        base_stmt = _make_problem_statement(gap)
        seed = EvolutionCandidate(
            candidate_id=stable_id("cand", gap.gap_id, "seed", idx),
            gap_id=gap.gap_id,
            generation=0,
            problem_statement=base_stmt,
            gap=gap.gap,
            target=gap.target,
            scope=gap.scope,
            mechanism=gap.mechanism,
            supporting_evidence=gap.supporting_evidence,
            counterevidence=gap.counterevidence,
            traceability_path=gap.traceability_path,
            novelty_score=gap.novelty_score,
            feasibility_score=gap.feasibility_score,
            impact_score=gap.impact_score,
            survival_score=surv,
            lineage=[gap.gap_id],
        )
        _apply_seed_lineage(seed, gap)
        population.append(seed)
        # Generate additional variants for this gap — each with a distinct problem framing
        _VARIANT_SUFFIXES = [
            " Require controlled evaluation across diverse settings.",
            " Propose a mechanism to address this gap.",
            " Generalize to adjacent tasks and domains.",
            " Design a benchmark to directly measure this gap.",
            " Provide theoretical analysis of the failure mode.",
        ]
        for v_idx in range(1, initial_variants_per_gap):
            if len(population) >= population_size:
                break
            op = _SEED_MUTATIONS[v_idx % len(_SEED_MUTATIONS)]
            variant, _ = mutate(seed, op, generation=0)
            # Ensure the variant has a distinct problem statement for dedup
            suffix = _VARIANT_SUFFIXES[(v_idx - 1) % len(_VARIANT_SUFFIXES)]
            variant.problem_statement = base_stmt + suffix
            variant.candidate_id = stable_id("cand", gap.gap_id, "seed_variant", idx, v_idx)
            variant.lineage = [gap.gap_id, seed.candidate_id]
            if not is_duplicate(variant, population):
                population.append(variant)
    return population


def _make_immigrants(
    gaps: list[CandidateGap],
    survival: dict[str, dict[str, float]],
    count: int,
    generation: int,
    rng: random.Random,
    existing: list[EvolutionCandidate],
) -> list[EvolutionCandidate]:
    """Create fresh immigrants from random gaps to prevent premature convergence."""
    if not gaps or count <= 0:
        return []
    immigrants: list[EvolutionCandidate] = []

    # Group gaps by motif type and sample one per motif to ensure diversity
    from collections import defaultdict
    by_motif: dict[str, list] = defaultdict(list)
    for g in gaps:
        by_motif[g.motif_type].append(g)
    motif_order = sorted(by_motif.keys(), key=lambda m: len(by_motif[m]), reverse=True)

    # Build a priority-ordered list: cycle through motif types to get diverse gaps
    diverse_order: list = []
    max_len = max(len(v) for v in by_motif.values()) if by_motif else 0
    for idx in range(max_len):
        for m in motif_order:
            bucket = by_motif[m]
            rng.shuffle(bucket)
            if idx < len(bucket):
                diverse_order.append(bucket[idx])

    # Fall back to random shuffle if diversity ordering produced nothing
    if not diverse_order:
        diverse_order = list(gaps)
        rng.shuffle(diverse_order)

    for gap in diverse_order:
        if len(immigrants) >= count:
            break
        surv = survival.get(gap.gap_id, {}).get("gap_survival_score", gap.overall_score)
        op = rng.choice(["narrow_scope", "broaden_scope", "add_mechanism", "change_target_domain"])
        seed = EvolutionCandidate(
            candidate_id=stable_id("cand", gap.gap_id, "immigrant_seed", generation),
            gap_id=gap.gap_id,
            generation=generation,
            problem_statement=_make_problem_statement(gap),
            gap=gap.gap,
            target=gap.target,
            scope=gap.scope,
            mechanism=gap.mechanism,
            supporting_evidence=gap.supporting_evidence,
            counterevidence=gap.counterevidence,
            traceability_path=gap.traceability_path,
            novelty_score=gap.novelty_score,
            feasibility_score=gap.feasibility_score,
            impact_score=gap.impact_score,
            survival_score=surv,
            lineage=[gap.gap_id],
            operator="immigrant",
        )
        _apply_seed_lineage(seed, gap)
        imm, _ = mutate(seed, op, generation)
        imm.candidate_id = stable_id("cand", gap.gap_id, "immigrant", generation, op)
        imm.operator = "immigrant"
        imm.operator_type = "immigrant"
        if not is_duplicate(imm, existing + immigrants):
            immigrants.append(imm)
    return immigrants


def _log_evolution_summary(ctx: Any, best_fitness_by_gen: list[float], n_gaps: int, final_pop_size: int) -> None:
    plateau_gens: list[int] = []
    for i in range(1, len(best_fitness_by_gen)):
        if abs(best_fitness_by_gen[i] - best_fitness_by_gen[i - 1]) < 0.001:
            plateau_gens.append(i)
    summary = {
        "initial_gaps": n_gaps,
        "final_population_size": final_pop_size,
        "best_fitness_by_generation": best_fitness_by_gen,
        "plateau_generations": plateau_gens,
        "plateau_detected": len(plateau_gens) > len(best_fitness_by_gen) // 2,
    }
    write_json(ctx.path("evolution", "evolution_summary.json"), summary)


def evaluate_population(population: list[EvolutionCandidate], cfg: dict[str, Any]) -> None:
    """Compute fitness for each candidate, including a diversity bonus.

    Diversity bonus rewards candidates whose problem statement is dissimilar to the
    current best candidate. This prevents the population from collapsing into one
    semantic cluster even when all base scores are equal.
    """
    weights = cfg.get("fitness_weights", {})
    diversity_weight = float(weights.get("diversity", 0.10))

    # Compute base fitness first
    for cand in population:
        evidence_density = min(1.0, len(cand.supporting_evidence) / 6.0)
        traceability = min(1.0, len(cand.traceability_path) / 5.0)
        cand.fitness = bounded(
            weights.get("novelty", 0.2) * cand.novelty_score
            + weights.get("feasibility", 0.2) * cand.feasibility_score
            + weights.get("impact", 0.2) * cand.impact_score
            + weights.get("evidence_density", 0.15) * evidence_density
            + weights.get("traceability", 0.1) * traceability
            + weights.get("survival", 0.15) * cand.survival_score
        )

    if diversity_weight <= 0 or len(population) < 2:
        return

    # Diversity bonus: average Jaccard distance from every other candidate
    # Scaled so a perfectly unique candidate gets +diversity_weight, a clone gets +0
    texts = [c.problem_statement.lower() for c in population]
    token_sets = [set(t.split()) for t in texts]
    for i, cand in enumerate(population):
        if not token_sets[i]:
            continue
        distances = []
        for j, other_tokens in enumerate(token_sets):
            if i == j or not other_tokens:
                continue
            inter = len(token_sets[i] & other_tokens)
            union = len(token_sets[i] | other_tokens)
            distances.append(1.0 - inter / union if union else 0.0)
        if distances:
            avg_distance = sum(distances) / len(distances)
            cand.fitness = bounded(cand.fitness + diversity_weight * avg_distance)


def mutate(parent: EvolutionCandidate, operator: str, generation: int) -> tuple[EvolutionCandidate, EvolutionEvent]:
    child_data = model_dump(parent)
    child_data["generation"] = generation
    child_data["operator"] = operator
    child_data["candidate_id"] = stable_id("cand", parent.candidate_id, operator, generation)
    child_data["lineage"] = [*parent.lineage, parent.candidate_id]
    if operator == "narrow_scope":
        child_data["scope"] = f"{parent.scope}; narrowed to the most traceable setting"
        child_data["feasibility_score"] = bounded(parent.feasibility_score + 0.08)
    elif operator == "broaden_scope":
        child_data["scope"] = f"{parent.scope}; broadened to adjacent tasks or datasets"
        child_data["impact_score"] = bounded(parent.impact_score + 0.08)
    elif operator == "change_target_domain":
        child_data["target"] = f"adjacent domain for {parent.target}"
        child_data["novelty_score"] = bounded(parent.novelty_score + 0.05)
    elif operator == "add_mechanism":
        child_data["mechanism"] = parent.mechanism if parent.mechanism != "insufficient evidence" else "Potential mechanism: mismatch between training/evaluation assumptions and deployment perturbations."
        child_data["feasibility_score"] = bounded(parent.feasibility_score + 0.04)
    elif operator == "strengthen_evidence_requirement":
        child_data["problem_statement"] = parent.problem_statement + " Require replication across at least two independent papers or benchmarks."
        child_data["novelty_score"] = bounded(parent.novelty_score + 0.03)
    elif operator == "merge_compatible_gaps":
        child_data["problem_statement"] = parent.problem_statement + " Merge with compatible recurring limitations when supported by traceable evidence."
    elif operator == "scope_narrowing":
        child_data["scope"] = f"{parent.scope}; narrowed to the most evidence-dense setting"
        child_data["feasibility_score"] = bounded(parent.feasibility_score + 0.07)
    elif operator == "scope_broadening":
        child_data["scope"] = f"{parent.scope}; broadened to include adjacent tasks"
        child_data["impact_score"] = bounded(parent.impact_score + 0.07)
    elif operator == "mechanism_substitution":
        child_data["mechanism"] = f"Alternative mechanism: {parent.mechanism or 'distribution mismatch between training and evaluation conditions'}"
        child_data["novelty_score"] = bounded(parent.novelty_score + 0.04)
    elif operator == "failure_condition_swap":
        child_data["target"] = f"robustness under: {parent.target}" if parent.target else parent.target
        child_data["feasibility_score"] = bounded(parent.feasibility_score + 0.03)
    elif operator == "evaluation_protocol_generation":
        child_data["problem_statement"] = parent.problem_statement + " Propose a systematic evaluation protocol across at least three diverse settings."
        child_data["specificity_score"] = bounded(getattr(parent, "specificity_score", 0.5) + 0.08)
    elif operator == "contradiction_to_benchmark":
        child_data["problem_statement"] = parent.problem_statement + " Design a benchmark to directly measure this contradiction."
        child_data["impact_score"] = bounded(parent.impact_score + 0.05)
    elif operator == "limitation_to_method":
        child_data["problem_statement"] = parent.problem_statement + " Propose a method that directly addresses this limitation."
        child_data["novelty_score"] = bounded(parent.novelty_score + 0.04)
    child = EvolutionCandidate(**child_data)
    _inherit_lineage_mutation(child, parent)
    event = EvolutionEvent(event_id=stable_id("event", child.candidate_id), generation=generation, operator=operator, parent_ids=[parent.candidate_id], child_id=child.candidate_id)
    return child, event


def crossover(p1: EvolutionCandidate, p2: EvolutionCandidate, operator: str, generation: int) -> tuple[EvolutionCandidate, EvolutionEvent]:
    data = model_dump(p1)
    data["generation"] = generation
    data["operator"] = operator
    data["candidate_id"] = stable_id("cand", p1.candidate_id, p2.candidate_id, operator, generation)
    data["lineage"] = [*p1.lineage, *p2.lineage, p1.candidate_id, p2.candidate_id]
    if operator == "combine_mechanism_and_gap":
        data["mechanism"] = p2.mechanism if p2.mechanism != "insufficient evidence" else p1.mechanism
    elif operator == "merge_evidence_sets":
        data["supporting_evidence"] = _dedup_evidence([*p1.supporting_evidence, *p2.supporting_evidence])
    elif operator == "combine_target_scope":
        data["target"] = p1.target or p2.target
        data["scope"] = f"{p1.scope}; related scope: {p2.scope}"
    data["novelty_score"] = bounded((p1.novelty_score + p2.novelty_score) / 2 + 0.02)
    data["feasibility_score"] = bounded((p1.feasibility_score + p2.feasibility_score) / 2)
    data["impact_score"] = bounded((p1.impact_score + p2.impact_score) / 2 + 0.02)
    data["survival_score"] = bounded(max(p1.survival_score, p2.survival_score))
    child = EvolutionCandidate(**data)
    _inherit_lineage_combine(child, [p1, p2], "crossover")
    event = EvolutionEvent(event_id=stable_id("event", child.candidate_id), generation=generation, operator=operator, parent_ids=[p1.candidate_id, p2.candidate_id], child_id=child.candidate_id)
    return child, event


def tournament(population: list[EvolutionCandidate], rng: random.Random, size: int) -> EvolutionCandidate:
    sample = rng.sample(population, min(size, len(population)))
    return max(sample, key=lambda c: c.fitness)


def is_duplicate(candidate: EvolutionCandidate, population: list[EvolutionCandidate], threshold: float = 0.45) -> bool:
    """Return True if candidate is too similar to any member of population.

    Three domain-agnostic checks:
    1. Word-level Jaccard on problem statement >= threshold (0.45).
    2. Same gap_id with near-identical gap + mechanism text (mutation siblings).
    3. Same gap_id + high content-word overlap: if two hypotheses from the same
       origin gap share >=60% of their content words (long non-stopwords), they
       are conceptually identical even with different surface phrasing.
    """
    ps = candidate.problem_statement.lower()
    gap = candidate.gap.lower()
    mech = candidate.mechanism.lower()
    cand_content = _content_words(ps)

    for other in population:
        # Check 1: word Jaccard on problem statement
        if _jaccard(ps, other.problem_statement.lower()) >= threshold:
            return True
        # Check 2: same gap_id + near-identical gap + mechanism (mutation siblings)
        if (candidate.gap_id == other.gap_id
                and _jaccard(gap, other.gap.lower()) >= 0.90
                and _jaccard(mech, other.mechanism.lower()) >= 0.90):
            return True
        # Check 3: same origin gap + content-word overlap >= 60%
        if candidate.gap_id == other.gap_id and cand_content:
            other_content = _content_words(other.problem_statement.lower())
            if other_content:
                overlap = len(cand_content & other_content) / len(cand_content | other_content)
                if overlap >= 0.60:
                    return True
    return False


def _content_words(text: str) -> set[str]:
    """Extract meaningful content words: tokens >=5 chars that aren't common stopwords."""
    _STOPWORDS = {
        "about", "above", "after", "again", "against", "being", "between", "could",
        "doing", "during", "every", "from", "further", "have", "having", "here",
        "itself", "might", "more", "most", "other", "over", "same", "should",
        "some", "such", "than", "that", "their", "them", "then", "there", "these",
        "they", "this", "those", "through", "under", "until", "very", "was", "were",
        "what", "when", "where", "which", "while", "will", "with", "would", "your",
        "problem", "designing", "achieves", "despite", "using", "based", "toward",
        "without", "across", "within", "proposed", "novel", "approach", "method",
        "algorithm", "framework", "system", "model", "existing", "current",
    }
    return {w for w in text.split() if len(w) >= 5 and w not in _STOPWORDS}


def load_survival_scores(path: str | Path) -> dict[str, dict[str, float]]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        gid = row.get("gap_id", "")
        out[gid] = {k: float(v) for k, v in row.items() if k != "gap_id" and v not in {"", None}}
    return out


def write_generation(ctx: Any, generation: int, population: list[EvolutionCandidate], *, selected: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> None:
    write_json(
        ctx.path("evolution", f"generation_{generation:03d}.json"),
        {"generation": generation, "population": [model_dump(c) for c in population], "selected_elites": selected, "rejected_candidates": rejected},
    )


def _semantic_cluster_key(cand: EvolutionCandidate) -> str:
    """Coarse semantic cluster key: sorted top content words of the problem statement."""
    cw = sorted(_content_words(cand.problem_statement.lower()))[:6]
    return "|".join(cw)


def _diverse_final_selection(
    population: list[EvolutionCandidate],
    limit: int,
    cfg: dict[str, Any],
) -> list[EvolutionCandidate]:
    """MMR + cap-based diverse selection over origin signatures, motifs, and clusters."""
    enforce = bool(cfg.get("enforce_origin_diversity", True))
    max_per_primary = int(cfg.get("max_per_primary_origin", 2))
    max_synth_frac = float(cfg.get("max_cross_gap_synthesis_fraction", 0.35))
    max_cluster_frac = float(cfg.get("max_same_semantic_cluster_fraction", 0.40))
    lam = float(cfg.get("mmr_lambda", 0.35))

    # Exclude lineage_invalid and any known_solved candidates upfront (fallback later if needed)
    valid = [c for c in population if not c.lineage_invalid and c.counterevidence_status != "known_solved_in_corpus"]
    pool = valid or population  # fallback if everything filtered

    selected: list[EvolutionCandidate] = []
    sel_tokens: list[set[str]] = []
    primary_counts: dict[str, int] = {}
    cluster_counts: dict[str, int] = {}
    synth_cap = int(limit * max_synth_frac) if enforce else limit
    cluster_cap = max(1, int(limit * max_cluster_frac)) if enforce else limit

    def _tok(c): return _content_words(c.problem_statement.lower())

    remaining = sorted(pool, key=lambda c: c.fitness, reverse=True)
    while remaining and len(selected) < limit:
        best = None; best_score = -1e9
        for c in remaining:
            # MMR score
            ct = _tok(c)
            sim = max((len(ct & s) / len(ct | s) if (ct | s) else 0.0) for s in sel_tokens) if sel_tokens else 0.0
            score = c.fitness - lam * sim
            if score > best_score:
                best_score = score; best = c
        c = best
        remaining.remove(c)
        if enforce:
            prim = c.primary_origin_signature or c.origin_signature
            if primary_counts.get(prim, 0) >= max_per_primary:
                continue
            clk = _semantic_cluster_key(c)
            if cluster_counts.get(clk, 0) >= cluster_cap:
                continue
            if c.operator_type in {"crossover", "cross_gap_synthesis"} and sum(1 for s in selected if s.operator_type in {"crossover","cross_gap_synthesis"}) >= synth_cap:
                continue
            primary_counts[prim] = primary_counts.get(prim, 0) + 1
            cluster_counts[clk] = cluster_counts.get(clk, 0) + 1
        selected.append(c); sel_tokens.append(_tok(c))

    # Note: caps are hard. If diversity caps prevent reaching `limit`, we return fewer
    # rather than admitting cap-violating near-duplicates. For real runs with many
    # distinct verified origins this comfortably reaches `limit`; the cap only binds in
    # degenerate single-origin populations (which SHOULD be trimmed).
    return selected[:limit]


def ranked_final_hypotheses(population: list[EvolutionCandidate], limit: int = 20, cfg: dict[str, Any] | None = None) -> list[FinalHypothesis]:
    cfg = cfg or {}
    ranked = _diverse_final_selection(population, limit, cfg)
    finals: list[FinalHypothesis] = []
    for rank, cand in enumerate(ranked, start=1):
        deduped_evidence = _dedup_evidence(cand.supporting_evidence)
        # For partially-addressed gaps, ensure remaining scope appears in the scope field
        scope = cand.scope
        if cand.counterevidence_status == "partially_addressed_in_corpus" and cand.remaining_gap_scope:
            if cand.remaining_gap_scope[:40] not in scope:
                scope = f"{scope}; remaining open scope: {cand.remaining_gap_scope}"
        finals.append(
            FinalHypothesis(
                rank=rank,
                hypothesis_id=stable_id("hypothesis", cand.candidate_id),
                problem_statement=cand.problem_statement,
                gap=cand.gap,
                target=cand.target,
                scope=scope,
                mechanism=cand.mechanism,
                supporting_papers=sorted({str(ev.get("paper_id")) for ev in deduped_evidence if ev.get("paper_id")}),
                supporting_evidence=deduped_evidence,
                counterevidence=cand.counterevidence,
                traceability_path=cand.traceability_path,
                novelty_score=cand.novelty_score,
                feasibility_score=cand.feasibility_score,
                impact_score=cand.impact_score,
                survival_score=cand.survival_score,
                fitness=cand.fitness,
                evolutionary_lineage=cand.lineage,
                origin_signature=cand.origin_signature,
                root_origin_signatures=cand.root_origin_signatures,
                primary_origin_signature=cand.primary_origin_signature,
                origin_gap_ids=cand.origin_gap_ids,
                origin_motif_types=cand.origin_motif_types,
                operator_type=cand.operator_type,
                counterevidence_status=cand.counterevidence_status,
                remaining_gap_scope=cand.remaining_gap_scope,
                counterevidence_papers=cand.counterevidence_papers,
                original_gap_description=cand.original_gap_description,
                downstream_gap_description=cand.downstream_gap_description,
            )
        )
    return finals


def _dedup_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        key = (item.get("paper_id"), item.get("evidence_text"))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _jaccard(a: str, b: str) -> float:
    sa = set(a.split())
    sb = set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
