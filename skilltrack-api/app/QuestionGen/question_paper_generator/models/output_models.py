from __future__ import annotations

from pydantic import BaseModel, Field


class OutputValidationSummary(BaseModel):
    distribution_valid: bool = True
    quality_valid: bool = True
    duplicate_check_valid: bool = True
    total_questions_valid: bool = True
    total_marks_valid: bool = True
    regeneration_rounds: int = 0


class FinalPaperEnvelope(BaseModel):
    status: str
    test: dict
    distribution: dict
    questions: list[dict]
    validation: OutputValidationSummary
    errors: list[dict] = Field(default_factory=list)
