import random
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import ActivityLog, Domain, Enrollment, ExamKey, ExamSession, Level, Question, Slot, SlotBooking, User
from ..ratelimit import exam_start
from ..rules import check_eligible, get_settings, record_attempt
from ..schemas import KeyIn, StartIn, SubmitIn

router = APIRouter(prefix="/exam", tags=["exam"])

staff = require_roles("invigilator", "admin")
student_only = require_roles("student")

LATE_GRACE = timedelta(minutes=2)
GAP_THRESHOLD = 60  # topics scored below this % are reported as skill gaps


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _slot_students(db: Session, slot_id: int) -> list[dict]:
    rows = db.execute(
        select(User.id, User.name, User.reg_no)
        .join(SlotBooking, SlotBooking.user_id == User.id)
        .where(SlotBooking.slot_id == slot_id)
        .order_by(User.name)
    ).all()
    return [{"id": r.id, "name": r.name, "reg_no": r.reg_no} for r in rows]


def _slot_out(db: Session, slot: Slot, with_students: bool = True) -> dict:
    domain = db.get(Domain, slot.domain_id)
    students = _slot_students(db, slot.id)
    return {
        "id": slot.id, "domain_id": domain.id, "domain_name": domain.name,
        "starts_at": _aware(slot.starts_at), "venue": slot.venue, "capacity": slot.capacity,
        "booked": len(students), "students": students if with_students else [],
    }


def _key_out(db: Session, k: ExamKey) -> dict:
    left = int((_aware(k.expires_at) - _now()).total_seconds())
    slot = db.get(Slot, k.slot_id) if k.slot_id else None
    domain = db.get(Domain, k.domain_id)
    level = db.get(Level, k.level_id) if k.level_id else None
    return {
        "id": k.id, "code": k.code, "domain_id": domain.id, "domain_name": domain.name,
        "level_name": level.name if level else f"{domain.name} (any level)",
        "expires_at": _aware(k.expires_at), "seconds_left": max(0, left),
        "slot": _slot_out(db, slot) if slot else None,
    }


# ---------- Invigilator / admin ----------

@router.get("/catalog")
def catalog(db: Session = Depends(get_db), _: User = Depends(staff)):
    domains = db.scalars(select(Domain).order_by(Domain.id)).all()
    return [
        {
            "id": d.id, "name": d.name,
            "levels": [{"id": lv.id, "number": lv.number, "name": lv.name} for lv in d.levels],
        }
        for d in domains
    ]


@router.get("/slots")
def keyable_slots(db: Session = Depends(get_db), _: User = Depends(staff)):
    """Slots a key can be issued for: anything starting from 6 hours ago onwards, with the students who booked it."""
    since = _now() - timedelta(hours=6)
    slots = db.scalars(select(Slot).where(Slot.starts_at >= since).order_by(Slot.starts_at)).all()
    return [_slot_out(db, s) for s in slots]


@router.post("/keys", status_code=status.HTTP_201_CREATED)
def issue_key(body: KeyIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    slot = None
    domain_id = None
    level_id = None

    if body.slot_id is not None:
        # Key for a specific slot - any level student in that domain can use it
        slot = db.get(Slot, body.slot_id)
        if slot is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not found")
        domain_id = slot.domain_id
        level_id = None  # Will be determined from student's enrollment
    else:
        # Key for a specific level (legacy mode or manual override)
        level = db.get(Level, body.level_id)
        if level is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Level not found")
        domain_id = level.domain_id
        level_id = level.id

    for _ in range(20):
        code = f"SKL-{secrets.randbelow(9000) + 1000}"
        if db.scalar(select(ExamKey.id).where(ExamKey.code == code)) is None:
            break
    else:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not generate a key, try again")

    key = ExamKey(
        code=code, domain_id=domain_id, level_id=level_id,
        slot_id=slot.id if slot else None, issued_by=user.id,
        expires_at=_now() + timedelta(minutes=body.minutes or get_settings(db)["key_minutes"]),
    )
    db.add(key)
    domain = db.get(Domain, domain_id)
    where = f" ({slot.venue}, slot #{slot.id})" if slot else ""
    db.add(ActivityLog(user_id=user.id, action=f"Exam key issued for {domain.name}{where}"))
    db.commit()
    return _key_out(db, key)


@router.get("/keys")
def recent_keys(db: Session = Depends(get_db), user: User = Depends(staff)):
    keys = db.scalars(
        select(ExamKey).where(ExamKey.issued_by == user.id).order_by(ExamKey.id.desc()).limit(10)
    ).all()
    return [_key_out(db, k) for k in keys]


# ---------- Student ----------

def _pick_questions(db: Session, level: Level) -> list[Question]:
    bank = db.scalars(select(Question).where(Question.level_id == level.id)).all()
    by_difficulty: dict[str, list[Question]] = {"easy": [], "medium": [], "hard": []}
    for q in bank:
        by_difficulty.setdefault(q.difficulty, []).append(q)

    # Use integer division to avoid rounding errors, allocate remainder to hard questions
    easy_count = int(level.question_count * level.easy_pct / 100)
    medium_count = int(level.question_count * level.medium_pct / 100)
    hard_count = level.question_count - easy_count - medium_count  # Ensures exact total

    targets = {"easy": easy_count, "medium": medium_count, "hard": hard_count}

    chosen: list[Question] = []
    for difficulty, pool in by_difficulty.items():
        target = targets.get(difficulty, 0)
        if target > 0:
            chosen += random.sample(pool, min(len(pool), target))

    # If we still need more questions (due to insufficient questions in specific difficulties)
    leftover = [q for q in bank if q not in chosen]
    if len(chosen) < level.question_count and leftover:
        chosen += random.sample(leftover, min(len(leftover), level.question_count - len(chosen)))

    random.shuffle(chosen)
    return chosen


def _session_out(db: Session, session: ExamSession, level: Level) -> dict:
    questions = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_(session.question_ids)))}
    ids = [qid for qid in session.question_ids if qid in questions]
    now = _now()
    return {
        "session_id": session.id,
        "level": {"id": level.id, "name": level.name, "pass_mark": level.pass_mark},
        "seconds_left": max(0, int((_aware(session.ends_at) - now).total_seconds())),
        "server_time": now.isoformat(),  # Send server time for client sync
        "ends_at": _aware(session.ends_at).isoformat(),
        "questions": [
            {"id": qid, "text": questions[qid].text, "options": questions[qid].options}
            for qid in ids
        ],
    }


def _wait_text(starts: datetime) -> str:
    mins = max(1, -(-int((starts - _now()).total_seconds()) // 60))
    return f"Your exam has not started yet. It opens in {mins} minute{'s' if mins != 1 else ''}, at your booked slot time."


def _check_slot_time(db: Session, user: User, key: ExamKey) -> None:
    """Students may only begin once their booked slot has started, even if they already hold a key."""
    now = _now()
    if key.slot_id is not None:
        slot = db.get(Slot, key.slot_id)
        if _aware(slot.starts_at) > now:
            raise HTTPException(status.HTTP_403_FORBIDDEN, _wait_text(_aware(slot.starts_at)))
        return
    # Key not tied to a slot: if the student has booked a slot for this domain, hold them to its start time
    starts = sorted(
        _aware(t) for t in db.scalars(
            select(Slot.starts_at).join(SlotBooking, SlotBooking.slot_id == Slot.id)
            .where(SlotBooking.user_id == user.id, Slot.domain_id == key.domain_id)
        )
    )
    if starts and not any(now - timedelta(hours=6) <= t <= now for t in starts):
        upcoming = [t for t in starts if t > now]
        if upcoming:
            raise HTTPException(status.HTTP_403_FORBIDDEN, _wait_text(upcoming[0]))


@router.get("/my-slot")
def my_slot(db: Session = Depends(get_db), user: User = Depends(student_only)):
    """The student's next booked slot (or one that started within the last 6 hours), with their level info."""
    since = _now() - timedelta(hours=6)
    slot = db.scalar(
        select(Slot).join(SlotBooking, SlotBooking.slot_id == Slot.id)
        .where(SlotBooking.user_id == user.id, SlotBooking.status == "booked", Slot.starts_at >= since)
        .order_by(Slot.starts_at).limit(1)
    )
    if slot is None:
        return None
    domain = db.get(Domain, slot.domain_id)
    # Get student's current level in this domain
    enrollment = db.scalar(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.domain_id == slot.domain_id)
    )
    level_number = enrollment.current_level if enrollment else 1
    level = db.scalar(
        select(Level).where(Level.domain_id == slot.domain_id, Level.number == level_number)
    )
    return {
        "id": slot.id, "starts_at": _aware(slot.starts_at), "venue": slot.venue,
        "level_name": level.name if level else f"Level {level_number}",
        "domain_name": domain.name,
        "seconds_until_start": max(0, int((_aware(slot.starts_at) - _now()).total_seconds())),
    }


@router.post("/start")
def start_exam(body: StartIn, db: Session = Depends(get_db), user: User = Depends(student_only)):
    exam_start.check(f"user:{user.id}")
    # Serialise this student's starts so two requests cannot both create a new session
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    key = db.scalar(select(ExamKey).where(ExamKey.code == body.key.strip().upper()))
    if key is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid key. Check with the invigilator.")
    if _aware(key.expires_at) <= _now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This key has expired. Ask the invigilator for a new key.")

    # Check if student booked the slot (if key is tied to a slot)
    if key.slot_id is not None and db.scalar(
        select(SlotBooking.id).where(SlotBooking.slot_id == key.slot_id, SlotBooking.user_id == user.id)
    ) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This key is for a different slot. Check that you are using the key for the slot you booked.")
    _check_slot_time(db, user, key)

    # Get student's enrollment to determine their level in this domain
    enrollment = db.scalar(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.domain_id == key.domain_id)
    )
    if enrollment is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You are not enrolled in this domain. Please enroll first.")
    if enrollment.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Your enrollment in this domain is {enrollment.status}.")

    # Get the level for this student based on their enrollment
    level = db.scalar(
        select(Level).where(Level.domain_id == key.domain_id, Level.number == enrollment.current_level)
    )
    if level is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Level {enrollment.current_level} not found in this domain.")

    check_eligible(db, user, level)

    # Resume an unfinished session (e.g. after a refresh or a network drop)
    open_session = db.scalar(
        select(ExamSession).where(
            ExamSession.user_id == user.id, ExamSession.level_id == level.id, ExamSession.submitted_at.is_(None),
        ).order_by(ExamSession.id.desc())
    )
    if open_session:
        now = _now()
        if _aware(open_session.ends_at) > now:
            # Session still valid, resume it
            return _session_out(db, open_session, level)
        else:
            # Session expired without submission - auto-submit with zero score
            open_session.submitted_at = now
            open_session.violations = 0
            # Get enrollment without eligibility check (session already started)
            enr = db.scalar(
                select(Enrollment).where(
                    Enrollment.user_id == user.id, Enrollment.domain_id == level.domain_id, Enrollment.status == "active"
                )
            )
            if enr:
                outcome = record_attempt(db, user, level, enr, 0, None, None)
                db.add(ActivityLog(
                    user_id=user.id,
                    action=f"{user.name}: Auto-submitted expired session for {level.name} (time ran out)"
                ))
                db.commit()
                raise HTTPException(
                    status.HTTP_410_GONE,
                    f"Your previous exam session expired without submission and was recorded as a failed attempt. "
                    f"You have used {outcome['attempt_no']} attempt(s)."
                )
            else:
                # Enrollment no longer exists or is inactive
                db.commit()
                raise HTTPException(
                    status.HTTP_410_GONE,
                    "Your previous exam session expired. Please contact your administrator."
                )

    questions = _pick_questions(db, level)
    if not questions:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No questions have been added for this level yet")
    if len(questions) < level.question_count:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Insufficient questions for this exam. Need {level.question_count}, but only {len(questions)} available. Contact your administrator."
        )
    now = _now()
    session = ExamSession(
        user_id=user.id, level_id=level.id, key_id=key.id, question_ids=[q.id for q in questions],
        started_at=now, ends_at=now + timedelta(minutes=level.duration_min),
    )
    db.add(session)
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} started {level.name}"))
    db.commit()
    return _session_out(db, session, level)


@router.get("/sessions/{session_id}/time")
def session_time(session_id: int, db: Session = Depends(get_db), user: User = Depends(student_only)):
    """Return server time and remaining seconds for client sync during exam."""
    session = db.get(ExamSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if session.submitted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Exam already submitted")
    now = _now()
    return {
        "server_time": now.isoformat(),
        "ends_at": _aware(session.ends_at).isoformat(),
        "seconds_left": max(0, int((_aware(session.ends_at) - now).total_seconds())),
    }


@router.post("/sessions/{session_id}/submit")
def submit_exam(session_id: int, body: SubmitIn, db: Session = Depends(get_db), user: User = Depends(student_only)):
    # Lock the row so a double-click, retry or auto-submit racing a manual one can only be graded once
    session = db.get(ExamSession, session_id, with_for_update=True)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam session not found")
    if session.submitted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This exam was already submitted")

    level = db.get(Level, session.level_id)
    enr = check_eligible(db, user, level)
    now = _now()
    late = now > _aware(session.ends_at) + LATE_GRACE

    questions = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_(session.question_ids)))}
    ids = [qid for qid in session.question_ids if qid in questions]
    correct = 0
    topics: dict[str, list[int]] = {}
    for qid in ids:
        q = questions[qid]
        is_right = not late and body.answers.get(str(qid)) == q.answer_index
        correct += is_right
        stats = topics.setdefault(q.topic or "General", [0, 0])
        stats[0] += is_right
        stats[1] += 1

    total = len(ids)
    score = round(correct / total * 100) if total else 0
    gaps = sorted(
        ({"topic": t, "score": round(c / n * 100)} for t, (c, n) in topics.items() if c / n * 100 < GAP_THRESHOLD),
        key=lambda g: g["score"],
    )

    all_topics = [{"topic": t, "score": round(c / n * 100)} for t, (c, n) in topics.items()]
    outcome = record_attempt(db, user, level, enr, score, gaps, all_topics)
    session.submitted_at = now
    session.violations = body.violations
    if body.violations:
        db.add(ActivityLog(user_id=user.id, action=f"{user.name}: {body.violations} tab switch(es) during {level.name}"))
    db.commit()
    return {
        **outcome, "score": score, "correct": correct, "total": total,
        "pass_mark": level.pass_mark, "late": late, "skill_gaps": gaps, "topic_scores": all_topics,
    }
