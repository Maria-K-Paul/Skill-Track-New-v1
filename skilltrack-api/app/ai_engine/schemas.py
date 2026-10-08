from typing import Literal

from pydantic import BaseModel, Field


class SkillGap(BaseModel):
    topic: str
    score: float = Field(ge=0, le=100)
    classification: str
    severity: str
    confidence: str
    trend: str
    reason: str
    priority: int = Field(ge=1)


class PreparationRecommendation(BaseModel):
    topic: str
    reason: str
    prerequisites: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class SkillGapReport(BaseModel):
    overall_summary: str
    readiness: Literal["READY", "DEVELOPING", "NOT_READY"]
    strengths: list[str] = Field(default_factory=list)
    gaps: list[SkillGap] = Field(default_factory=list)
    next_level_priorities: list[PreparationRecommendation] = Field(default_factory=list)
    recommended_plan: list[str] = Field(default_factory=list)
    priority_topics: list[str] = Field(default_factory=list)
