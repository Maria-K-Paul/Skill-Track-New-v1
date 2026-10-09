from __future__ import annotations

import uuid
import json

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableLambda, RunnableWithMessageHistory

from ..llm_factory import get_llm
from ..models.input_models import GeneratedQuestion
from ..prompts.generation_prompt import GENERATION_SYSTEM_PROMPT
from ..services.generation_memory import get_session_history


def _safe_parse_llm_response(raw_response: object) -> dict:
    if hasattr(raw_response, "content"):
        content = raw_response.content
    else:
        content = raw_response

    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    texts.append(text)
            elif isinstance(item, str):
                texts.append(item)
        content = "\n".join(texts)

    if isinstance(content, str):
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`\n ")
            if text.lower().startswith("json"):
                text = text[4:].lstrip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    if isinstance(content, dict):
        if "content" in content and len(content) == 1:
            return _safe_parse_llm_response(content["content"])
        return content

    if isinstance(content, list):
        if content and all(isinstance(item, dict) for item in content):
            return content[0]

    return {}


def _normalize_question_payload(payload: dict, requirement: dict) -> dict:
    question = payload.get("question") or payload.get("prompt") or (
        f"Which statement best describes the {requirement['subtopic']} concept in {requirement['topic']}?"
    )

    raw_options = payload.get("options", [])
    if raw_options and all(isinstance(opt, str) for opt in raw_options):
        normalized = []
        for idx, opt in enumerate(raw_options[:4], start=1):
            normalized.append({"id": chr(64 + idx), "text": str(opt)})
        options = normalized
    else:
        options = [
            {"id": str(opt.get("id", "A")), "text": str(opt.get("text", ""))}
            for opt in raw_options[:4]
        ]

    if len(options) < 4:
        filler = [
            {"id": "A", "text": f"{requirement['subtopic']} is essential to {requirement['topic']}"},
            {"id": "B", "text": f"{requirement['subtopic']} is unrelated to {requirement['topic']}"},
            {"id": "C", "text": f"{requirement['subtopic']} is only relevant outside {requirement['topic']}"},
            {"id": "D", "text": f"{requirement['subtopic']} is a random external concept"},
        ]
        for item in filler:
            if len(options) >= 4:
                break
            if item["id"] not in {opt["id"] for opt in options}:
                options.append(item)

    correct_value = payload.get("correct_option") or payload.get("answer") or "A"
    if isinstance(correct_value, int):
        correct_value = str(correct_value)

    correct_option = correct_value
    if isinstance(correct_value, str) and correct_value.isdigit() and 1 <= int(correct_value) <= len(options):
        correct_option = options[int(correct_value) - 1]["id"]
    elif isinstance(correct_value, str) and correct_value not in {opt["id"] for opt in options}:
        for opt in options:
            if str(opt.get("text", "")).lower() == correct_value.lower():
                correct_option = opt["id"]
                break

    explanation = payload.get("explanation") or (
        f"The correct answer is supported by the syllabus objective for {requirement['subtopic']} in {requirement['topic']}."
    )

    return {
        "question": question,
        "options": options,
        "correct_option": correct_option,
        "explanation": explanation,
    }


class GenerationAgent:
    def __init__(self, session_id: str | None = None, known_questions: list[str] | None = None):
        self.llm = get_llm()
        self.system_prompt = GENERATION_SYSTEM_PROMPT
        self.session_id = session_id or uuid.uuid4().hex
        self.known_questions = known_questions if known_questions is not None else []
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ])
        runnable_llm: Runnable = self.llm if isinstance(self.llm, Runnable) else RunnableLambda(self.llm.invoke)
        self.generation_chain = RunnableWithMessageHistory(
            prompt | runnable_llm,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )

    def generate_candidates(self, requirement: dict, count: int) -> list[GeneratedQuestion]:
        candidates = []
        for index in range(count):
            prompt = (
                f"Generate one high-quality MCQ for the topic '{requirement['topic']}', "
                f"subtopic '{requirement['subtopic']}', difficulty '{requirement['difficulty']}', "
                f"and Bloom level '{requirement.get('bloom_level', 'remember')}'. "
                "Return valid JSON with fields: question, options (list of {id,text} objects), "
                "correct_option, explanation. Ensure exactly 4 options with one correct answer. "
                "Keep it syllabus-aligned and non-duplicate."
            )

            if requirement.get("failure_reasons"):
                prompt += f" Avoid these issues: {requirement['failure_reasons']}"
            if requirement.get("existing_questions"):
                prompt += (
                    " Do not repeat or paraphrase any of these existing questions: "
                    f"{requirement['existing_questions']}"
                )
            if self.known_questions:
                prompt += (
                    " Do not repeat or paraphrase any question already generated in this run: "
                    f"{self.known_questions}"
                )

            llm_response = self.generation_chain.invoke(
                {"input": prompt},
                config={"configurable": {"session_id": self.session_id}},
            )
            payload = _safe_parse_llm_response(llm_response)

            if payload:
                payload = _normalize_question_payload(payload, requirement)

            if not payload:
                payload = {
                    "question": (
                        f"Which statement best describes the {requirement['subtopic']} concept in {requirement['topic']} "
                        f"for a {requirement['difficulty'].lower()} question?"
                    ),
                    "options": [
                        {"id": "A", "text": f"{requirement['subtopic']} is essential to {requirement['topic']}"},
                        {"id": "B", "text": f"{requirement['subtopic']} is unrelated to {requirement['topic']}"},
                        {"id": "C", "text": f"{requirement['subtopic']} is only relevant outside {requirement['topic']}"},
                        {"id": "D", "text": f"{requirement['subtopic']} is a random external concept"},
                    ],
                    "correct_option": "A",
                    "explanation": f"The correct answer matches the syllabus objective for {requirement['subtopic']} within {requirement['topic']}.",
                }

            candidate = GeneratedQuestion(
                question_id=f"candidate_{uuid.uuid4().hex[:8]}",
                question=payload.get("question") or (
                    f"Which statement best describes the {requirement['subtopic']} concept in {requirement['topic']}?"
                ),
                options=[
                    {"id": option.get("id", "A"), "text": option.get("text", "")}
                    for option in payload.get("options", [])[:4]
                ] or [
                    {"id": "A", "text": f"{requirement['subtopic']} is essential to {requirement['topic']}"},
                    {"id": "B", "text": f"{requirement['subtopic']} is unrelated to {requirement['topic']}"},
                    {"id": "C", "text": f"{requirement['subtopic']} is only relevant outside {requirement['topic']}"},
                    {"id": "D", "text": f"{requirement['subtopic']} is a random external concept"},
                ],
                correct_option=payload.get("correct_option") or "A",
                explanation=payload.get("explanation") or (
                    f"The correct answer matches the syllabus objective for {requirement['subtopic']} within {requirement['topic']}."
                ),
                requested_topic=requirement["topic"],
                requested_subtopic=requirement["subtopic"],
                requested_difficulty=requirement["difficulty"],
                requested_bloom_level=requirement.get("bloom_level", "remember"),
            )
            candidates.append(candidate)
            self.known_questions.append(candidate.question)
        return candidates
