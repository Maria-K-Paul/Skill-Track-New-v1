import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import ai
from ..ai_engine.skill_gap import run_skill_gap_agent
from ..database import get_db
from ..deps import require_roles
from ..models import AiCache, Attempt, Domain, Enrollment, Level, Question, SkillGapAnalysis, User
from ..rules import DOMAIN_SELECTION_SEMESTER, current_enrollment, level_is_open, semester_of

router = APIRouter(prefix="/ai", tags=["ai"])

student_only = require_roles("student")


# ---------- Output shapes the model must follow ----------

class RecItem(BaseModel):
    domain: str
    match: int
    reason: str


class RecOut(BaseModel):
    recommendations: list[RecItem]


class FocusTopic(BaseModel):
    topic: str
    why: str


class PrepOut(BaseModel):
    focus_topics: list[FocusTopic]
    study_plan: list[str]
    requirements: list[str]


class GapAdvice(BaseModel):
    topic: str
    tips: list[str]


class GapAdviceOut(BaseModel):
    advice: list[GapAdvice]


class SkillGapAnalyzeIn(BaseModel):
    assessment_id: int | None = None


# ---------- Helpers ----------

def _digest(value) -> str:
    return hashlib.sha1(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _cached(db: Session, user: User, kind: str, key: str, build) -> dict:
    row = db.scalar(select(AiCache).where(AiCache.user_id == user.id, AiCache.kind == kind, AiCache.cache_key == key))
    if row:
        return row.payload
    payload = build()
    db.add(AiCache(user_id=user.id, kind=kind, cache_key=key, payload=payload))
    db.commit()
    return payload


def _latest_gaps(db: Session, user: User, domain_id: int | None = None) -> tuple[Level | None, list[dict]]:
    query = (
        select(Attempt, Level).join(Level, Level.id == Attempt.level_id)
        .where(Attempt.user_id == user.id, Attempt.skill_gaps.is_not(None))
        .order_by(Attempt.taken_at.desc(), Attempt.id.desc())
    )
    if domain_id:
        query = query.where(Level.domain_id == domain_id)
    row = db.execute(query).first()
    if row is None or not row[0].skill_gaps:
        return None, []
    return row[1], row[0].skill_gaps


# ---------- Endpoints ----------

@router.get("/recommendations")
def recommendations(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Top 3 suggested domains, based on the student's attempt history (no personal identifiers are sent)."""
    if semester_of(user) < DOMAIN_SELECTION_SEMESTER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Recommendations open in Semester 3")

    domains = {d.name: d for d in db.scalars(select(Domain).where(Domain.is_common.is_(False)).order_by(Domain.id))}
    history = []
    for domain_name, level_name, score, passed, attempt_no, gaps, topic_scores in db.execute(
        select(Domain.name, Level.name, Attempt.score, Attempt.passed, Attempt.attempt_no, Attempt.skill_gaps, Attempt.topic_scores)
        .join(Level, Level.id == Attempt.level_id).join(Domain, Domain.id == Level.domain_id)
        .where(Attempt.user_id == user.id).order_by(Attempt.taken_at)
    ):
        history.append({
            "domain": domain_name, "level": level_name, "score": score, "passed": passed,
            "attempt": attempt_no, "weak_topics": [g["topic"] for g in gaps or []],
            "topic_scores": topic_scores or [],
        })
    enrolled = [d.name for d in domains.values() if d.id in {
        e.domain_id for e in db.scalars(select(Enrollment).where(Enrollment.user_id == user.id))
    }]

    def build() -> dict:
        prompt = (
            "Recommend the 3 best-suited domains for this student to pursue from the list of available domains.\n\n"
            f"Department: {user.department or 'unknown'}\nSemester: {user.semester}\n"
            f"Available domains: {json.dumps(list(domains))}\n"
            f"Domains already enrolled in: {json.dumps(enrolled)}\n"
            f"Test history (may be empty): {json.dumps(history)}\n\n"
            "Test history entries include topic_scores: per-topic percentages such as Coding, Aptitude and Basic domain from the "
            "common assessments. Use them as the main evidence when they are present.\n"
            "Rules: choose only from the available domains; give each a match score from 0 to 100; "
            "give a one-sentence reason that cites the student's actual results when they exist. "
            "If there is little or no history, base the ranking on the department, keep match scores modest, "
            "and say in the reason that the recommendation is based on limited data."
        )
        result = ai.generate(prompt, RecOut)
        items = []
        for item in result.recommendations:
            if item.domain in domains and item.domain not in {i["domain"] for i in items}:
                items.append({"domain": item.domain, "match": max(0, min(100, item.match)), "reason": item.reason.strip()})
        if not items:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The AI returned no valid domains. Try again.")
        items.sort(key=lambda i: i["match"], reverse=True)
        return {"recommendations": items[:3]}

    return _cached(db, user, "recommendations", f"attempts:{len(history)}:sem:{user.semester}:dept:{user.department}", build)


@router.get("/prep")
def preparation(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """What to learn before the student's next test, tied to the level's real question topics."""
    enr = current_enrollment(db, user)
    if enr is None or enr.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You have no upcoming test")
    domain = db.get(Domain, enr.domain_id)
    level = next((lv for lv in domain.levels if level_is_open(user, enr, lv)), None)
    if level is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You have no upcoming test")

    bank_topics = sorted({t for t in db.scalars(select(Question.topic).where(Question.level_id == level.id)) if t})
    _, gaps = _latest_gaps(db, user, domain.id)
    weak = [g["topic"] for g in gaps]
    used = db.scalar(select(func.count(Attempt.id)).where(Attempt.user_id == user.id, Attempt.level_id == level.id)) or 0

    def build() -> dict:
        prompt = (
            "Prepare a student for their next proctored test.\n\n"
            f"Domain: {domain.name}\nLevel: {level.name}\n"
            f"Pass mark: {level.pass_mark}%\nDuration: {level.duration_min} minutes\n"
            f"Questions per test: {level.question_count}\n"
            f"Topics the question bank covers for this level: {json.dumps(bank_topics) or 'not specified'}\n"
            f"Topics the student scored poorly on before: {json.dumps(weak)}\n"
            f"Attempts already used on this level: {used}\n\n"
            "Return: focus_topics (3-5 topics, each with one sentence on why it matters for this test, prioritising the "
            "student's weak topics), study_plan (3-5 short, concrete steps), and requirements (3-4 practical items to "
            "bring or prepare for a proctored, fullscreen, no-copy-paste exam at a college venue)."
        )
        result = ai.generate(prompt, PrepOut)
        return {
            "level": level.name,
            "focus_topics": [t.model_dump() for t in result.focus_topics[:5]],
            "study_plan": result.study_plan[:5],
            "requirements": result.requirements[:4],
        }

    key = f"level:{level.id}:{_digest([bank_topics, weak, used, level.pass_mark, level.duration_min])}"
    return _cached(db, user, "prep", key, build)


@router.get("/gap-advice")
def gap_advice(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Concrete improvement tips for the topics the student was weak on in their latest test."""
    enr = current_enrollment(db, user)
    level, gaps = _latest_gaps(db, user, enr.domain_id if enr else None)
    if level is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No skill-gap data yet")
    domain = db.get(Domain, level.domain_id)

    def build() -> dict:
        prompt = (
            f"A student was weak on these topics in {domain.name}, {level.name} (score per topic, out of 100):\n"
            f"{json.dumps(gaps)}\n\n"
            "For each topic, give 2-3 specific, actionable tips to improve before the next attempt "
            "(what to practise, and a small exercise). Keep each tip to one sentence. "
            "Return advice for exactly the topics listed."
        )
        result = ai.generate(prompt, GapAdviceOut)
        wanted = {g["topic"] for g in gaps}
        return {"advice": [a.model_dump() for a in result.advice if a.topic in wanted]}

    return _cached(db, user, "gap-advice", f"level:{level.id}:{_digest(gaps)}", build)


@router.post("/skill-gap/analyze")
def analyze_skill_gap(
    body: SkillGapAnalyzeIn | None = None,
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    """Run the skill-gap agent for the authenticated student and persist the structured report."""
    assessment_id = (body.assessment_id if body else None)
    try:
        report = run_skill_gap_agent(user.id, assessment_id, db)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard for Gemini or DB faults
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Skill-gap analysis failed: {exc}") from exc
    return report


@router.get("/skill-gap/latest")
def latest_skill_gap(user: User = Depends(student_only), db: Session = Depends(get_db)):
    row = db.scalar(
        select(SkillGapAnalysis).where(SkillGapAnalysis.user_id == user.id).order_by(SkillGapAnalysis.created_at.desc(), SkillGapAnalysis.id.desc())
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No skill-gap analysis has been generated yet")
    return {
        "id": row.id,
        "assessment_id": row.assessment_id,
        "overall_summary": row.overall_summary,
        "readiness": row.readiness,
        "strengths": row.strengths,
        "gaps": row.gaps,
        "next_level_priorities": row.next_level_priorities,
        "recommended_plan": row.recommended_plan,
        "priority_topics": row.priority_topics,
        "confidence": row.confidence,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/skill-gap/history")
def skill_gap_history(user: User = Depends(student_only), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SkillGapAnalysis).where(SkillGapAnalysis.user_id == user.id).order_by(SkillGapAnalysis.created_at.desc(), SkillGapAnalysis.id.desc())
    ).all()
    return [
        {
            "id": row.id,
            "assessment_id": row.assessment_id,
            "overall_summary": row.overall_summary,
            "readiness": row.readiness,
            "strengths": row.strengths,
            "gaps": row.gaps,
            "next_level_priorities": row.next_level_priorities,
            "recommended_plan": row.recommended_plan,
            "priority_topics": row.priority_topics,
            "confidence": row.confidence,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
