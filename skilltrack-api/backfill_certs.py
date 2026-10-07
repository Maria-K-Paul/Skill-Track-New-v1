import sqlite3
import secrets
import os

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from app.models import Attempt, Certificate, Domain, Level, User

def backfill():
    # Setup sqlalchemy session
    engine = create_engine("sqlite:///skilltrack.db")
    with Session(engine) as db:
        users = db.scalars(select(User).where(User.role == "student")).all()
        for user in users:
            # Get all domains
            domains = db.scalars(select(Domain)).all()
            for domain in domains:
                # Check if all levels in this domain are passed by the user
                passed_levels = db.scalar(
                    select(func.count(func.distinct(Attempt.level_id)))
                    .join(Level, Level.id == Attempt.level_id)
                    .where(Attempt.user_id == user.id, Level.domain_id == domain.id, Attempt.passed.is_(True))
                ) or 0
                
                if passed_levels >= len(domain.levels) and len(domain.levels) > 0:
                    # Idempotent check
                    cert = db.scalar(select(Certificate).where(Certificate.user_id == user.id, Certificate.domain_id == domain.id))
                    if not cert:
                        code = f"CERT-D{domain.id}-U{user.id}-{secrets.token_hex(4).upper()}"
                        # level_id is not nullable, so pick the last level
                        last_level = domain.levels[-1]
                        new_cert = Certificate(user_id=user.id, level_id=last_level.id, domain_id=domain.id, code=code, first_attempt=False)
                        db.add(new_cert)
                        print(f"Issued backfill certificate {code} to {user.name} for domain {domain.name}")
        db.commit()
        print("Backfill complete.")

if __name__ == "__main__":
    backfill()
