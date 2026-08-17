NODE_TYPES = [
    "Paper",
    "Method",
    "Task",
    "Dataset",
    "Metric",
    "Assumption",
    "Result",
    "Limitation",
    "FailureCondition",
    "Claim",
    "Gap",
    "Hypothesis",
]

EDGE_TYPES = [
    "mentions",
    "proposes",
    "evaluated_on",
    "uses_dataset",
    "measured_by",
    "improves_over",
    "fails_under",
    "assumes",
    "limited_by",
    "contradicts",
    "addresses",
    "not_addressed_by",
    "supports_gap",
    "weakens_gap",
    "has_mechanism",
    "feasible_with",
    "derived_from",
    "counterevidence_for",
    "partially_addresses_gap",
    "relaxes_assumption_of",
    "handles_failure_of",
]

RELATION_OBJECT_TYPE = {
    "evaluated_on": "Task",
    "improves_over": "Method",
    "fails_under": "FailureCondition",
    "assumes": "Assumption",
    "contradicts": "Claim",
    "uses_dataset": "Dataset",
    "measured_by": "Metric",
    "limited_by": "Limitation",
    "addresses": "Limitation",
    "not_addressed_by": "Limitation",
}

LIST_FIELD_TYPES = {
    "methods": "Method",
    "tasks": "Task",
    "datasets": "Dataset",
    "metrics": "Metric",
    "assumptions": "Assumption",
    "results": "Result",
    "limitations": "Limitation",
    "failure_conditions": "FailureCondition",
    "claims": "Claim",
    "contradictions_or_tensions": "Claim",
}

GRAPH_SCHEMA = {"node_types": NODE_TYPES, "edge_types": EDGE_TYPES}
