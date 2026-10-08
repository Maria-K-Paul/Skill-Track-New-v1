from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

ROLES = ("student", "owner", "admin", "invigilator")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    reg_no: Mapped[str | None] = mapped_column(String(30), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="student")
    department: Mapped[str | None] = mapped_column(String(20))
    semester: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # The Semester 1-2 common assessments live in a special domain that students never pick themselves
    is_common: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    description: Mapped[str | None] = mapped_column(String(500))
    difficulty: Mapped[str | None] = mapped_column(String(20))  # beginner | intermediate | advanced
    levels: Mapped[list["Level"]] = relationship(back_populates="domain", order_by="Level.number")


class Level(Base):
    __tablename__ = "levels"
    __table_args__ = (UniqueConstraint("domain_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id", ondelete="RESTRICT"))
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    question_count: Mapped[int] = mapped_column(Integer, default=20)
    pass_mark: Mapped[int] = mapped_column(Integer, default=50)
    duration_min: Mapped[int] = mapped_column(Integer, default=30)
    easy_pct: Mapped[int] = mapped_column(Integer, default=30)
    medium_pct: Mapped[int] = mapped_column(Integer, default=50)
    hard_pct: Mapped[int] = mapped_column(Integer, default=20)
    domain: Mapped[Domain] = relationship(back_populates="levels")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(String(1000))
    options: Mapped[list] = mapped_column(JSON)
    answer_index: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[str] = mapped_column(String(10))  # easy | medium | hard
    topic: Mapped[str | None] = mapped_column(String(100))


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "domain_id"),
        # Enforced at DB level: partial unique index (SQLite 3.8+, PostgreSQL)
        # Created via migration; declared here for documentation only — SQLAlchemy
        # does not emit partial indexes via create_all.
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed | removed
    current_level: Mapped[int] = mapped_column(Integer, default=1)
    points: Mapped[int] = mapped_column(Integer, default=0)
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Denormalized flag so the partial unique index (one active domain per student) can
    # exclude the common-assessments track without joining to the domains table.
    is_common_enrollment: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("level_id", "starts_at", "venue"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id", ondelete="RESTRICT"))
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    venue: Mapped[str] = mapped_column(String(120))
    capacity: Mapped[int] = mapped_column(Integer)


class SlotBooking(Base):
    __tablename__ = "slot_bookings"
    __table_args__ = (UniqueConstraint("slot_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="booked")  # booked | cancelled | missed
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)
    change_cancel_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledgement_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id", ondelete="RESTRICT"))
    attempt_no: Mapped[int] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer)
    passed: Mapped[bool] = mapped_column(Boolean)
    skill_gaps: Mapped[list | None] = mapped_column(JSON)
    topic_scores: Mapped[list | None] = mapped_column(JSON)  # every topic's score, not just the weak ones
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (UniqueConstraint("user_id", "domain_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    domain_id: Mapped[int | None] = mapped_column(ForeignKey("domains.id", ondelete="SET NULL"))
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id", ondelete="RESTRICT"))
    code: Mapped[str] = mapped_column(String(40), unique=True)
    first_attempt: Mapped[bool] = mapped_column(Boolean, default=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Snapshot fields (populated at issue time; survive renames)
    student_name: Mapped[str | None] = mapped_column(String(120))
    domain_name: Mapped[str | None] = mapped_column(String(100))
    # Cryptographically secure token (128 bits / 32 hex chars) used in QR verify URLs
    verification_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    # valid | revoked | legacy (legacy = old per-level cert kept for historical display)
    status: Mapped[str] = mapped_column(String(20), default="valid")


class Badge(Base):
    __tablename__ = "badges"
    __table_args__ = (UniqueConstraint("user_id", "level_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id", ondelete="RESTRICT"))
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id", ondelete="RESTRICT"))
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExamKey(Base):
    __tablename__ = "exam_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id", ondelete="RESTRICT"))
    # level_id is optional - used only for keys generated without a slot (by specific level)
    level_id: Mapped[int | None] = mapped_column(ForeignKey("levels.id", ondelete="SET NULL"))
    issued_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # When set, only students who booked this slot can use the key
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("slots.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id", ondelete="RESTRICT"))
    key_id: Mapped[int] = mapped_column(ForeignKey("exam_keys.id", ondelete="RESTRICT"))
    question_ids: Mapped[list] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    violations: Mapped[int] = mapped_column(Integer, default=0)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[int] = mapped_column(Integer)


class AiCache(Base):
    """Stored AI answers so Gemini is only called when the student's data changes."""
    __tablename__ = "ai_cache"
    __table_args__ = (UniqueConstraint("user_id", "kind", "cache_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))
    cache_key: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SkillGapAnalysis(Base):
    __tablename__ = "skill_gap_analysis"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assessment_id: Mapped[int | None] = mapped_column(ForeignKey("attempts.id"))
    overall_summary: Mapped[str] = mapped_column(String(2000))
    readiness: Mapped[str] = mapped_column(String(100), default="developing")
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    gaps: Mapped[list[dict]] = mapped_column(JSON, default=list)
    next_level_priorities: Mapped[list[dict]] = mapped_column(JSON, default=list)
    recommended_plan: Mapped[list[str]] = mapped_column(JSON, default=list)
    priority_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[str] = mapped_column(String(30), default="LOW")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
