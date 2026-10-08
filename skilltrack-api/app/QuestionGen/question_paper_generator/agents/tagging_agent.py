from __future__ import annotations

from ..models.input_models import TaggedQuestion
from ..prompts.tagging_prompt import TAGGING_SYSTEM_PROMPT


class TaggingAgent:
    def __init__(self):
        self.system_prompt = TAGGING_SYSTEM_PROMPT

    def tag_question(self, question: dict) -> TaggedQuestion:
        topic = question.get("requested_topic") or "General"
        subtopic = question.get("requested_subtopic") or "General"
        difficulty = question.get("requested_difficulty") or "Medium"
        bloom_level = question.get("requested_bloom_level") or "remember"
        return TaggedQuestion(
            question_id=question["question_id"],
            topic=topic,
            subtopic=subtopic,
            difficulty=difficulty,
            bloom_level=bloom_level,
        )
