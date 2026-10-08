import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Attempt, Domain, Enrollment, Level, Question, User
from ..rules import current_enrollment, semester_of

log = logging.getLogger(__name__)


def get_current_assessment_result(db: Session, student_id: int, assessment_id: int | None = None) -> dict[str, Any] | None:
    query = (
        select(Attempt, Level, Domain)
        .join(Level, Level.id == Attempt.level_id)
        .join(Domain, Domain.id == Level.domain_id)
        .where(Attempt.user_id == student_id)
        .order_by(Attempt.taken_at.desc(), Attempt.id.desc())
    )
    if assessment_id is not None:
        row = db.execute(query.where(Attempt.id == assessment_id)).first()
    else:
        row = db.execute(query).first()
    if row is None:
        return None
    attempt, level, domain = row
    return {
        "id": attempt.id,
        "attempt_no": attempt.attempt_no,
        "score": attempt.score,
        "passed": attempt.passed,
        "level_id": level.id,
        "level_name": level.name,
        "domain_name": domain.name,
        "taken_at": attempt.taken_at.isoformat() if attempt.taken_at else None,
        "skill_gaps": attempt.skill_gaps or [],
        "topic_scores": attempt.topic_scores or [],
        "level_pass_mark": level.pass_mark,
    }


def get_topic_performance(db: Session, student_id: int, assessment_id: int | None = None) -> list[dict[str, Any]]:
    result = get_current_assessment_result(db, student_id, assessment_id)
    if result is None:
        return []
    latest_topics = result.get("topic_scores") or []
    if latest_topics:
        return [
            {
                "topic": item.get("topic") or "General",
                "score": float(item.get("score", 0) or 0),
                "latest_score": float(item.get("score", 0) or 0),
            }
            for item in latest_topics
        ]
    skill_gaps = result.get("skill_gaps") or []
    return [
        {"topic": item.get("topic") or "General", "score": float(item.get("score", 0) or 0), "latest_score": float(item.get("score", 0) or 0)}
        for item in skill_gaps
    ]


def get_student_history(db: Session, student_id: int, limit: int = 12) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Attempt, Level, Domain)
        .join(Level, Level.id == Attempt.level_id)
        .join(Domain, Domain.id == Level.domain_id)
        .where(Attempt.user_id == student_id)
        .order_by(Attempt.taken_at.desc(), Attempt.id.desc())
        .limit(limit)
    ).all()
    history: list[dict[str, Any]] = []
    for attempt, level, domain in rows:
        history.append(
            {
                "id": attempt.id,
                "score": attempt.score,
                "passed": attempt.passed,
                "attempt_no": attempt.attempt_no,
                "level_name": level.name,
                "domain_name": domain.name,
                "taken_at": attempt.taken_at.isoformat() if attempt.taken_at else None,
                "topic_scores": attempt.topic_scores or [],
                "skill_gaps": attempt.skill_gaps or [],
            }
        )
    return sorted(history, key=lambda item: (item["attempt_no"] or 0, item["taken_at"] or ""))


def get_difficulty_performance(db: Session, student_id: int, assessment_id: int | None = None) -> dict[str, Any] | None:
    """Difficulty performance is only available when the project records it for attempts. The current schema stores topic scores, not difficulty breakdowns."""
    return None


def get_current_level_syllabus(db: Session, student_id: int) -> list[str]:
    user = db.get(User, student_id)
    if user is None:
        return []
    enr = current_enrollment(db, user)
    if enr is None:
        return []
    level = db.scalar(select(Level).where(Level.domain_id == enr.domain_id, Level.number == enr.current_level))
    if level is None:
        return []
    return sorted({q.topic for q in db.scalars(select(Question).where(Question.level_id == level.id)) if q.topic})


def get_next_level_syllabus(db: Session, student_id: int) -> list[str]:
    user = db.get(User, student_id)
    if user is None:
        return []
    enr = current_enrollment(db, user)
    if enr is None:
        return []
    level = db.scalar(select(Level).where(Level.domain_id == enr.domain_id, Level.number == enr.current_level))
    if level is None:
        return []
    next_level = db.scalar(select(Level).where(Level.domain_id == enr.domain_id, Level.number == level.number + 1))
    if next_level is None:
        return []
    return sorted({q.topic for q in db.scalars(select(Question).where(Question.level_id == next_level.id)) if q.topic})


def get_progression_status(db: Session, student_id: int) -> dict[str, Any]:
    user = db.get(User, student_id)
    if user is None:
        return {"status": "unknown", "current_level": None, "next_level": None, "readiness": "unknown"}
    enr = current_enrollment(db, user)
    if enr is None:
        return {"status": "not_enrolled", "current_level": None, "next_level": None, "readiness": "unknown"}
    current_level_num = enr.current_level
    next_level = db.scalar(select(Level).where(Level.domain_id == enr.domain_id, Level.number == current_level_num + 1))
    return {
        "status": "on_track" if enr.status == "active" else enr.status,
        "current_level": current_level_num,
        "next_level": next_level.number if next_level else None,
        "domain_id": enr.domain_id,
        "readiness": "developing" if enr.status == "active" else enr.status,
        "semester": semester_of(user),
    }
