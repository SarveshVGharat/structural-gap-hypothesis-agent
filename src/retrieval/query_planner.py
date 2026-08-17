"""Query planner: natural language query → RetrievalPlan with multiple facets."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import RetrievalFacet, RetrievalPlan

# Core ML/NLP categories we target by default
DEFAULT_CATEGORIES = ["cs.LG", "cs.CL", "cs.AI", "stat.ML"]

# Off-topic exclusion signals for ML/NLP papers
_BIOLOGY_TERMS = ["protein", "cell", "gene", "genomic", "cancer", "clinical", "pathology", "disease"]
_CHEMISTRY_TERMS = ["molecule", "synthesis", "chemical", "reaction", "drug", "pharmacology"]
_ROBOTICS_TERMS = ["robot", "manipulation", "locomotion", "gripper", "embodied control"]
_VISION_HARDWARE_TERMS = ["FPGA", "circuit", "antenna", "radar", "LIDAR", "microcontroller"]

_DEFAULT_EXCLUDES = _BIOLOGY_TERMS + _CHEMISTRY_TERMS


def plan_query(
    query: str,
    *,
    min_year: int = 2022,
    categories: list[str] | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str = "EMPTY",
    llm_timeout: float = 60.0,
) -> RetrievalPlan:
    cats = categories or DEFAULT_CATEGORIES
    if llm_base_url:
        try:
            plan = _llm_plan(query, min_year=min_year, categories=cats, base_url=llm_base_url, model=llm_model or "Qwen/Qwen3.5-9B", api_key=llm_api_key, timeout=llm_timeout)
            plan.strategy = "llm"
            return plan
        except Exception:
            pass
    plan = _rule_based_plan(query, min_year=min_year, categories=cats)
    plan.strategy = "rule_based"
    return plan


def _rule_based_plan(query: str, *, min_year: int, categories: list[str]) -> RetrievalPlan:
    tokens = _tokenize(query)
    core_terms = _extract_core_terms(tokens)
    facets: list[RetrievalFacet] = []

    # Facet 1: core query — broadest match
    facets.append(RetrievalFacet(
        facet_id="f1",
        label="core topic",
        keywords=core_terms[:5],
        must_include_any=core_terms[:3],
        must_exclude=list(_DEFAULT_EXCLUDES),
        categories=categories,
        min_year=min_year,
    ))

    # Facet 2: robustness / failure / limitation angle
    robustness_hints = [t for t in tokens if t in {"robustness", "robust", "sensitivity", "perturbation", "instability", "failure", "brittle"}]
    if robustness_hints or "robustness" in query.lower() or "sensitivity" in query.lower():
        facets.append(RetrievalFacet(
            facet_id="f2",
            label="robustness and sensitivity",
            keywords=core_terms[:3] + ["robustness", "sensitivity", "perturbation"],
            must_include_any=["robustness", "sensitivity", "perturbation", "stability", "brittle"],
            must_exclude=list(_DEFAULT_EXCLUDES),
            categories=[c for c in categories if c in {"cs.LG", "cs.CL", "stat.ML"}],
            min_year=min_year,
        ))

    # Facet 3: empirical analysis / evaluation angle
    facets.append(RetrievalFacet(
        facet_id="f3",
        label="empirical evaluation and benchmarking",
        keywords=core_terms[:3] + ["evaluation", "benchmark", "analysis"],
        must_include_any=["evaluation", "benchmark", "analysis", "empirical", "experiment"],
        must_exclude=list(_DEFAULT_EXCLUDES),
        categories=[c for c in categories if c in {"cs.LG", "cs.CL", "stat.ML"}],
        min_year=min_year,
    ))

    # Facet 4: theory / mechanism angle
    theory_hints = [t for t in tokens if t in {"mechanism", "theory", "theoretical", "understanding", "why", "analysis"}]
    if theory_hints or "understanding" in query.lower() or "mechanism" in query.lower():
        facets.append(RetrievalFacet(
            facet_id="f4",
            label="theoretical understanding",
            keywords=core_terms[:3] + ["theory", "understanding", "mechanism"],
            must_include_any=["theory", "theoretical", "understanding", "mechanism", "why", "analysis"],
            must_exclude=list(_DEFAULT_EXCLUDES),
            categories=[c for c in categories if c in {"cs.LG", "cs.CL", "stat.ML"}],
            min_year=min_year,
        ))

    # Facet 5: improvement / method angle
    facets.append(RetrievalFacet(
        facet_id="f5",
        label="methods and improvements",
        keywords=core_terms[:3] + ["method", "improvement", "approach"],
        must_include_any=core_terms[:2] + ["improve", "method", "approach", "propose"],
        must_exclude=list(_DEFAULT_EXCLUDES),
        categories=categories,
        min_year=min_year,
    ))

    return RetrievalPlan(original_query=query, facets=facets)


def _llm_plan(query: str, *, min_year: int, categories: list[str], base_url: str, model: str, api_key: str, timeout: float) -> RetrievalPlan:
    from openai import OpenAI

    prompt_template_path = Path(__file__).parent / "prompts" / "query_planner_prompt.txt"
    template = prompt_template_path.read_text()
    prompt = template.format(query=query, min_year=min_year, categories=", ".join(categories))

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You return strict JSON only. No markdown fences."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=2048,
    )
    msg = response.choices[0].message
    content = (msg.content or "").strip()

    # Handle thinking models (reasoning in model_extra)
    if not content or content == "{}":
        reasoning = (msg.model_extra or {}).get("reasoning", "") or ""
        if reasoning:
            response2 = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You return strict JSON only. No markdown fences."},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "I have planned the retrieval."},
                    {"role": "user", "content": f"Based on this plan:\n{reasoning}\n\nOutput the final JSON only."},
                ],
                temperature=0.0,
                max_tokens=2048,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            content = (response2.choices[0].message.content or "{}").strip()

    raw = _extract_json(content)
    data = json.loads(raw)
    facets = [
        RetrievalFacet(
            facet_id=f.get("facet_id", f"f{i+1}"),
            label=f.get("label", f"facet {i+1}"),
            keywords=f.get("keywords", []),
            must_include_any=f.get("must_include_any", []),
            must_exclude=f.get("must_exclude", list(_DEFAULT_EXCLUDES)),
            categories=f.get("categories", categories),
            min_year=int(f.get("min_year", min_year)),
        )
        for i, f in enumerate(data.get("facets", []))
    ]
    if not facets:
        raise ValueError("LLM returned no facets")
    return RetrievalPlan(original_query=query, facets=facets)


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.split(r"\W+", text) if len(w) > 2]


def _extract_core_terms(tokens: list[str]) -> list[str]:
    stopwords = {"the", "and", "for", "with", "from", "this", "that", "are", "was", "has", "can", "its"}
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in stopwords and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _extract_json(text: str) -> str:
    """Extract first JSON object from text."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return text[start:end + 1]
    return text
