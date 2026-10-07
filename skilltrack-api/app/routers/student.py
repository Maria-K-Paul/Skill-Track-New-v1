from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import BOOKING_WINDOW_MINUTES
from ..database import get_db
from ..deps import require_roles
from ..models import (
    ActivityLog, Attempt, Certificate, Domain, Enrollment, Level, Question, Slot, SlotBooking, User,
)
from ..rules import (
    DOMAIN_SELECTION_SEMESTER, active_domain_enrollment, current_enrollment,
    ensure_common_enrollment, get_settings, level_is_open, semester_of,
)
from ..schemas import BookSlotIn, ChangeSlotIn, EnrollIn

router = APIRouter(tags=["student"])

student_only = require_roles("student")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seats_taken(db: Session, slot_id: int) -> int:
    return db.scalar(
        select(func.count(SlotBooking.id))
        .where(SlotBooking.slot_id == slot_id, SlotBooking.status != "cancelled")
    ) or 0


def _as_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware UTC (SQLite returns naive datetimes)."""
    if dt is None:
        return dt
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _booking_out(booking: SlotBooking, slot: Slot, level: Level) -> dict:
    deadline = _as_utc(booking.change_cancel_deadline)
    remaining = max(0, int((deadline - _now()).total_seconds())) if deadline else 0
    return {
        "booking_id": booking.id,
        "slot_id": slot.id,
        "starts_at": slot.starts_at,
        "venue": slot.venue,
        "level_name": level.name,
        "domain_name": level.domain.name,
        "booked_at": booking.booked_at,
        "change_cancel_deadline": deadline,
        "window_expired": remaining == 0,
        "seconds_remaining_in_window": remaining,
        "status": booking.status,
    }


# ── Domain discovery ──────────────────────────────────────────────────────────

@router.get("/domains")
def list_domains(
    search: str = "",
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    """All non-common domains with search, student's enrollment status, and progress."""
    query = select(Domain).where(Domain.is_common.is_(False)).order_by(Domain.id)
    domains = db.scalars(query).all()

    # Student's existing enrollments (all statuses)
    enrollments_by_domain: dict[int, Enrollment] = {
        enr.domain_id: enr
        for enr in db.scalars(select(Enrollment).where(Enrollment.user_id == user.id))
    }
    active_enr = active_domain_enrollment(db, user)

    term = search.strip().lower()
    result = []
    for d in domains:
        if term and term not in d.name.lower() and (not d.description or term not in d.description.lower()):
            continue

        level_count = len(d.levels)
        # Count distinct topics across all questions in this domain
        topic_count = db.scalar(
            select(func.count(func.distinct(Question.topic)))
            .join(Level, Level.id == Question.level_id)
            .where(Level.domain_id == d.id, Question.topic.is_not(None))
        ) or 0
        total_duration = sum(lv.duration_min for lv in d.levels)

        enr = enrollments_by_domain.get(d.id)
        passed_levels = 0
        if enr:
            passed_levels = db.scalar(
                select(func.count(func.distinct(Attempt.level_id)))
                .join(Level, Level.id == Attempt.level_id)
                .where(Attempt.user_id == user.id, Level.domain_id == d.id, Attempt.passed.is_(True))
            ) or 0

        result.append({
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "difficulty": d.difficulty,
            "level_count": level_count,
            "topic_count": topic_count,
            "total_duration_min": total_duration,
            "enrollment_status": enr.status if enr else None,
            "passed_levels": passed_levels,
            "progress_pct": round(passed_levels / level_count * 100) if level_count else 0,
        })

    # Points-based unlock status
    cfg = get_settings(db)
    total_points = db.scalar(
        select(func.sum(Enrollment.points)).where(Enrollment.user_id == user.id)
    ) or 0
    completed_domain_count = db.scalar(
        select(func.count(Enrollment.id)).where(
            Enrollment.user_id == user.id,
            Enrollment.status == "completed",
            Enrollment.is_common_enrollment.is_(False),
        )
    ) or 0
    # First domain needs only the semester gate; subsequent domains also need the points threshold
    points_unlocked = (completed_domain_count == 0) or (total_points >= cfg["points_to_unlock"])

    return {
        "domains": result,
        "active_enrollment": {
            "domain_id": active_enr.domain_id,
            "domain_name": db.get(Domain, active_enr.domain_id).name,
        } if active_enr else None,
        "can_enroll": semester_of(user) >= DOMAIN_SELECTION_SEMESTER,
        "points_to_unlock": cfg["points_to_unlock"],
        "student_points": total_points,
        "points_unlocked": points_unlocked,
    }


@router.get("/domains/{domain_id}")
def domain_detail(
    domain_id: int,
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    domain = db.get(Domain, domain_id)
    if domain is None or domain.is_common:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found")

    enr = db.scalar(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.domain_id == domain_id
    ))

    passed_set: set[int] = set()
    if enr:
        passed_set = set(
            db.scalars(
                select(func.distinct(Attempt.level_id))
                .where(Attempt.user_id == user.id, Attempt.passed.is_(True))
            )
        )

    levels_out = []
    for lv in domain.levels:
        if enr and enr.status != "removed":
            if lv.id in passed_set:
                lv_status = "completed"
            elif level_is_open(user, enr, lv) and enr.status == "active":
                lv_status = "current"
            else:
                lv_status = "locked"
        else:
            lv_status = "locked"

        topics = list({
            t for t in db.scalars(
                select(func.distinct(Question.topic))
                .where(Question.level_id == lv.id, Question.topic.is_not(None))
            )
        })
        levels_out.append({
            "id": lv.id,
            "number": lv.number,
            "name": lv.name,
            "pass_mark": lv.pass_mark,
            "duration_min": lv.duration_min,
            "question_count": lv.question_count,
            "status": lv_status,
            "topics": topics,
        })

    topic_count = db.scalar(
        select(func.count(func.distinct(Question.topic)))
        .join(Level, Level.id == Question.level_id)
        .where(Level.domain_id == domain_id, Question.topic.is_not(None))
    ) or 0

    active_enr = active_domain_enrollment(db, user)

    cfg = get_settings(db)
    total_points = db.scalar(
        select(func.sum(Enrollment.points)).where(Enrollment.user_id == user.id)
    ) or 0
    completed_domain_count = db.scalar(
        select(func.count(Enrollment.id)).where(
            Enrollment.user_id == user.id,
            Enrollment.status == "completed",
            Enrollment.is_common_enrollment.is_(False),
        )
    ) or 0
    points_unlocked = (completed_domain_count == 0) or (total_points >= cfg["points_to_unlock"])

    return {
        "id": domain.id,
        "name": domain.name,
        "description": domain.description,
        "difficulty": domain.difficulty,
        "level_count": len(domain.levels),
        "topic_count": topic_count,
        "total_duration_min": sum(lv.duration_min for lv in domain.levels),
        "levels": levels_out,
        "enrollment_status": enr.status if enr else None,
        "active_enrollment": {
            "domain_id": active_enr.domain_id,
            "domain_name": db.get(Domain, active_enr.domain_id).name,
        } if active_enr and active_enr.domain_id != domain_id else None,
        "can_enroll": semester_of(user) >= DOMAIN_SELECTION_SEMESTER,
        "points_to_unlock": cfg["points_to_unlock"],
        "student_points": total_points,
        "points_unlocked": points_unlocked,
    }


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/me/dashboard")
def dashboard(user: User = Depends(student_only), db: Session = Depends(get_db)):
    cfg = get_settings(db)
    ensure_common_enrollment(db, user)
    db.commit()
    domains = db.scalars(select(Domain).where(Domain.is_common.is_(False)).order_by(Domain.id)).all()
    # Only domain-completion certs (status != legacy) for the dashboard tile
    certs = db.scalars(
        select(Certificate)
        .where(Certificate.user_id == user.id, Certificate.domain_id.is_not(None), Certificate.status != "legacy")
        .order_by(Certificate.issued_at)
    ).all()
    certificates_out = []
    for c in certs:
        d_name = c.domain_name or db.get(Domain, c.domain_id).name
        certificates_out.append({
            "code": c.code, "title": d_name,
            "issued_at": c.issued_at, "first_attempt": c.first_attempt,
        })

    total_points = db.scalar(
        select(func.sum(Enrollment.points)).where(Enrollment.user_id == user.id)
    ) or 0
    completed_domain_count = db.scalar(
        select(func.count(Enrollment.id)).where(
            Enrollment.user_id == user.id,
            Enrollment.status == "completed",
            Enrollment.is_common_enrollment.is_(False),
        )
    ) or 0
    points_unlocked = (completed_domain_count == 0) or (total_points >= cfg["points_to_unlock"])

    result = {
        "user": {"name": user.name, "department": user.department, "semester": user.semester},
        "domains": [{"id": d.id, "name": d.name} for d in domains],
        "points_to_unlock": cfg["points_to_unlock"],
        "total_points": total_points,
        "points_unlocked": points_unlocked,
        "max_attempts": cfg["max_attempts"],
        "enrollment": None,
        "levels": [],
        "slots": [],
        "booked_slot_id": None,
        "active_booking": None,
        "skill_gap": None,
        "certificates": certificates_out,
        # completed domain info
        "completed_domain": None,
    }

    enr = current_enrollment(db, user)

    # Check for the most recently completed domain enrollment to show after completion
    completed_enr = db.scalar(
        select(Enrollment).join(Domain, Domain.id == Enrollment.domain_id)
        .where(Enrollment.user_id == user.id, Enrollment.status == "completed", Domain.is_common.is_(False))
        .order_by(Enrollment.id.desc())
    )
    if completed_enr:
        comp_domain = db.get(Domain, completed_enr.domain_id)
        comp_cert = db.scalar(select(Certificate).where(
            Certificate.user_id == user.id, Certificate.domain_id == completed_enr.domain_id
        ))
        result["completed_domain"] = {
            "domain_id": comp_domain.id,
            "domain_name": comp_domain.name,
            "completed_at": completed_enr.completed_at,
            "certificate_code": comp_cert.code if comp_cert else None,
        }

    if enr is None:
        return result

    domain = db.get(Domain, enr.domain_id)
    level_count = len(domain.levels)
    passed_levels_count = db.scalar(
        select(func.count(func.distinct(Attempt.level_id)))
        .join(Level, Level.id == Attempt.level_id)
        .where(Attempt.user_id == user.id, Level.domain_id == domain.id, Attempt.passed.is_(True))
    ) or 0

    result["enrollment"] = {
        "domain_id": domain.id, "domain": domain.name, "status": enr.status, "is_common": domain.is_common,
        "points": enr.points, "current_level": enr.current_level,
        "level_count": level_count, "passed_levels": passed_levels_count,
        "progress_pct": round(passed_levels_count / level_count * 100) if level_count else 0,
        "enrolled_at": enr.enrolled_at,
    }
    if domain.is_common:
        result["max_attempts"] = None  # common assessments have no attempt cap

    attempts = db.scalars(
        select(Attempt).where(Attempt.user_id == user.id, Attempt.level_id.in_([lv.id for lv in domain.levels]))
        .order_by(Attempt.attempt_no)
    ).all()
    by_level: dict[int, list[Attempt]] = {}
    for a in attempts:
        by_level.setdefault(a.level_id, []).append(a)

    active_level = None
    for lv in domain.levels:
        atts = by_level.get(lv.id, [])
        passed = next((a for a in atts if a.passed), None)
        if passed:
            lv_state = "cleared"
        elif lv.number == enr.current_level and enr.status == "removed":
            lv_state = "removed"
        elif level_is_open(user, enr, lv) and enr.status == "active":
            lv_state = "active"
            active_level = lv
        else:
            lv_state = "locked"
        result["levels"].append({
            "id": lv.id, "number": lv.number, "name": lv.name, "status": lv_state,
            "attempts_used": len(atts),
            "score": atts[-1].score if atts else None,
            "first_attempt": bool(passed and passed.attempt_no == 1),
        })

    with_gaps = [a for a in attempts if a.skill_gaps]
    if with_gaps:
        latest = max(with_gaps, key=lambda a: a.taken_at)
        level = next(lv for lv in domain.levels if lv.id == latest.level_id)
        result["skill_gap"] = {"level_name": level.name, "weak": latest.skill_gaps}

    if active_level:
        # Fetch student's booked slot in this domain (any level)
        booked = db.scalar(
            select(SlotBooking.slot_id).join(Slot, Slot.id == SlotBooking.slot_id)
            .where(SlotBooking.user_id == user.id, Slot.domain_id == domain.id)
        )
        result["booked_slot_id"] = booked
        # Fetch all upcoming slots for this domain (students can book any slot regardless of level)
        # Use timezone-aware datetime for consistent comparison
        now = datetime.now(timezone.utc)
        slots = db.scalars(
            select(Slot).where(Slot.domain_id == domain.id, Slot.starts_at > now)
            .order_by(Slot.starts_at)
        ).all()
        result["slots"] = [
            {
                "id": s.id, "starts_at": s.starts_at, "venue": s.venue,
                "seats_left": max(0, s.capacity - _seats_taken(db, s.id)),
            }
            for s in slots
        ]
    return result


# ── Enrollment ────────────────────────────────────────────────────────────────

@router.post("/enrollments", status_code=status.HTTP_201_CREATED)
def enroll(body: EnrollIn, user: User = Depends(student_only), db: Session = Depends(get_db)):
    domain = db.get(Domain, body.domain_id)
    if domain is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found")
    if domain.is_common:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Common assessments are assigned automatically")
    if semester_of(user) < DOMAIN_SELECTION_SEMESTER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Domain selection opens in Semester 3")

    # Check for existing (any status) enrollment in this exact domain
    existing_same = db.scalar(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.domain_id == domain.id)
    )
    if existing_same:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already enrolled in this domain")

    # Enforce single active domain enrollment
    active_enr = active_domain_enrollment(db, user)
    if active_enr:
        active_domain = db.get(Domain, active_enr.domain_id)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You cannot enroll in this domain because you are already enrolled in another domain. "
            f"Complete your current domain before enrolling in a new domain. "
            f"(Current domain: {active_domain.name})",
        )

    # Points gate: after completing a domain, require enough accumulated points to unlock the next one
    cfg = get_settings(db)
    completed_domain_count = db.scalar(
        select(func.count(Enrollment.id)).where(
            Enrollment.user_id == user.id,
            Enrollment.status == "completed",
            Enrollment.is_common_enrollment.is_(False),
        )
    ) or 0
    if completed_domain_count > 0:
        total_points = db.scalar(
            select(func.sum(Enrollment.points)).where(Enrollment.user_id == user.id)
        ) or 0
        if total_points < cfg["points_to_unlock"]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"You need {cfg['points_to_unlock']} points to unlock your next domain. "
                f"You have {total_points} point{'s' if total_points != 1 else ''} so far.",
            )

    new_enr = Enrollment(
        user_id=user.id,
        domain_id=domain.id,
        is_common_enrollment=False,
        enrolled_at=_now(),
    )
    db.add(new_enr)
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} enrolled in {domain.name}"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You cannot enroll in this domain because you are already enrolled in another domain. "
            "Complete your current domain before enrolling in a new domain.",
        )
    return {"domain_id": domain.id, "domain_name": domain.name}


# ── Slot booking ──────────────────────────────────────────────────────────────

@router.post("/slots/{slot_id}/book")
def book_slot(slot_id: int, body: BookSlotIn, user: User = Depends(student_only), db: Session = Depends(get_db)):
    # acknowledgement is already validated by BookSlotIn

    slot = db.get(Slot, slot_id, with_for_update=True)  # row-lock for capacity
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not found")

    level = db.get(Level, slot.level_id)
    domain = db.get(Domain, slot.domain_id)

    # Enrollment + eligibility check
    enr = db.scalar(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.domain_id == slot.domain_id, Enrollment.status == "active",
    ))
    if enr is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You are not enrolled in {domain.name}")

    starts_at = slot.starts_at if slot.starts_at.tzinfo else slot.starts_at.replace(tzinfo=timezone.utc)
    if starts_at <= _now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This slot has already started")

    # Block double-booking same domain+level
    existing_level_booking = db.scalar(
        select(SlotBooking).join(Slot, Slot.id == SlotBooking.slot_id)
        .where(
            SlotBooking.user_id == user.id,
            Slot.level_id == level.id,
            SlotBooking.status == "booked",
        )
    )
    if existing_level_booking:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You already have a booked examination slot for this test.",
        )

    if _seats_taken(db, slot.id) >= slot.capacity:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This slot is no longer available. Please select another slot.",
        )

    now = _now()
    deadline = now + timedelta(minutes=BOOKING_WINDOW_MINUTES)

    # Reactivate a previously cancelled booking for this slot (unique constraint prevents a new row)
    cancelled = db.scalar(
        select(SlotBooking).where(
            SlotBooking.slot_id == slot.id,
            SlotBooking.user_id == user.id,
            SlotBooking.status == "cancelled",
        )
    )
    if cancelled:
        cancelled.status = "booked"
        cancelled.booked_at = now
        cancelled.change_cancel_deadline = deadline
        cancelled.acknowledgement_acknowledged_at = now
        booking = cancelled
    else:
        booking = SlotBooking(
            slot_id=slot.id,
            user_id=user.id,
            status="booked",
            booked_at=now,
            change_cancel_deadline=deadline,
            acknowledgement_acknowledged_at=now,
        )
        db.add(booking)
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} booked a slot for {level.name}"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a booking for this slot.")
    db.refresh(booking)
    return _booking_out(booking, slot, level)


@router.delete("/me/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_booking(booking_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    booking = db.scalar(
        select(SlotBooking).where(SlotBooking.id == booking_id, SlotBooking.user_id == user.id)
        .with_for_update()
    )
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.status != "booked":
        raise HTTPException(status.HTTP_409_CONFLICT, "This booking cannot be cancelled")

    deadline = _as_utc(booking.change_cancel_deadline)
    if deadline and _now() > deadline:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "The 30-minute change/cancellation window has expired. You can no longer change or cancel this booking.",
        )

    booking.status = "cancelled"
    slot = db.get(Slot, booking.slot_id)
    level = db.get(Level, slot.level_id)
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} cancelled their slot booking for {level.name}"))
    db.commit()


@router.post("/me/bookings/{booking_id}/change")
def change_booking(
    booking_id: int,
    body: ChangeSlotIn,
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    # Lock current booking first
    old_booking = db.scalar(
        select(SlotBooking).where(SlotBooking.id == booking_id, SlotBooking.user_id == user.id)
        .with_for_update()
    )
    if old_booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if old_booking.status != "booked":
        raise HTTPException(status.HTTP_409_CONFLICT, "This booking cannot be changed")

    deadline = _as_utc(old_booking.change_cancel_deadline)
    if deadline and _now() > deadline:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "The 30-minute change/cancellation window has expired. You can no longer change or cancel this booking.",
        )

    if body.new_slot_id == old_booking.slot_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You are already booked for this slot.")

    # Lock the new slot for capacity check
    new_slot = db.get(Slot, body.new_slot_id, with_for_update=True)
    if new_slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "New slot not found")

    old_slot = db.get(Slot, old_booking.slot_id)
    if new_slot.level_id != old_slot.level_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New slot must be for the same level.")

    new_starts = new_slot.starts_at if new_slot.starts_at.tzinfo else new_slot.starts_at.replace(tzinfo=timezone.utc)
    if new_starts <= _now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The new slot has already started.")

    # Capacity check on new slot (exclude the student's own current booking row if somehow counted)
    if _seats_taken(db, new_slot.id) >= new_slot.capacity:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This slot is no longer available. Please select another slot.",
        )

    # Execute the change: cancel old, create new (deadline does NOT reset)
    old_booking.status = "cancelled"
    level = db.get(Level, new_slot.level_id)
    new_booking = SlotBooking(
        slot_id=new_slot.id,
        user_id=user.id,
        status="booked",
        booked_at=old_booking.booked_at,        # keep original booked_at
        change_cancel_deadline=old_booking.change_cancel_deadline,  # deadline does not extend
        acknowledgement_acknowledged_at=old_booking.acknowledgement_acknowledged_at,
    )
    db.add(new_booking)
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} changed their slot booking for {level.name}"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a booking for the new slot.")
    db.refresh(new_booking)
    return _booking_out(new_booking, new_slot, level)


@router.get("/me/bookings")
def my_bookings(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """All active (non-cancelled) bookings for the student."""
    bookings = db.scalars(
        select(SlotBooking).where(SlotBooking.user_id == user.id, SlotBooking.status == "booked")
    ).all()
    result = []
    for b in bookings:
        slot = db.get(Slot, b.slot_id)
        level = db.get(Level, slot.level_id)
        result.append(_booking_out(b, slot, level))
    return result
