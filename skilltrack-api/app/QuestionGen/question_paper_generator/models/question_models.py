from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class QuestionMetadata(BaseModel):
    question_id: str
    topic: str
    subtopic: str
    difficulty: str
    marks: int = 2
    test_name: str | None = None
    test_level: int | None = None
    created_at: str | None = None


class DuplicateCheckResult(BaseModel):
    question_id: str
    duplicates: list[str] = []
    semantic_duplicates: list[str] = []
    exact_duplicate: bool = False
    semantic_duplicate: bool = False
    notes: list[str] = []


class CandidateQuestionContainer(BaseModel):
    question_id: str
    question: str
    options: list[dict[str, str]]
    correct_option: str
    explanation: str
    requested_topic: str | None = None
    requested_subtopic: str | None = None
    requested_difficulty: str | None = None
    metadata: dict[str, Any] = {}
