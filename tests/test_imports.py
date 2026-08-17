from __future__ import annotations


def test_import_sgha() -> None:
    import sgha

    assert sgha.__version__


def test_import_retrieval() -> None:
    import retrieval

    assert retrieval.__all__


def test_schema_and_pipeline_modules_import() -> None:
    from sgha import extraction_schemas, gap_objects, motif_queries, verification_gate

    assert extraction_schemas.PaperExtraction
    assert gap_objects.CandidateGap
    assert motif_queries
    assert verification_gate


def test_judge_parser_module_import() -> None:
    import scripts.run_llm_judge_openrouter as judge

    assert judge.parse_model_json


def test_offline_smoke_module_import() -> None:
    import scripts.run_offline_smoke_test as smoke

    assert smoke.build_synthetic_objects
