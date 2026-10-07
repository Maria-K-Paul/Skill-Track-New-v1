"""Test-slot management for admins (any level) and track owners (their own domain only)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from ..deps import require_roles
from ..models import ActivityLog, Domain, Level, Slot, SlotBooking, User
from ..schemas import SlotIn, SlotPatch

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
    query = select(Domain).where(Domain.is_common.is_(False)).order_by(Domain.id)
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


@router.post("", status_code=status.HTTP_201_CREATED)
def create_slot(body: SlotIn, db: Session = Depends(get_db), user: User = Depends(managers)):
    domain = _manageable_domain(db, user, body.domain_id)
    _require_future(body.starts_at)
    # Get level to associate with slot
    level = db.get(Level, body.level_id) if hasattr(body, 'level_id') and body.level_id else None
    if level is None:
        # Default to first level of domain if not specified
        level = db.scalar(select(Level).where(Level.domain_id == domain.id).order_by(Level.number).limit(1))
    if level is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No levels found for this domain")

    slot = Slot(domain_id=domain.id, level_id=level.id, starts_at=body.starts_at, venue=body.venue.strip(), capacity=body.capacity)
    db.add(slot)
    db.add(ActivityLog(user_id=user.id, action=f"{user.name} scheduled a slot for {level.name} at {slot.venue}"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A slot for this level at this time and venue already exists.")
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
