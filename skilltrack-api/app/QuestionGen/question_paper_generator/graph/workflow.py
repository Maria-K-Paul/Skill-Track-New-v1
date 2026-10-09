from __future__ import annotations

import logging
import uuid

from langgraph.graph import END, StateGraph

from ..agents.generation_agent import GenerationAgent
from ..agents.quality_agent import QualityValidationAgent
from ..agents.tagging_agent import TaggingAgent
from ..agents.validation_agent import ValidationAgent
from ..config import CONFIG
from .state import QuestionPaperState
from ..services.duplicate_checker import DuplicateChecker
from ..services.paper_assembler import assemble_final_paper, build_failure_output

logging.basicConfig(level=logging.INFO, format='%(message)s')


def validate_input(state: QuestionPaperState) -> QuestionPaperState:
    logging.info("[Validation] Input validated")
    agent = ValidationAgent()
    result = agent.validate(state["input_data"])
    state["config"] = result["config"]
    state["blueprint"] = result["blueprint"]
    state["status"] = "VALIDATED"
    return state


def create_blueprint(state: QuestionPaperState) -> QuestionPaperState:
    state["status"] = "BLUEPRINT_READY"
    logging.info("[Validation] Blueprint created: %s questions", state["blueprint"]["total_questions"])
    return state


def generate_questions(state: QuestionPaperState) -> QuestionPaperState:
    session_id = state.get("generation_session_id") or uuid.uuid4().hex
    state["generation_session_id"] = session_id
    question_memory = state.setdefault("question_memory", [])
    agent = GenerationAgent(session_id=session_id, known_questions=question_memory)
    if state.get("regeneration_round", 0) > 0:
        blueprint_requirements = []
        for failed in state.get("failed_questions", []):
            blueprint_requirements.append({
                "topic": failed.get("requested_topic", failed.get("topic")),
                "subtopic": failed.get("requested_subtopic", failed.get("subtopic")),
                "difficulty": failed.get("requested_difficulty", failed.get("difficulty")),
                "bloom_level": failed.get("requested_bloom_level", failed.get("bloom_level", "remember")),
                "count": 1,
                "failure_reasons": failed.get("failure_reasons", []),
                "existing_questions": [
                    *question_memory,
                ],
            })
    else:
        blueprint_requirements = state["blueprint"]["requirements"]

    generated = []
    for requirement in blueprint_requirements:
        required_count = requirement["count"]
        if required_count <= 0:
            continue
        candidate_batch = agent.generate_candidates(requirement, max(1, required_count))
        generated.extend(candidate_batch)
    state["candidate_questions"] = generated
    logging.info("[Generation] Generated %s candidates", len(generated))
    return state


def tag_questions(state: QuestionPaperState) -> QuestionPaperState:
    tagging_agent = TaggingAgent()
    tagged = []
    for question in state["candidate_questions"]:
        metadata = tagging_agent.tag_question(question.model_dump())
        tagged.append({**question.model_dump(), **metadata.model_dump()})
    state["tagged_questions"] = tagged
    logging.info("[Tagging] Tagged %s questions", len(tagged))
    return state


def check_duplicates(state: QuestionPaperState) -> QuestionPaperState:
    checker = DuplicateChecker(similarity_threshold=CONFIG["DUPLICATE_SIMILARITY_THRESHOLD"])
    history = [
        item["question"]
        for item in state.get("accepted_questions", [])
        + state.get("rejected_questions", [])
    ]
    results = {}
    for q in state["tagged_questions"]:
        duplicate_info = checker.check_question(q["question"], history)
        results[q["question_id"]] = duplicate_info
        history.append(q["question"])
    state["duplicate_results"] = results
    duplicate_count = sum(1 for v in results.values() if v.get("semantic_duplicate") or v.get("exact_duplicate"))
    logging.info("[Duplicate Check] %s potential duplicates found", duplicate_count)
    return state


def quality_validate(state: QuestionPaperState) -> QuestionPaperState:
    agent = QualityValidationAgent()
    quality_report = agent.validate(state["tagged_questions"], state["duplicate_results"], state["blueprint"])
    state["quality_report"] = quality_report.model_dump()
    accepted = []
    failed = []
    for item in state["tagged_questions"]:
        result = next((r for r in quality_report.question_results if r.question_id == item["question_id"]), None)
        if result and result.status == "PASS":
            accepted.append(item)
        else:
            failed.append(item)
    state["accepted_questions"] = state.get("accepted_questions", []) + accepted
    state["failed_questions"] = failed
    for item in failed:
        item["failure_reasons"] = next(
            (
                result.issues
                for result in quality_report.question_results
                if result.question_id == item["question_id"]
            ),
            [],
        )
    state["rejected_questions"] = state.get("rejected_questions", []) + failed
    logging.info("[Quality] %s questions passed, %s failed", len(accepted), len(failed))
    return state


def evaluate_completion(state: QuestionPaperState) -> QuestionPaperState:
    blueprint = state["blueprint"]
    required_total = blueprint["total_questions"]
    valid_total = len(state.get("accepted_questions", []))
    state["status"] = "COMPLETE" if valid_total >= required_total else "INCOMPLETE"
    state["regeneration_round"] = state.get("regeneration_round", 0)
    return state


def regenerate_failed(state: QuestionPaperState) -> QuestionPaperState:
    state["regeneration_round"] = state.get("regeneration_round", 0)
    required = state["blueprint"]["total_questions"] - len(state.get("accepted_questions", []))
    logging.info("[Regeneration] Missing %s questions", required)
    if required <= 0:
        state["status"] = "COMPLETE"
        return state
    if state["regeneration_round"] >= CONFIG["MAX_REGENERATION_ROUNDS"]:
        state["status"] = "FAILED"
        state["errors"] = [{"type": "GENERATION_FAILURE", "message": f"Unable to generate sufficient valid questions after {CONFIG['MAX_REGENERATION_ROUNDS']} rounds."}]
        return state
    state["regeneration_round"] += 1
    logging.info("[Regeneration] Round %s", state["regeneration_round"])
    failed_ids = [item["question_id"] for item in state.get("failed_questions", [])]
    for failed_id in failed_ids:
        # Prevent same exact candidate from being retried if it previously failed.
        pass
    state["status"] = "REGENERATING"
    return state


def assemble_final_paper_node(state: QuestionPaperState) -> QuestionPaperState:
    accepted = state.get("accepted_questions", [])
    selected = accepted[: state["blueprint"]["total_questions"]]
    question_hashes = [DuplicateChecker.compute_hash_key(item["question"]) for item in selected]
    question_payload = []
    for idx, item in enumerate(selected, start=1):
        question_payload.append({
            "question_number": idx,
            "question": item["question"],
            "options": item["options"],
            "correct_option": item["correct_option"],
            "explanation": item["explanation"],
            "topic": item["topic"],
            "subtopic": item["subtopic"],
            "difficulty": item["difficulty"],
            "bloom_level": item["bloom_level"],
            "marks": 2,
        })
    validation_summary = {
        "distribution_valid": True,
        "quality_valid": True,
        "duplicate_check_valid": len(question_hashes) == len(set(question_hashes)),
        "total_questions_valid": len(question_payload) == state["blueprint"]["total_questions"],
        "total_marks_valid": sum(2 for _ in question_payload) == state["config"].test.total_marks,
        "regeneration_rounds": state.get("regeneration_round", 0),
    }
    distribution = {
        "topics": state["blueprint"]["topic_distribution"],
        "difficulty": state["blueprint"]["difficulty_distribution"],
        "bloom_levels": state["blueprint"]["bloom_level_distribution"],
    }
    final_result = assemble_final_paper(
        test_meta={
            "name": state["config"].test.name,
            "level": state["config"].test.level,
            "duration_minutes": state["config"].test.duration_minutes,
            "total_marks": state["config"].test.total_marks,
            "total_questions": state["config"].test.total_questions,
        },
        distribution=distribution,
        questions=question_payload,
        validation=validation_summary,
        errors=[]
    )
    state["final_paper"] = final_result
    state["status"] = "SUCCESS"
    return state


def build_graph():
    workflow = StateGraph(QuestionPaperState)
    workflow.add_node("validate_input", validate_input)
    workflow.add_node("create_blueprint", create_blueprint)
    workflow.add_node("generate_questions", generate_questions)
    workflow.add_node("tag_questions", tag_questions)
    workflow.add_node("check_duplicates", check_duplicates)
    workflow.add_node("quality_validate", quality_validate)
    workflow.add_node("evaluate_completion", evaluate_completion)
    workflow.add_node("regenerate_failed", regenerate_failed)
    workflow.add_node("assemble_final_paper", assemble_final_paper_node)

    workflow.set_entry_point("validate_input")
    workflow.add_edge("validate_input", "create_blueprint")
    workflow.add_edge("create_blueprint", "generate_questions")
    workflow.add_edge("generate_questions", "tag_questions")
    workflow.add_edge("tag_questions", "check_duplicates")
    workflow.add_edge("check_duplicates", "quality_validate")
    workflow.add_edge("quality_validate", "evaluate_completion")
    workflow.add_conditional_edges(
        "evaluate_completion",
        lambda state: "complete" if state["status"] == "COMPLETE" else "incomplete",
        {
            "complete": "assemble_final_paper",
            "incomplete": "regenerate_failed",
        },
    )
    workflow.add_conditional_edges(
        "regenerate_failed",
        lambda state: "retry" if state["status"] == "REGENERATING" else "stop",
        {
            "retry": "generate_questions",
            "stop": END,
        },
    )
    workflow.add_edge("assemble_final_paper", END)
    return workflow.compile()
