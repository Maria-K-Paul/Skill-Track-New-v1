from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import ActivityLog, Attempt, Domain, Enrollment, Level, Question, User
from ..rules import enrollment_status, get_settings
from ..schemas import LevelUpdate, QuestionIn

router = APIRouter(prefix="/owner", tags=["owner"])

owner_only = require_roles("owner")
content_editors = require_roles("owner", "admin")


def _my_domain(db: Session, user: User) -> Domain:
    domain = db.scalar(select(Domain).where(Domain.owner_id == user.id))
    if domain is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No domain is assigned to you")
    return domain


def _my_level(db: Session, user: User, level_id: int) -> Level:
    level = db.get(Level, level_id)
    if level is None or (user.role == "owner" and level.domain.owner_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Level not found in your domain")
    return level


def _bank_counts(db: Session, level_ids: list[int]) -> dict[int, dict[str, int]]:
    counts = {lid: {"easy": 0, "medium": 0, "hard": 0} for lid in level_ids}
    rows = db.execute(
        select(Question.level_id, Question.difficulty, func.count(Question.id))
        .where(Question.level_id.in_(level_ids)).group_by(Question.level_id, Question.difficulty)
    ).all()
    for level_id, difficulty, n in rows:
        counts[level_id][difficulty] = n
    return counts


def _level_out(level: Level, bank: dict[str, int]) -> dict:
    return {
        "id": level.id, "number": level.number, "name": level.name,
        "question_count": level.question_count, "pass_mark": level.pass_mark, "duration_min": level.duration_min,
        "easy_pct": level.easy_pct, "medium_pct": level.medium_pct, "hard_pct": level.hard_pct,
        "bank": bank,
    }


@router.get("/overview")
def overview(user: User = Depends(owner_only), db: Session = Depends(get_db)):
    domain = _my_domain(db, user)
    max_attempts = get_settings(db)["max_attempts"]
    levels = domain.levels
    level_by_number = {lv.number: lv for lv in levels}
    bank = _bank_counts(db, [lv.id for lv in levels])

    attempts = db.scalars(select(Attempt).where(Attempt.level_id.in_([lv.id for lv in levels]))).all()
    attempt_count: dict[tuple[int, int], int] = {}
    for a in attempts:
        key = (a.user_id, a.level_id)
        attempt_count[key] = attempt_count.get(key, 0) + 1

    rows = db.execute(
        select(Enrollment, User).join(User, User.id == Enrollment.user_id)
        .where(Enrollment.domain_id == domain.id).order_by(User.name)
    ).all()
    students = []
    for enr, student in rows:
        current = level_by_number.get(enr.current_level)
        used = attempt_count.get((student.id, current.id), 0) if current else 0
        state = enrollment_status(enr, len(levels), used, max_attempts)
        students.append({
            "id": student.id, "name": student.name, "reg_no": student.reg_no, "semester": student.semester,
            "department": student.department, "level": enr.current_level if current else None,
            "attempts": used, "points": enr.points, "status": state,
        })

    return {
        "domain": {"id": domain.id, "name": domain.name},
        "max_attempts": max_attempts,
        "students": students,
        "levels": [_level_out(lv, bank[lv.id]) for lv in levels],
    }


@router.patch("/levels/{level_id}")
def update_level(level_id: int, body: LevelUpdate, user: User = Depends(content_editors), db: Session = Depends(get_db)):
    level = _my_level(db, user, level_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(level, field, value)
    if level.easy_pct + level.medium_pct + level.hard_pct != 100:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Difficulty split must add up to 100%")
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} updated settings for {level.name}"))
    db.commit()
    return _level_out(level, _bank_counts(db, [level.id])[level.id])


@router.get("/levels/{level_id}/questions")
def list_questions(level_id: int, user: User = Depends(content_editors), db: Session = Depends(get_db)):
    level = _my_level(db, user, level_id)
    questions = db.scalars(select(Question).where(Question.level_id == level.id).order_by(Question.id)).all()
    return [
        {
            "id": q.id, "text": q.text, "options": q.options, "answer_index": q.answer_index,
            "difficulty": q.difficulty, "topic": q.topic,
        }
        for q in questions
    ]


@router.post("/levels/{level_id}/questions", status_code=status.HTTP_201_CREATED)
def add_question(level_id: int, body: QuestionIn, user: User = Depends(content_editors), db: Session = Depends(get_db)):
    level = _my_level(db, user, level_id)
    q = Question(
        level_id=level.id, text=body.text.strip(), options=[o.strip() for o in body.options],
        answer_index=body.answer_index, difficulty=body.difficulty, topic=(body.topic or "").strip() or None,
    )
    db.add(q)
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} added a {body.difficulty} question to {level.name}"))
    db.commit()
    return {"id": q.id}


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: int, user: User = Depends(content_editors), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    _my_level(db, user, q.level_id)

    # Check if question is in any active exam session
    from sqlalchemy import func
    from ..models import ExamSession
    active_session_count = db.scalar(
        select(func.count(ExamSession.id))
        .where(ExamSession.submitted_at.is_(None))
        .where(func.json_array_length(ExamSession.question_ids) > 0)
    )
    # Note: SQLAlchemy/PostgreSQL JSON array containment would need custom implementation
    # For safety, we'll just warn if ANY active sessions exist
    if active_session_count and active_session_count > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot delete question - there are {active_session_count} active exam session(s). "
            "Please wait for all exams to complete before deleting questions."
        )

    db.delete(q)
    db.commit()
