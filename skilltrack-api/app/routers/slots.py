"""Test-slot management for admins (any level) and track owners (their own domain only)."""
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import json

from ..database import get_db, SessionLocal
from ..deps import require_roles
from ..models import ActivityLog, Domain, Slot, SlotBooking, User, Enrollment, Level, Question
from ..schemas import SlotIn, SlotPatch
from ..QuestionGen.question_gen import run_pipeline

log = logging.getLogger(__name__)

router = APIRouter(prefix="/manage/slots", tags=["slots"])

managers = require_roles("admin", "owner")


def _manageable_domain(db: Session, user: User, domain_id: int) -> Domain:
    domain = db.get(Domain, domain_id)
    if domain is None or (user.role == "owner" and domain.owner_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found")
    return domain


def _manageable_slot(db: Session, user: User, slot_id: int) -> Slot:
    slot = db.get(Slot, slot_id)
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not found")
    _manageable_domain(db, user, slot.domain_id)
    return slot


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _require_future(starts_at: datetime) -> None:
    if _aware(starts_at) <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a date and time in the future")


def _booked(db: Session, slot_id: int) -> int:
    return db.scalar(select(func.count(SlotBooking.id)).where(SlotBooking.slot_id == slot_id)) or 0


def _out(db: Session, slot: Slot) -> dict:
    domain = db.get(Domain, slot.domain_id)
    return {
        "id": slot.id, "domain_id": slot.domain_id, "domain_name": domain.name if domain else "",
        "starts_at": slot.starts_at, "venue": slot.venue, "capacity": slot.capacity,
        "booked": _booked(db, slot.id),
    }


@router.get("/catalog")
def catalog(db: Session = Depends(get_db), user: User = Depends(managers)):
    query = select(Domain).where(Domain.is_common == False).order_by(Domain.id)
    if user.role == "owner":
        query = query.where(Domain.owner_id == user.id)
    return [
        {"id": d.id, "name": d.name}
        for d in db.scalars(query)
    ]


@router.get("")
def list_slots(domain_id: int, db: Session = Depends(get_db), user: User = Depends(managers)):
    domain = _manageable_domain(db, user, domain_id)
    slots = db.scalars(select(Slot).where(Slot.domain_id == domain.id).order_by(Slot.starts_at)).all()
    return [_out(db, s) for s in slots]


def _get_active_levels(db: Session, domain_id: int) -> list[Level]:
    active_level_numbers = db.scalars(
        select(Enrollment.current_level)
        .where(Enrollment.domain_id == domain_id)
        .where(Enrollment.status == "active")
        .distinct()
    ).all()
    if not active_level_numbers:
        return []
    return db.scalars(
        select(Level)
        .where(Level.domain_id == domain_id)
        .where(Level.number.in_(active_level_numbers))
    ).all()

def _validate_all_domain_levels(db: Session, domain_id: int) -> None:
    all_levels = db.scalars(
        select(Level).where(Level.domain_id == domain_id)
    ).all()
    for level in all_levels:
        if not level.topics or not level.bloom_level_ratio:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, 
                f"Test management is incomplete for level '{level.name}'. Please configure syllabus topics and Bloom's ratios for all levels before creating a slot."
            )
        question_count = db.scalar(select(func.count(Question.id)).where(Question.level_id == level.id))
        if question_count == 0:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Question Paper is not generated for level '{level.name}'. Please generate questions for all levels before creating a slot."
            )

@router.post("", status_code=status.HTTP_201_CREATED)
def create_slot(body: SlotIn, db: Session = Depends(get_db), user: User = Depends(managers)):
    domain = _manageable_domain(db, user, body.domain_id)
    
    # Track owner must set the syllabus and generate questions for ALL levels before creating a slot
    _validate_all_domain_levels(db, domain.id)
    
    _require_future(body.starts_at)
    slot = Slot(domain_id=domain.id, starts_at=body.starts_at, venue=body.venue.strip(), capacity=body.capacity)
    db.add(slot)
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} scheduled a slot for {domain.name} at {slot.venue}"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This slot is already enrolled/created.")
        
    return _out(db, slot)


@router.patch("/{slot_id}")
def update_slot(slot_id: int, body: SlotPatch, db: Session = Depends(get_db), user: User = Depends(managers)):
    slot = _manageable_slot(db, user, slot_id)
    changes = body.model_dump(exclude_unset=True)
    if "starts_at" in changes and changes["starts_at"] is not None:
        _require_future(changes["starts_at"])
    if changes.get("capacity") is not None and changes["capacity"] < _booked(db, slot.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"This slot already has {_booked(db, slot.id)} booking(s), so capacity cannot go below that",
        )
    for field, value in changes.items():
        if value is not None:
            setattr(slot, field, value.strip() if isinstance(value, str) else value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This slot is already enrolled/created.")
    return _out(db, slot)


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_slot(slot_id: int, db: Session = Depends(get_db), user: User = Depends(managers)):
    slot = _manageable_slot(db, user, slot_id)
    booked = _booked(db, slot.id)
    if booked:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"This slot has {booked} booking(s). Add another slot and ask those students to switch first.",
        )
    db.delete(slot)
    db.commit()
