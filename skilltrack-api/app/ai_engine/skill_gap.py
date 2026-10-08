import json
import logging
from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .. import ai
from ..models import SkillGapAnalysis
from .schemas import PreparationRecommendation, SkillGap, SkillGapReport
from .tools import (
    get_current_assessment_result,
    get_current_level_syllabus,
    get_difficulty_performance,
    get_next_level_syllabus,
    get_progression_status,
    get_student_history,
    get_topic_performance,
)

log = logging.getLogger(__name__)


def classify_gap(score: float, history: list[float] | None = None) -> str:
    if score >= 80:
        return "MASTERED"
    if history and len(history) >= 2:
        recent = history[-3:]
        if recent and score >= max(recent) - 5 and score >= 65:
            return "IMPROVING"
        if recent and score <= min(recent) - 8:
            return "REGRESSED"
        if len(history) >= 3 and sum(recent) / len(recent) < 60:
            return "PERSISTENT"
    if score < 60:
        return "CURRENT"
    return "CURRENT"


def analyze_trend(scores: list[float]) -> str:
    if len(scores) < 2:
        return "INSUFFICIENT_DATA"
    if max(scores) - min(scores) <= 8:
        return "STABLE"
    if scores[-1] > scores[0] + 10:
        return "IMPROVING"
    if scores[-1] < scores[0] - 10:
        return "DECLINING"
    return "VOLATILE"


def calculate_severity(score: float, next_level_relevance: bool = False) -> str:
    if score < 35 or (next_level_relevance and score < 55):
        return "HIGH"
    if score < 60:
        return "MEDIUM"
    return "LOW"


def calculate_confidence(history: list[dict] | None = None, score: float | None = None) -> str:
    if not history or len(history) < 2:
        return "LOW"
    if len(history) >= 3 and score is not None and score >= 40:
        return "HIGH"
    return "MEDIUM"


def _latest_scores(history: list[dict]) -> list[float]:
    return [float(item.get("score", 0) or 0) for item in history]


def _build_evidence(student_id: int, assessment_id: int | None, db: Session) -> dict:
    current_result = get_current_assessment_result(db, student_id, assessment_id)
    history = get_student_history(db, student_id)
    topic_performance = get_topic_performance(db, student_id, assessment_id)
    difficulty_performance = get_difficulty_performance(db, student_id, assessment_id)
    current_syllabus = get_current_level_syllabus(db, student_id)
    next_level_syllabus = get_next_level_syllabus(db, student_id)
    progression = get_progression_status(db, student_id)
    return {
        "current_result": current_result,
        "topic_performance": topic_performance,
        "history": history,
        "difficulty_performance": difficulty_performance,
        "current_syllabus": current_syllabus,
        "next_level_syllabus": next_level_syllabus,
        "progression_status": progression,
        "deterministic_analysis": {
            "trend": analyze_trend(_latest_scores(history)),
            "confidence": calculate_confidence(history, (current_result or {}).get("score")),
        },
    }


def _deterministic_gap_payload(student_id: int, db: Session, current_result: dict | None, history: list[dict], topic_performance: list[dict], next_level_syllabus: list[str]) -> tuple[list[dict], list[str], list[dict], list[str]]:
    if current_result is None:
        return [], [], [], []

    current_score = float(current_result.get("score", 0) or 0)
    topic_map = {item["topic"]: float(item.get("score", 0) or 0) for item in topic_performance}
    history_scores = _latest_scores(history)
    trend = analyze_trend(history_scores)
    next_set = {t.lower() for t in next_level_syllabus}

    gap_entries: list[dict] = []
    strengths: list[str] = []

    for topic, score in sorted(topic_map.items(), key=lambda item: item[1]):
        history_for_topic = [
            float(item.get("topic_scores", [{}])[0].get("score", 0)) for item in history if any(t.get("topic") == topic for t in item.get("topic_scores", []))
        ]
        if history_for_topic:
            history_for_topic = [
                float(match.get("score", 0) or 0)
                for item in history
                for match in item.get("topic_scores", [])
                if match.get("topic") == topic
            ]
        else:
            history_for_topic = []

        if score >= 70:
            strengths.append(f"{topic} is a relative strength at {score:.0f}%")
            continue

        relevance = any(topic.lower() in next_set for _ in [0])
        severity = calculate_severity(score, relevance)
        confidence = calculate_confidence(history, score)
        gap_entries.append(
            {
                "topic": topic,
                "score": round(score, 1),
                "classification": classify_gap(score, history_for_topic or history_scores),
                "severity": severity,
                "confidence": confidence,
                "trend": trend,
                "reason": (
                    f"{topic} scored {score:.0f}% on the latest assessment; it is {('heavily required' if relevance else 'relevant')} in the next level transition "
                    f"and the recent trend is {trend.lower()}."
                ),
                "priority": 1 if relevance else 2,
            }
        )

    gap_entries.sort(key=lambda item: (item["priority"], item["score"]))
    strengths = strengths[:5]

    recommendations: list[dict] = []
    for gap in gap_entries[:3]:
        topic = gap["topic"]
        prereqs = [
            f"Review the core concepts behind {topic}",
            f"Practice targeted problems in {topic}",
            "Check the underlying misconception before moving to harder application questions",
        ]
        actions = [
            f"Complete 5 short drills in {topic}",
            f"Do 2 mixed-practice questions that rely on {topic}",
            "Re-test the same topic in a fresh mock exercise",
        ]
        recommendations.append(
            {
                "topic": topic,
                "reason": gap["reason"],
                "prerequisites": prereqs,
                "actions": actions,
            }
        )

    priority_topics = [entry["topic"] for entry in gap_entries[:3]]
    return gap_entries, strengths, recommendations, priority_topics


def run_skill_gap_agent(student_id: int, assessment_id: int | None = None, db: Session | None = None) -> dict:
    if db is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Database session is required")

    log.info("Skill Gap Agent started for student %s", student_id)
    evidence = _build_evidence(student_id, assessment_id, db)
    current_result = evidence["current_result"]
    if current_result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No assessment result found for this student")

    log.info("Evidence retrieved for student %s", student_id)
    topic_performance = evidence["topic_performance"]
    history = evidence["history"]
    next_level_syllabus = evidence["next_level_syllabus"]

    gap_entries, strengths, recommendations, priority_topics = _deterministic_gap_payload(
        student_id, db, current_result, history, topic_performance, next_level_syllabus
    )

    if not gap_entries and current_result.get("score", 0) >= 60:
        gap_entries = [{
            "topic": "General readiness",
            "score": float(current_result.get("score", 0) or 0),
            "classification": "MASTERED",
            "severity": "LOW",
            "confidence": calculate_confidence(history, current_result.get("score")),
            "trend": analyze_trend(_latest_scores(history)),
            "reason": "Current result is strong enough that no obvious priority gap is present in the available evidence.",
            "priority": 3,
        }]

    if not strengths:
        strengths = [f"Current assessment score is {current_result.get('score', 0)}% and the student is in progress."]

    prompt = (
        "You are a Skill Gap Analysis Agent.\n\n"
        "You are given verified student assessment evidence. Database evidence and deterministic calculations are authoritative.\n"
        "Never invent scores, topics, syllabus items, previous attempts, or difficulty results.\n\n"
        f"Current result: {json.dumps(current_result, default=str)}\n"
        f"Topic performance: {json.dumps(topic_performance, default=str)}\n"
        f"History: {json.dumps(history, default=str)}\n"
        f"Difficulty performance: {json.dumps(evidence['difficulty_performance'], default=str)}\n"
        f"Current syllabus: {json.dumps(evidence['current_syllabus'], default=str)}\n"
        f"Next level syllabus: {json.dumps(next_level_syllabus, default=str)}\n"
        f"Deterministic analysis: {json.dumps({'gaps': gap_entries, 'strengths': strengths, 'recommendations': recommendations}, default=str)}\n\n"
        "Interpret the evidence and produce a concise, actionable skill-gap summary. "
        "Do not merely repeat low scores. Distinguish current weaknesses, persistent weaknesses, improving skills, declining skills, and next-level risk. "
        "Return valid structured JSON matching the supplied schema."
    )

    log.info("Gemini reasoning started")
    report = ai.generate(prompt, SkillGapReport)
    log.info("Gemini reasoning completed")

    if not getattr(report, "gaps", None):
        report.gaps = [SkillGap(**gap) for gap in gap_entries]
    if not getattr(report, "next_level_priorities", None):
        report.next_level_priorities = [PreparationRecommendation(**rec) for rec in recommendations]
    if not getattr(report, "priority_topics", None):
        report.priority_topics = priority_topics
    if not getattr(report, "recommended_plan", None):
        report.recommended_plan = [
            "Review the current weak topics with a timed drill session.",
            "Revisit next-level concepts that appear in the current assessment gaps.",
            "Complete a targeted mock exercise before the next assessment.",
        ]

    payload = {
        "overall_summary": report.overall_summary,
        "readiness": report.readiness,
        "strengths": report.strengths,
        "gaps": [g.model_dump() for g in report.gaps],
        "next_level_priorities": [r.model_dump() for r in report.next_level_priorities],
        "recommended_plan": report.recommended_plan,
        "priority_topics": report.priority_topics,
        "confidence": calculate_confidence(history, current_result.get("score")),
        "assessment_id": current_result["id"],
    }

    record = SkillGapAnalysis(
        user_id=student_id,
        assessment_id=current_result["id"],
        overall_summary=payload["overall_summary"],
        readiness=payload["readiness"],
        strengths=payload["strengths"],
        gaps=payload["gaps"],
        next_level_priorities=payload["next_level_priorities"],
        recommended_plan=payload["recommended_plan"],
        priority_topics=payload["priority_topics"],
        confidence=payload["confidence"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    payload["id"] = record.id
    payload["created_at"] = record.created_at.isoformat()
    log.info("Skill Gap Agent completed for student %s", student_id)
    return payload
