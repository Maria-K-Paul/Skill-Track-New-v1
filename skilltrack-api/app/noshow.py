"""No-show job: marks slot bookings MISSED and records a score=0 attempt.

Rule used: consistent with the existing scoring architecture — a no-show is
treated as a failed attempt with score 0 (counts toward max_attempts, triggers
removal if it was the last allowed attempt). No point deduction is applied
because the existing system only awards points, never deducts them.

Idempotent: each booking is processed at most once (status transitions to
'missed' atomically; the attempt is only recorded if no attempt already exists
after the slot start time for that student+level).
"""
from datetime import datetime, timezone

from sqlalchemy import func, select

from .database import SessionLocal
from .models import ActivityLog, Attempt, Enrollment, Level, Slot, SlotBooking, User
from .rules import get_settings, record_attempt


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def run_noshow_job() -> int:
    """Process all missed bookings. Returns the number of bookings processed."""
    processed = 0
    with SessionLocal() as db:
        threshold = _now()
        candidates = db.scalars(
            select(SlotBooking)
            .join(Slot, Slot.id == SlotBooking.slot_id)
            .where(
                SlotBooking.status == "booked",
                Slot.starts_at < threshold,
            )
        ).all()

        cfg = get_settings(db)  # noqa: F841 — available if needed

        for booking in candidates:
            slot = db.get(Slot, booking.slot_id)
            level = db.get(Level, slot.level_id)
            user = db.get(User, booking.user_id)
            if user is None:
                continue

            slot_start = _aware(slot.starts_at)

            # Student already has an attempt for this level after the slot started → attended
            has_attempt = db.scalar(
                select(func.count(Attempt.id)).where(
                    Attempt.user_id == booking.user_id,
                    Attempt.level_id == level.id,
                    Attempt.taken_at >= slot_start,
                )
            )
            if has_attempt:
                booking.status = "attended"
                db.commit()
                continue

            enr = db.scalar(
                select(Enrollment).where(
                    Enrollment.user_id == booking.user_id,
                    Enrollment.domain_id == level.domain_id,
                    Enrollment.status == "active",
                )
            )
            if enr is None:
                booking.status = "missed"
                db.commit()
                continue

            # Mark missed and record zero-score attempt (counts toward max_attempts)
            booking.status = "missed"
            record_attempt(db, user, level, enr, 0, None)
            db.add(ActivityLog(
                user_id=booking.user_id,
                action=f"No-show for {level.name} — attempt recorded with score 0",
            ))
            db.commit()
            processed += 1

    return processed
