from __future__ import annotations

from ..models.input_models import QualityReport, QuestionFailure
from ..prompts.quality_prompt import QUALITY_SYSTEM_PROMPT


class QualityValidationAgent:
    def __init__(self):
        self.system_prompt = QUALITY_SYSTEM_PROMPT

    def validate(self, candidate_questions: list[dict], duplicate_results: dict[str, dict], blueprint: dict) -> QualityReport:
        question_results = []
        failed_ids = []
        for item in candidate_questions:
            issues = []
            if item.get("question") is None or not str(item["question"]).strip():
                issues.append("Question text is empty")
            if item.get("correct_option") not in {opt["id"] for opt in item["options"]}:
                issues.append("Correct option missing from options")
            if len(item["options"]) < 4:
                issues.append("Not enough options for MCQ")
            if duplicate_results.get(item["question_id"], {}).get("semantic_duplicate"):
                issues.append("Question is semantically similar to an existing historical or current question")
            if duplicate_results.get(item["question_id"], {}).get("exact_duplicate"):
                issues.append("Question is an exact duplicate")
            if item.get("requested_topic") and item.get("requested_topic") not in {k for k in blueprint["topic_distribution"]}:
                issues.append("Question topic is outside the syllabus")
            status = "FAIL" if issues else "PASS"
            if status == "FAIL":
                failed_ids.append(item["question_id"])
            question_results.append(QuestionFailure(question_id=item["question_id"], status=status, issues=issues))
        return QualityReport(paper_status="FAIL" if failed_ids else "PASS", question_results=question_results, failed_question_ids=failed_ids)
