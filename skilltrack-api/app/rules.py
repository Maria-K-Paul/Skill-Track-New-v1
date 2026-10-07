"""Platform rules shared by the student and exam routers."""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import ActivityLog, Attempt, Badge, Certificate, Domain, Enrollment, Level, Setting, User

DOMAIN_SELECTION_SEMESTER = 3
COMMON_DOMAIN_NAME = "Common Assessments"

DEFAULT_SETTINGS = {
    "max_attempts": 3,
    "points_to_unlock": 200,
    "first_attempt_points": 30,
    "retry_points": 10,
    "key_minutes": 5,
}

DEFAULT_LEVELS = [  # (name, questions per test, pass mark %, duration min)
    ("Foundations", 20, 50, 30), ("Core Skills", 25, 55, 40), ("Applied Projects", 30, 60, 60),
    ("Advanced", 30, 65, 60), ("Expert", 35, 70, 90),
]


def get_settings(db: Session) -> dict[str, int]:
    """Platform settings: admin-edited values from the database over the defaults."""
    values = dict(DEFAULT_SETTINGS)
    for row in db.scalars(select(Setting)):
        if row.key in values:
            values[row.key] = row.value
    return values


def enrollment_status(enr: Enrollment, level_count: int, used_on_current: int, max_attempts: int) -> str:
    if enr.status == "removed":
        return "Removed"
    if enr.current_level > level_count:
        return "Completed"
    if used_on_current >= 1 and used_on_current >= max_attempts - 1:
        return "At risk"
    return "Active"


def semester_of(user: User) -> int:
    return user.semester or 1


def current_enrollment(db: Session, user: User) -> Enrollment | None:
    """The enrollment the student is working on now: the common track in Semesters 1-2, a domain from Semester 3.
    Active enrollments come first, newest first. Completed enrollments are excluded from the active view."""
    want_common = semester_of(user) < DOMAIN_SELECTION_SEMESTER
    rows = db.execute(
        select(Enrollment, Domain).join(Domain, Domain.id == Enrollment.domain_id)
        .where(Enrollment.user_id == user.id, Enrollment.status != "completed")
        .order_by(Enrollment.status.asc(), Enrollment.id.desc())
    ).all()
    return next((enr for enr, dom in rows if dom.is_common == want_common), None)


def active_domain_enrollment(db: Session, user: User) -> Enrollment | None:
    """The student's single active non-common domain enrollment, or None."""
    return db.scalar(
        select(Enrollment)
        .where(Enrollment.user_id == user.id, Enrollment.status == "active", Enrollment.is_common_enrollment.is_(False))
    )


def ensure_common_enrollment(db: Session, user: User) -> None:
    """Semester 1-2 students are enrolled in the common assessments automatically. Caller commits."""
    if semester_of(user) >= DOMAIN_SELECTION_SEMESTER:
        return
    common = db.scalar(select(Domain).where(Domain.is_common.is_(True)))
    if common is None:
        return
    exists = db.scalar(select(Enrollment.id).where(Enrollment.user_id == user.id, Enrollment.domain_id == common.id))
    if exists is None:
        db.add(Enrollment(user_id=user.id, domain_id=common.id, current_level=semester_of(user), is_common_enrollment=True))
        db.flush()


def level_is_open(user: User, enr: Enrollment, level: Level) -> bool:
    """Common tests open by semester (Semester 1 sits level 1, and so on); domain levels open by progress."""
    if level.domain.is_common:
        return level.number == semester_of(user)
    return enr.current_level == level.number


def check_eligible(db: Session, user: User, level: Level) -> Enrollment:
    """The student must be active in the domain, on this level, with attempts left."""
    enr = db.scalar(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.domain_id == level.domain_id, Enrollment.status == "active",
    ))
    if enr is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not enrolled in this domain")
    if not level_is_open(user, enr, level):
        if level.domain.is_common:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"This key is for the Semester {level.number} test, but you are in Semester {semester_of(user)}. "
                "Ask the invigilator for a Semester " + str(semester_of(user)) + " key.",
            )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This level is not unlocked for you")
    if db.scalar(select(Attempt.id).where(Attempt.user_id == user.id, Attempt.level_id == level.id, Attempt.passed.is_(True))):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You have already cleared this test")
    used = db.scalar(select(func.count(Attempt.id)).where(Attempt.user_id == user.id, Attempt.level_id == level.id)) or 0
    # Common assessments have no attempt cap; only domain tests do
    if not level.domain.is_common and used >= get_settings(db)["max_attempts"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No attempts left")
    return enr


def record_attempt(
    db: Session, user: User, level: Level, enr: Enrollment, score: int, skill_gaps: list[dict] | None,
    topic_scores: list[dict] | None = None,
) -> dict:
    """Store a result and apply the rules: points (bonus on the first attempt), unlock,
    certificate, and removal from a domain after too many failed attempts. Caller commits."""
    cfg = get_settings(db)
    common = level.domain.is_common
    used = db.scalar(select(func.count(Attempt.id)).where(Attempt.user_id == user.id, Attempt.level_id == level.id)) or 0
    attempt_no = used + 1
    passed = score >= level.pass_mark
    db.add(Attempt(
        user_id=user.id, level_id=level.id, attempt_no=attempt_no, score=score, passed=passed,
        skill_gaps=skill_gaps or None, topic_scores=topic_scores or None,
    ))

    outcome = {
        "passed": passed, "attempt_no": attempt_no, "points_earned": 0, "removed": False,
        "certificate": None, "new_semester": None,
    }
    if passed:
        import secrets as _secrets
        first = attempt_no == 1
        outcome["points_earned"] = cfg["first_attempt_points"] if first else cfg["retry_points"]
        enr.points += outcome["points_earned"]
        if not common:
            enr.current_level = level.number + 1
        else:
            # Clearing the common test for your semester moves you up a semester
            user.semester = semester_of(user) + 1
            outcome["new_semester"] = user.semester
            db.add(ActivityLog(user_id=user.id, action=f"{user.name} moved up to Semester {user.semester}"))
        db.flush()

        # Award badge for this level (idempotent)
        badge = db.scalar(
            select(Badge).where(Badge.user_id == user.id, Badge.level_id == level.id).with_for_update()
        )
        if badge is None:
            db.add(Badge(user_id=user.id, domain_id=level.domain_id, level_id=level.id))

        # Check if all levels in this domain are passed → issue domain certificate + complete enrollment
        passed_levels = db.scalar(
            select(func.count(func.distinct(Attempt.level_id)))
            .join(Level, Level.id == Attempt.level_id)
            .where(Attempt.user_id == user.id, Level.domain_id == level.domain_id, Attempt.passed.is_(True))
        ) or 0
        if not common and passed_levels >= len(level.domain.levels):
            # Idempotent lock
            cert = db.scalar(
                select(Certificate)
                .where(Certificate.user_id == user.id, Certificate.domain_id == level.domain_id)
                .with_for_update()
            )
            if cert:
                outcome["certificate"] = cert.code
            else:
                code = f"CERT-D{level.domain_id}-U{user.id}-{_secrets.token_hex(4).upper()}"
                cert = Certificate(
                    user_id=user.id,
                    level_id=level.id,
                    domain_id=level.domain_id,
                    code=code,
                    first_attempt=False,
                    student_name=user.name,
                    domain_name=level.domain.name,
                    verification_token=_secrets.token_hex(16),
                    status="valid",
                )
                db.add(cert)
                outcome["certificate"] = code
            # Mark enrollment completed in the same transaction as the cert
            if enr.status == "active":
                enr.status = "completed"
                enr.completed_at = datetime.now(timezone.utc)
                outcome["domain_completed"] = True
        db.add(ActivityLog(user_id=user.id, action=f"{user.name} cleared {level.name}"))
    elif not common and attempt_no >= cfg["max_attempts"]:
        enr.status = "removed"
        outcome["removed"] = True
        db.add(ActivityLog(user_id=user.id, action=f"{user.name} removed from domain after {cfg['max_attempts']} failed attempts"))
    return outcome
