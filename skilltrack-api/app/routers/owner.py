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
    topics_out = []
    for t in level.topics:
        topics_out.append({
            "id": t.id, "name": t.name, "weightage": t.weightage,
            "subtopics": [{"id": st.id, "name": st.name, "weightage": st.weightage} for st in t.subtopics]
        })
    return {
        "id": level.id, "number": level.number, "name": level.name,
        "question_count": level.question_count, "pass_mark": level.pass_mark, "duration_min": level.duration_min,
        "easy_pct": level.easy_pct, "medium_pct": level.medium_pct, "hard_pct": level.hard_pct,
        "bloom_level_ratio": level.bloom_level_ratio or {"remember": 100},
        "question_generation_status": level.question_generation_status,
        "topics": topics_out,
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

from ..models import SyllabusTopic, SyllabusSubtopic
from ..schemas import SyllabusUpdate

@router.put("/levels/{level_id}/syllabus")
def update_syllabus(level_id: int, body: SyllabusUpdate, user: User = Depends(content_editors), db: Session = Depends(get_db)):
    level = _my_level(db, user, level_id)
    
    level.bloom_level_ratio = body.bloom_level_ratio
    
    new_topics = []
    for t_in in body.topics:
        topic = SyllabusTopic(name=t_in.name, weightage=t_in.weightage)
        new_topics.append(topic)
        for st_in in t_in.subtopics:
            topic.subtopics.append(SyllabusSubtopic(name=st_in.name, weightage=st_in.weightage))
    
    level.topics = new_topics
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} updated syllabus for {level.name}"))
    db.commit()
    db.refresh(level)
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

@router.put("/questions/{question_id}")
def edit_question(question_id: int, body: QuestionIn, user: User = Depends(content_editors), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    level = _my_level(db, user, q.level_id)
    
    q.text = body.text.strip()
    q.options = [o.strip() for o in body.options]
    q.answer_index = body.answer_index
    q.difficulty = body.difficulty
    q.topic = (body.topic or "").strip() or None
    
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} edited a question in {level.name}"))
    db.commit()
    return {"id": q.id}


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: int, user: User = Depends(content_editors), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    _my_level(db, user, q.level_id)
    db.delete(q)
    db.commit()


@router.delete("/levels/{level_id}/questions", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_questions(level_id: int, user: User = Depends(content_editors), db: Session = Depends(get_db)):
    level = _my_level(db, user, level_id)
    db.execute(select(Question).where(Question.level_id == level.id)) # to verify they exist? not needed.
    
    # Actually delete them
    from sqlalchemy import delete
    db.execute(delete(Question).where(Question.level_id == level.id))
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} deleted all questions for {level.name}"))
    db.commit()


from fastapi import BackgroundTasks
import json
import logging
from ..QuestionGen.question_gen import run_pipeline
from ..database import SessionLocal

log = logging.getLogger(__name__)

def generate_questions_task(level_ids: list[int]):
    generation_jobs = []
    failed_level_ids = []

    with SessionLocal() as db:
        levels = db.scalars(select(Level).where(Level.id.in_(level_ids))).all()
        for level in levels:
            try:
                # Ensure strict typing identical to question_gen.py inputJSON
                bloom = level.bloom_level_ratio if isinstance(level.bloom_level_ratio, dict) else (
                    json.loads(level.bloom_level_ratio) if level.bloom_level_ratio else {}
                )
                
                input_data = {
                    "test": {
                        "name": str(level.name),
                        "level": int(level.number),
                        "duration_minutes": int(level.duration_min),
                        "total_marks": int(level.question_count) * 2,
                        "total_questions": int(level.question_count)
                    },
                    "syllabus": {
                        "topics": [
                            {
                                "name": str(t.name),
                                "weightage": int(t.weightage),
                                "subtopics": [
                                    {"name": str(st.name), "weightage": int(st.weightage)} 
                                    for st in t.subtopics
                                ]
                            } for t in level.topics
                        ]
                    },
                    "difficulty_ratio": {
                        "Easy": int(level.easy_pct),
                        "Medium": int(level.medium_pct),
                        "Hard": int(level.hard_pct)
                    },
                    "bloom_level_ratio": {
                        "remember": int(bloom.get("remember", 0) or 0),
                        "understand": int(bloom.get("understand", 0) or 0),
                        "apply": int(bloom.get("apply", 0) or 0),
                        "analyze": int(bloom.get("analyze", 0) or 0),
                        "evaluate": int(bloom.get("evaluate", 0) or 0),
                        "create": int(bloom.get("create", 0) or 0)
                    },
                    "question_distribution": {"MCQ": int(level.question_count)},
                    "marks_distribution": {"MCQ": 2},
                    "question_constraints": {
                        "minimum_options_for_mcq": 4,
                        "allow_multiple_correct_answers": False,
                        "negative_marking": False,
                        "negative_marks": 0,
                        "allow_partial_marking": False
                    },
                    "output_requirements": {
                        "include_answer_key": True,
                        "include_explanations": True,
                        "include_topic_tags": True,
                        "include_difficulty": True,
                        "include_marks": True
                    }
                }

                generation_jobs.append((level.id, input_data))
            except Exception:
                failed_level_ids.append(level.id)
                log.exception("Could not prepare question generation for level %s", level.id)

    for level_id in failed_level_ids:
        with SessionLocal() as db:
            level = db.get(Level, level_id)
            if level is not None:
                level.question_generation_status = "failed"
                db.commit()

    for level_id, input_data in generation_jobs:
        try:
            output = run_pipeline(input_data)

            with SessionLocal() as db:
                level = db.get(Level, level_id)
                if level is None:
                    raise LookupError(f"Level {level_id} no longer exists")

                if output.get("status") == "FAILED":
                    level.question_generation_status = "failed"
                else:
                    # Clear existing questions for this level to avoid duplicates when regenerating
                    db.execute(Question.__table__.delete().where(Question.level_id == level_id))
                    
                    for q in output.get("questions", []):
                        db_question = Question(
                            level_id=level_id,
                            text=q["question"],
                            options=[opt["text"] for opt in q["options"]],
                            answer_index=next((i for i, opt in enumerate(q["options"]) if opt["id"] == q["correct_option"]), 0),
                            difficulty=q["difficulty"].lower(),
                            topic=q["topic"]
                        )
                        db.add(db_question)
                    level.question_generation_status = "completed"

                db.commit()
        except Exception:
            log.exception("Question generation failed for level %s", level_id)
            with SessionLocal() as db:
                level = db.get(Level, level_id)
                if level is not None:
                    level.question_generation_status = "failed"
                    db.commit()

@router.post("/levels/{level_id}/generate", status_code=status.HTTP_202_ACCEPTED)
def trigger_generation(level_id: int, background_tasks: BackgroundTasks, user: User = Depends(content_editors), db: Session = Depends(get_db)):
    level = _my_level(db, user, level_id)
    
    if not level.topics or not level.bloom_level_ratio:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, 
            f"Test management is incomplete for level '{level.name}'. Please configure syllabus topics and Bloom's ratios."
        )

    level.question_generation_status = "generating"
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} started question generation for {level.name}"))
    db.commit()

    # Starlette runs background tasks before FastAPI closes yielded dependencies.
    # Release this request's connection so it is not held during AI generation.
    db.close()

    # Run the generation in background for this single level
    background_tasks.add_task(generate_questions_task, [level_id])
    
    return {"message": "Generation started"}
