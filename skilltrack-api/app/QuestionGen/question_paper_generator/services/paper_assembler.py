from __future__ import annotations

from ..models.input_models import FinalPaperOutput


def assemble_final_paper(test_meta: dict, distribution: dict, questions: list[dict], validation: dict, errors: list[dict] | None = None) -> dict:
    payload = {
        "status": "SUCCESS",
        "test": test_meta,
        "distribution": distribution,
        "questions": questions,
        "validation": validation,
        "errors": errors or [],
    }
    return FinalPaperOutput.model_validate(payload).model_dump()


def build_failure_output(test_meta: dict, errors: list[dict], required: int, valid: int, max_rounds: int) -> dict:
    return {
        "status": "FAILED",
        "test": test_meta,
        "errors": errors,
        "details": {
            "required": required,
            "valid": valid,
            "missing": max(required - valid, 0),
            "max_regeneration_rounds": max_rounds,
        },
    }
