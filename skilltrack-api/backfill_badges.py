"""Idempotent backfill: run this once (or any number of times) after migrate.py.

What it does:
  1. Awards badges for every already-passed level attempt (one badge per student per level).
  2. Issues domain completion certificates for enrollments whose students passed all levels
     but have no domain cert yet.
  3. Populates student_name, domain_name, verification_token, status on existing domain certs.
  4. Marks old per-level certs (domain_id IS NULL) as status='legacy'.

Usage:
    cd skilltrack-api
    .venv/Scripts/python.exe backfill_badges.py        # Windows
    python backfill_badges.py                          # Linux / macOS
"""
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Attempt, Badge, Certificate, Domain, Enrollment, Level, User


def run(db) -> None:
    print("=== SkillTrack backfill: badges + certificate enrichment ===")

    # ── Step 1: badges for passed attempts ───────────────────────────────────
    existing_badges: set[tuple[int, int]] = set(
        db.execute(select(Badge.user_id, Badge.level_id)).all()
    )

    passed = db.execute(
        select(Attempt.user_id, Attempt.level_id, Level.domain_id, Attempt.taken_at)
        .join(Level, Level.id == Attempt.level_id)
        .where(Attempt.passed.is_(True))
    ).all()

    badges_created = 0
    for user_id, level_id, domain_id, taken_at in passed:
        if (user_id, level_id) not in existing_badges:
            db.add(Badge(user_id=user_id, domain_id=domain_id, level_id=level_id, awarded_at=taken_at))
            existing_badges.add((user_id, level_id))
            badges_created += 1

    db.flush()
    print(f"  Badges created: {badges_created}")

    # ── Step 2: enrich existing domain certs ─────────────────────────────────
    certs_updated = 0
    for cert in db.scalars(select(Certificate)).all():
        changed = False
        if cert.domain_id is None:
            if cert.status != "legacy":
                cert.status = "legacy"
                changed = True
        else:
            if cert.status not in ("valid", "revoked"):
                cert.status = "valid"
                changed = True
            if not cert.student_name:
                holder = db.get(User, cert.user_id)
                if holder:
                    cert.student_name = holder.name
                    changed = True
            if not cert.domain_name:
                domain = db.get(Domain, cert.domain_id)
                if domain:
                    cert.domain_name = domain.name
                    changed = True
            if not cert.verification_token:
                cert.verification_token = secrets.token_hex(16)
                changed = True
        if changed:
            certs_updated += 1

    db.flush()
    print(f"  Certificates enriched: {certs_updated}")

    # ── Step 3: issue certs for completed-but-uncertified enrollments ─────────
    domains = {d.id: d for d in db.scalars(select(Domain)).all()}

    # Passed level IDs per (user, domain)
    passed_by_user_domain: dict[tuple[int, int], set[int]] = {}
    for uid, lvl_id, dom_id in db.execute(
        select(Attempt.user_id, Attempt.level_id, Level.domain_id)
        .join(Level, Level.id == Attempt.level_id)
        .where(Attempt.passed.is_(True))
    ):
        passed_by_user_domain.setdefault((uid, dom_id), set()).add(lvl_id)

    existing_domain_cert_keys: set[tuple[int, int]] = set(
        db.execute(
            select(Certificate.user_id, Certificate.domain_id)
            .where(Certificate.domain_id.is_not(None))
        ).all()
    )

    certs_issued = 0
    for enr in db.scalars(select(Enrollment)).all():
        domain = domains.get(enr.domain_id)
        if domain is None or not domain.levels:
            continue
        total = len(domain.levels)
        passed_ids = passed_by_user_domain.get((enr.user_id, enr.domain_id), set())
        if len(passed_ids) < total:
            continue
        if (enr.user_id, enr.domain_id) in existing_domain_cert_keys:
            continue

        holder = db.get(User, enr.user_id)
        if holder is None:
            continue
        last_level = max(domain.levels, key=lambda l: l.number)

        code = f"CERT-D{enr.domain_id}-U{enr.user_id}-{secrets.token_hex(4).upper()}"
        while db.scalar(select(Certificate.id).where(Certificate.code == code)):
            code = f"CERT-D{enr.domain_id}-U{enr.user_id}-{secrets.token_hex(4).upper()}"

        db.add(Certificate(
            user_id=enr.user_id,
            domain_id=enr.domain_id,
            level_id=last_level.id,
            code=code,
            first_attempt=False,
            student_name=holder.name,
            domain_name=domain.name,
            verification_token=secrets.token_hex(16),
            status="valid",
        ))
        existing_domain_cert_keys.add((enr.user_id, enr.domain_id))
        certs_issued += 1

    db.flush()
    print(f"  Domain certificates issued: {certs_issued}")

    db.commit()
    print("=== Backfill complete ===")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()
