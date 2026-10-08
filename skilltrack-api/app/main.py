import os

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models  # noqa: F401  (registers tables on Base.metadata)
from .database import Base, engine
from .noshow import run_noshow_job
from .routers import admin, ai, auth, certificates, exam, owner, slots, student

Base.metadata.create_all(engine)


def _add_missing_columns() -> None:
    """create_all never alters existing tables, so add columns introduced after the database was made."""
    if "slot_id" not in {c["name"] for c in inspect(engine).get_columns("exam_keys")}:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE exam_keys ADD COLUMN slot_id INTEGER REFERENCES slots(id)"))

    level_columns = {c["name"] for c in inspect(engine).get_columns("levels")}
    missing_level_columns = {
        "bloom_level_ratio": "JSON",
        "question_generation_status": "VARCHAR(20) NOT NULL DEFAULT 'idle'",
    }
    for column, definition in missing_level_columns.items():
        if column not in level_columns:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE levels ADD COLUMN {column} {definition}"))


def _complete_finished_enrollments() -> None:
    """Repair enrollments where all levels are passed but status is still active (e.g. seeded data)."""
    import secrets as _secrets
    from datetime import datetime, timezone
    from sqlalchemy.orm import Session as _Session
    from . import models as _m

    with _Session(engine) as db:
        stuck = db.execute(text("""
            SELECT e.id, e.user_id, e.domain_id,
                   (SELECT COUNT(*) FROM levels l WHERE l.domain_id = e.domain_id) AS total_levels,
                   (SELECT COUNT(DISTINCT a.level_id)
                    FROM attempts a JOIN levels l ON l.id = a.level_id
                    WHERE a.user_id = e.user_id AND l.domain_id = e.domain_id AND a.passed IS TRUE) AS passed_levels
            FROM enrollments e
            WHERE e.status = 'active' AND e.is_common_enrollment IS FALSE
        """)).fetchall()

        now = datetime.now(timezone.utc)
        for row in stuck:
            if row.passed_levels < row.total_levels:
                continue
            enr = db.get(_m.Enrollment, row.id)
            if enr is None:
                continue
            enr.status = "completed"
            enr.completed_at = now
            # Issue missing domain certificate
            existing = db.scalar(
                text("SELECT id FROM certificates WHERE user_id = :u AND domain_id = :d"),
                {"u": row.user_id, "d": row.domain_id},
            )
            if existing is None:
                last_level = db.scalar(
                    text("SELECT id FROM levels WHERE domain_id = :d ORDER BY number DESC LIMIT 1"),
                    {"d": row.domain_id},
                )
                user = db.get(_m.User, row.user_id)
                domain = db.get(_m.Domain, row.domain_id)
                if last_level and user and domain:
                    db.add(_m.Certificate(
                        user_id=row.user_id,
                        level_id=last_level,
                        domain_id=row.domain_id,
                        code=f"CERT-D{row.domain_id}-U{row.user_id}-{_secrets.token_hex(4).upper()}",
                        first_attempt=False,
                        issued_at=now,
                        student_name=user.name,
                        domain_name=domain.name,
                        verification_token=_secrets.token_hex(16),
                        status="valid",
                    ))
        db.commit()


_add_missing_columns()
_complete_finished_enrollments()

app = FastAPI(title="SkillTrack API")
app.add_middleware(
    CORSMiddleware,
    # Local development: the Vite dev server may pick any free port (5173, 5174, ...)
    # Deployed frontend URL(s), comma-separated, e.g. CORS_ORIGINS=https://skilltrack.onrender.com
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(student.router)
app.include_router(exam.router)
app.include_router(owner.router)
app.include_router(admin.router)
app.include_router(ai.router)
app.include_router(slots.router)
app.include_router(certificates.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# ── No-show scheduler ──────────────────────────────────────────────────────────
_scheduler = BackgroundScheduler(timezone="UTC")
_scheduler.add_job(run_noshow_job, "interval", minutes=15, id="noshow_job", replace_existing=True)
_scheduler.start()


@app.on_event("shutdown")
def _shutdown_scheduler():
    _scheduler.shutdown(wait=False)
