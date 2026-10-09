"""Remove the demo students created by `python seed.py --demo`, and everything attached to them.

    python purge_demo.py

Only these exact accounts are touched. Accounts registered by real users are left alone.
"""
from sqlalchemy import delete, select

from app import models as m
from app.database import SessionLocal

DEMO_EMAILS = [
    "arun@college.edu", "divya@college.edu", "karthik@college.edu",
    "naveen@college.edu", "meera@college.edu",
]
def main() -> None:
    with SessionLocal() as db:
        ids = list(db.scalars(select(m.User.id).where(m.User.email.in_(DEMO_EMAILS), m.User.role == "student")))
        if not ids:
            print("No demo students found.")
            return

        # Children first, so foreign keys are satisfied
        for model in (m.ExamSession, m.SlotBooking, m.Attempt, m.Certificate, m.Enrollment, m.AiCache, m.ActivityLog):
            db.execute(delete(model).where(model.user_id.in_(ids)))

        # Exam keys that no remaining exam session refers to
        db.execute(delete(m.ExamKey).where(m.ExamKey.id.not_in(select(m.ExamSession.key_id))))

        db.execute(delete(m.User).where(m.User.id.in_(ids)))
        db.commit()
        print(f"Removed {len(ids)} demo students and their data.")


if __name__ == "__main__":
    main()
