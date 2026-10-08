from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TestDetails(BaseModel):
    name: str
    level: int
    duration_minutes: int
    total_marks: int
    total_questions: int


class TopicInput(BaseModel):
    name: str
    weightage: int
    subtopics: list["SubtopicInput"]


class SubtopicInput(BaseModel):
    name: str
    weightage: int


class SyllabusInput(BaseModel):
    topics: list[TopicInput]


class DifficultyRatio(BaseModel):
    Easy: int = Field(..., ge=0)
    Medium: int = Field(..., ge=0)
    Hard: int = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_total(self):
        if self.Easy + self.Medium + self.Hard != 100:
            raise ValueError("Difficulty ratios must sum to 100")
        return self


class BloomLevelRatio(BaseModel):
    remember: int = Field(0, ge=0)
    understand: int = Field(0, ge=0)
    apply: int = Field(0, ge=0)
    analyze: int = Field(0, ge=0)
    evaluate: int = Field(0, ge=0)
    create: int = Field(0, ge=0)

    @model_validator(mode="after")
    def validate_total(self):
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("Bloom level ratios must contain at least one positive value")
        return self


class QuestionDistribution(BaseModel):
    MCQ: int


class MarksDistribution(BaseModel):
    MCQ: int


class QuestionConstraints(BaseModel):
    minimum_options_for_mcq: int = 4
    allow_multiple_correct_answers: bool = False
    negative_marking: bool = False
    negative_marks: int = 0
    allow_partial_marking: bool = False


class OutputRequirements(BaseModel):
    include_answer_key: bool = True
    include_explanations: bool = True
    include_topic_tags: bool = True
    include_difficulty: bool = True
    include_marks: bool = True


class PaperConfig(BaseModel):
    test: TestDetails
    syllabus: SyllabusInput
    difficulty_ratio: DifficultyRatio
    bloom_level_ratio: BloomLevelRatio = Field(default_factory=lambda: BloomLevelRatio(remember=100))
    question_distribution: QuestionDistribution
    marks_distribution: MarksDistribution
    question_constraints: QuestionConstraints
    output_requirements: OutputRequirements

    @model_validator(mode="after")
    def validate_structure(self):
        if self.test.total_questions <= 0:
            raise ValueError("total_questions must be > 0")
        if self.test.total_marks <= 0:
            raise ValueError("total_marks must be > 0")
        if self.test.duration_minutes <= 0:
            raise ValueError("duration_minutes must be > 0")
        if self.question_distribution.MCQ != self.test.total_questions:
            raise ValueError("MCQ question count must match total_questions")
        if self.marks_distribution.MCQ * self.question_distribution.MCQ != self.test.total_marks:
            raise ValueError("MCQ marks * count must equal total_marks")

        topic_sum = sum(topic.weightage for topic in self.syllabus.topics)
        if topic_sum != 100:
            raise ValueError("Topic weightages must sum to 100")
        for topic in self.syllabus.topics:
            if not topic.subtopics:
                raise ValueError(f"Topic '{topic.name}' must have at least one subtopic")
            subtopic_sum = sum(subtopic.weightage for subtopic in topic.subtopics)
            if subtopic_sum != 100:
                raise ValueError(f"Subtopic weightages for topic '{topic.name}' must sum to 100")
        return self


class QuestionOption(BaseModel):
    id: str
    text: str


class GeneratedQuestion(BaseModel):
    question_id: str
    question: str
    options: list[QuestionOption]
    correct_option: str
    explanation: str
    requested_topic: str | None = None
    requested_subtopic: str | None = None
    requested_difficulty: str | None = None
    requested_bloom_level: str | None = None


class TaggedQuestion(BaseModel):
    question_id: str
    topic: str
    subtopic: str
    difficulty: str
    bloom_level: str


class QuestionFailure(BaseModel):
    question_id: str
    status: Literal["PASS", "FAIL"]
    issues: list[str] = Field(default_factory=list)


class QualityReport(BaseModel):
    paper_status: Literal["PASS", "FAIL"]
    question_results: list[QuestionFailure]
    failed_question_ids: list[str] = Field(default_factory=list)


class BlueprintRequirement(BaseModel):
    topic: str
    subtopic: str
    difficulty: str
    bloom_level: str
    count: int


class Blueprint(BaseModel):
    total_questions: int
    topic_distribution: dict[str, int]
    difficulty_distribution: dict[str, int]
    bloom_level_distribution: dict[str, int]
    requirements: list[BlueprintRequirement]


class FinalQuestionRecord(BaseModel):
    question_number: int
    question: str
    options: list[QuestionOption]
    correct_option: str
    explanation: str
    topic: str
    subtopic: str
    difficulty: str
    bloom_level: str
    marks: int


class FinalPaperOutput(BaseModel):
    status: str
    test: dict
    distribution: dict
    questions: list[FinalQuestionRecord]
    validation: dict
    errors: list[dict] = Field(default_factory=list)
