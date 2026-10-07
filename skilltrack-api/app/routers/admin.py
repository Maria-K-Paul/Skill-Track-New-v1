from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from ..deps import require_roles
from ..models import (
    ActivityLog, Attempt, Certificate, Domain, Enrollment, Level, Setting, Slot, User,
)
from ..rules import (
    COMMON_DOMAIN_NAME, DEFAULT_LEVELS, DEFAULT_SETTINGS, DOMAIN_SELECTION_SEMESTER,
    enrollment_status, get_settings, semester_of,
)
from ..schemas import AssignCommonIn, DomainIn, DomainMetaPatch, DomainPatch, PromoteIn, SettingsIn, StaffIn, UserOut, UserPatch
from ..security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])

admin_only = require_roles("admin")


# ---------- Analytics ----------

@router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    students = db.scalar(select(func.count(User.id)).where(User.role == "student")) or 0
    attempts = db.scalar(select(func.count(Attempt.id))) or 0
    passed = db.scalar(select(func.count(Attempt.id)).where(Attempt.passed.is_(True))) or 0
    certificates = db.scalar(select(func.count(Certificate.id))) or 0
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = db.scalar(select(func.count(Attempt.id)).where(Attempt.taken_at >= month_start)) or 0

    domain_rows = db.execute(
        select(Domain.name, func.avg(Attempt.score), func.count(Attempt.id))
        .select_from(Domain)
        .outerjoin(Level, Level.domain_id == Domain.id)
        .outerjoin(Attempt, Attempt.level_id == Level.id)
        .group_by(Domain.id, Domain.name).order_by(Domain.id)
    ).all()

    sem_rows = db.execute(
        select(User.semester, Attempt.passed, func.count(Attempt.id))
        .join(User, User.id == Attempt.user_id).group_by(User.semester, Attempt.passed)
    ).all()
    by_semester = {s: {"pass": 0, "fail": 0} for s in range(1, 7)}
    for semester, did_pass, n in sem_rows:
        if semester in by_semester:
            by_semester[semester]["pass" if did_pass else "fail"] += n

    affected: dict[str, set[int]] = {}
    for user_id, gaps in db.execute(select(Attempt.user_id, Attempt.skill_gaps).where(Attempt.skill_gaps.is_not(None))):
        for gap in gaps or []:
            affected.setdefault(gap["topic"], set()).add(user_id)
    top_gaps = sorted(affected.items(), key=lambda kv: len(kv[1]), reverse=True)[:5]

    return {
        "kpis": {
            "students": students,
            "pass_rate": round(passed / attempts * 100) if attempts else None,
            "certificates": certificates,
            "tests_this_month": this_month,
        },
        "domain_performance": [
            {"domain": name, "avg": round(float(avg)) if avg is not None else None, "attempts": n}
            for name, avg, n in domain_rows
        ],
        "semester_results": [{"sem": f"Sem {s}", **counts} for s, counts in by_semester.items()],
        "skill_gaps": [{"topic": topic, "students": len(users)} for topic, users in top_gaps],
    }


@router.get("/students")
def students(
    department: str | None = None, semester: int | None = None, domain: str | None = None,
    db: Session = Depends(get_db), _: User = Depends(admin_only),
):
    cfg = get_settings(db)
    query = select(User).where(User.role == "student").order_by(User.name)
    if department:
        query = query.where(User.department == department)
    if semester:
        query = query.where(User.semester == semester)
    users = db.scalars(query).all()

    domains = {d.id: d for d in db.scalars(select(Domain))}
    sem_of = {u.id: semester_of(u) for u in users}
    # A student's current enrollment: the common track in Semesters 1-2, a domain after that.
    # Active ones first, newest first.
    enrollment_of: dict[int, Enrollment] = {}
    for enr in db.scalars(select(Enrollment).order_by(Enrollment.status.asc(), Enrollment.id.desc())):
        if enr.user_id in sem_of and domains[enr.domain_id].is_common == (sem_of[enr.user_id] < DOMAIN_SELECTION_SEMESTER):
            enrollment_of.setdefault(enr.user_id, enr)
    passed = {(user_id, level_id) for user_id, level_id in db.execute(select(Attempt.user_id, Attempt.level_id).where(Attempt.passed.is_(True)))}

    attempt_total: dict[int, int] = {}
    attempt_on_level: dict[tuple[int, int], int] = {}
    for user_id, level_id in db.execute(select(Attempt.user_id, Attempt.level_id)):
        attempt_total[user_id] = attempt_total.get(user_id, 0) + 1
        attempt_on_level[(user_id, level_id)] = attempt_on_level.get((user_id, level_id), 0) + 1
    cert_total = dict(db.execute(select(Certificate.user_id, func.count(Certificate.id)).group_by(Certificate.user_id)).all())

    rows = []
    for u in users:
        enr = enrollment_of.get(u.id)
        cleared = None  # only meaningful for the Semester 1-2 common test
        if enr is None:
            state, domain_name = "Not enrolled", None
        else:
            dom = domains[enr.domain_id]
            if dom.is_common:
                test = next((lv for lv in dom.levels if lv.number == sem_of[u.id]), None)
                cleared = bool(test and (u.id, test.id) in passed)
                state = "Cleared" if cleared else "Active"
            else:
                current = next((lv for lv in dom.levels if lv.number == enr.current_level), None)
                used = attempt_on_level.get((u.id, current.id), 0) if current else 0
                state = enrollment_status(enr, len(dom.levels), used, cfg["max_attempts"])
            domain_name = dom.name
        if domain and domain_name != domain:
            continue
        rows.append({
            "id": u.id, "name": u.name, "reg_no": u.reg_no, "department": u.department, "semester": u.semester,
            "domain": domain_name, "attempts": attempt_total.get(u.id, 0), "certificates": cert_total.get(u.id, 0),
            "status": state, "cleared": cleared,
        })

    return {
        "students": rows,
        "departments": sorted({d for d in db.scalars(select(User.department).where(User.role == "student")) if d}),
        "domains": [d.name for d in domains.values()],
    }


@router.post("/promote")
def promote(body: PromoteIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    """Move the chosen students up one semester (Semester 6 is the last)."""
    students = db.scalars(select(User).where(User.id.in_(body.student_ids), User.role == "student")).all()
    promoted, at_final = 0, []
    for s in students:
        if semester_of(s) >= 6:
            at_final.append(s.name)
            continue
        s.semester = semester_of(s) + 1
        promoted += 1
    db.add(ActivityLog(user_id=admin.id, action=f"{admin.name} promoted {promoted} student(s) to the next semester"))
    db.commit()
    return {"promoted": promoted, "already_final": at_final}


@router.post("/assign-common")
def assign_common(body: AssignCommonIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    """One-click action for Semesters 1-2: ensure the Common Assessments domain exists,
    auto-enroll every student in that semester, and create an exam slot."""
    # 1. Ensure the Common Assessments domain + its levels exist
    common = db.scalar(select(Domain).where(Domain.is_common.is_(True)))
    if common is None:
        common = Domain(name=COMMON_DOMAIN_NAME, is_common=True)
        db.add(common)
        db.flush()
        for number, (level_name, questions, pass_mark, minutes) in enumerate(DEFAULT_LEVELS, start=1):
            db.add(Level(
                domain_id=common.id, number=number, name=f"Semester {number} Assessment",
                question_count=questions, pass_mark=pass_mark, duration_min=minutes,
            ))
        db.flush()

    # 2. Find the level that corresponds to the requested semester
    level = next((lv for lv in common.levels if lv.number == body.semester), None)
    if level is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No level for Semester {body.semester} in Common Assessments")

    # 3. Enroll all students in that semester who are not already enrolled
    students = db.scalars(
        select(User).where(User.role == "student", User.semester == body.semester)
    ).all()
    enrolled_ids = set(db.scalars(
        select(Enrollment.user_id).where(Enrollment.domain_id == common.id)
    ))
    enrolled_count = 0
    for s in students:
        if s.id not in enrolled_ids:
            db.add(Enrollment(user_id=s.id, domain_id=common.id, current_level=body.semester))
            enrolled_count += 1

    # 4. Create the exam slot
    slot = Slot(level_id=level.id, starts_at=body.starts_at, venue=body.venue.strip(), capacity=body.capacity)
    db.add(slot)

    db.add(ActivityLog(
        user_id=admin.id,
        action=f"{admin.name} assigned Semester {body.semester} common assessment — enrolled {enrolled_count} student(s), slot at {body.venue}",
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This slot is already enrolled/created.")
    return {
        "enrolled": enrolled_count,
        "already_enrolled": len(students) - enrolled_count,
        "total_students": len(students),
        "slot_id": slot.id,
        "level_name": level.name,
    }


@router.get("/activity")
def activity(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    logs = db.scalars(select(ActivityLog).order_by(ActivityLog.id.desc()).limit(15)).all()
    return [{"id": a.id, "action": a.action, "created_at": a.created_at} for a in logs]


# ---------- Users ----------

@router.get("/users", response_model=list[UserOut])
def list_staff(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return db.scalars(select(User).where(User.role != "student").order_by(User.role, User.name)).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_staff(body: StaffIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        name=body.name, email=body.email, role=body.role, department=body.department,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.add(ActivityLog(user_id=admin.id, action=f"{admin.name} created {body.role} account for {body.name}"))
    db.commit()
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def set_user_active(user_id: int, body: UserPatch, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")
    user.is_active = body.is_active
    db.add(ActivityLog(user_id=admin.id, action=f"{admin.name} {'activated' if body.is_active else 'deactivated'} {user.name}"))
    db.commit()
    return user


# ---------- Domains ----------

@router.get("/domains")
def list_domains(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    enrolled = dict(db.execute(select(Enrollment.domain_id, func.count(Enrollment.id)).group_by(Enrollment.domain_id)).all())
    owners = db.scalars(select(User).where(User.role == "owner").order_by(User.name)).all()
    return {
        "domains": [
            {"id": d.id, "name": d.name, "owner_id": d.owner_id, "students": enrolled.get(d.id, 0), "levels": len(d.levels)}
            for d in db.scalars(select(Domain).order_by(Domain.id))
        ],
        "owners": [{"id": o.id, "name": o.name} for o in owners],
    }


@router.post("/domains", status_code=status.HTTP_201_CREATED)
def create_domain(body: DomainIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    name = body.name.strip()
    if db.scalar(select(Domain).where(func.lower(Domain.name) == name.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "A domain with this name already exists")
    domain = Domain(name=name)
    db.add(domain)
    db.flush()
    for number, (level_name, questions, pass_mark, minutes) in enumerate(DEFAULT_LEVELS, start=1):
        db.add(Level(
            domain_id=domain.id, number=number, name=f"Level {number} · {level_name}",
            question_count=questions, pass_mark=pass_mark, duration_min=minutes,
        ))
    db.add(ActivityLog(user_id=admin.id, action=f"{admin.name} created domain {name}"))
    db.commit()
    return {"id": domain.id}


@router.patch("/domains/{domain_id}")
def assign_owner(domain_id: int, body: DomainPatch, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    domain = db.get(Domain, domain_id)
    if domain is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found")
    if body.owner_id is not None:
        owner = db.get(User, body.owner_id)
        if owner is None or owner.role != "owner":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pick a user with the track owner role")
        other = db.scalar(select(Domain).where(Domain.owner_id == owner.id, Domain.id != domain.id))
        if other:
            raise HTTPException(status.HTTP_409_CONFLICT, f"{owner.name} already owns {other.name}")
    domain.owner_id = body.owner_id
    db.add(ActivityLog(user_id=admin.id, action=f"{admin.name} updated the owner of {domain.name}"))
    db.commit()
    return {"id": domain.id, "owner_id": domain.owner_id}


@router.patch("/domains/{domain_id}/meta")
def update_domain_meta(
    domain_id: int, body: DomainMetaPatch,
    db: Session = Depends(get_db), admin: User = Depends(admin_only),
):
    """Set description and difficulty for a domain (used by admin to enrich the domain catalogue)."""
    domain = db.get(Domain, domain_id)
    if domain is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found")
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(domain, field, value)
    db.commit()
    return {"id": domain.id, "description": domain.description, "difficulty": domain.difficulty}


# ---------- Settings ----------

@router.get("/settings")
def read_settings(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return get_settings(db)


@router.put("/settings")
def save_settings(body: SettingsIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    for key in DEFAULT_SETTINGS:
        value = getattr(body, key)
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
    db.add(ActivityLog(user_id=admin.id, action=f"{admin.name} updated platform settings"))
    db.commit()
    return get_settings(db)
