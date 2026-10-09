from __future__ import annotations

from typing import Any, TypedDict


class QuestionPaperState(TypedDict, total=False):
    input_data: dict[str, Any]
    config: Any
    blueprint: dict[str, Any]
    candidate_questions: list[dict[str, Any]]
    tagged_questions: list[dict[str, Any]]
    duplicate_results: dict[str, dict[str, Any]]
    accepted_questions: list[dict[str, Any]]
    failed_questions: list[dict[str, Any]]
    rejected_questions: list[dict[str, Any]]
    question_memory: list[str]
    generation_session_id: str
    regeneration_round: int
    quality_report: dict[str, Any]
    final_paper: dict[str, Any]
    errors: list[dict[str, Any]]
    status: str
