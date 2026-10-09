#!/usr/bin/env python3
"""
Universal database migration script for SkillTrack.
Works with SQLite and PostgreSQL.
Run this before starting the application to update the database schema.
"""
import os
import re
import sys
from sqlalchemy import create_engine, text, inspect
from app.config import DATABASE_URL

def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def table_exists(inspector, table_name: str) -> bool:
    """Check if a table exists."""
    return table_name in inspector.get_table_names()

def index_exists(conn, index_name: str) -> bool:
    """Check if an index exists (works for both SQLite and PostgreSQL)."""
    is_sqlite = 'sqlite' in DATABASE_URL
    if is_sqlite:
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=:name"
        ), {"name": index_name})
    else:
        result = conn.execute(text(
            "SELECT indexname FROM pg_indexes WHERE indexname=:name"
        ), {"name": index_name})
    return result.first() is not None

def _readiness_category(value: str | None) -> tuple[str, str | None]:
    """Convert legacy free-form readiness values while retaining narrative details."""
    original = (value or "").strip()
    normalized = re.sub(r"[\s-]+", "_", original.upper())
    if normalized in {"READY", "DEVELOPING", "NOT_READY"}:
        return normalized, None

    if re.search(r"\bnot[\s_-]+(?:(?:currently|yet)[\s_-]+)?ready\b", original, re.IGNORECASE):
        category = "NOT_READY"
    elif re.search(r"\b(?:developing|in[\s_-]+progress|working\s+toward)\b", original, re.IGNORECASE):
        category = "DEVELOPING"
    elif re.search(r"\bready\b", original, re.IGNORECASE):
        category = "READY"
    else:
        category = "DEVELOPING"
    return category, original or None

def run_migration():
    """Run all database migrations."""
    engine = create_engine(DATABASE_URL)
    is_sqlite = 'sqlite' in DATABASE_URL
    print(f"🔄 Starting migration for {engine.dialect.name} database...")

    with engine.begin() as conn:
        inspector = inspect(engine)

        # ============================================================
        # 1. Domain table: description, difficulty
        # ============================================================
        if table_exists(inspector, 'domains'):
            print("📋 Migrating domains table...")
            if not column_exists(inspector, 'domains', 'description'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE domains ADD COLUMN description TEXT"))
                else:
                    conn.execute(text("ALTER TABLE domains ADD COLUMN description VARCHAR(500)"))
                print("  ✓ Added domains.description")

            if not column_exists(inspector, 'domains', 'difficulty'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE domains ADD COLUMN difficulty TEXT"))
                else:
                    conn.execute(text("ALTER TABLE domains ADD COLUMN difficulty VARCHAR(20)"))
                print("  ✓ Added domains.difficulty")

        # ============================================================
        # 2. Enrollments: enrolled_at, completed_at, is_common_enrollment
        # ============================================================
        if table_exists(inspector, 'enrollments'):
            print("📋 Migrating enrollments table...")
            if not column_exists(inspector, 'enrollments', 'enrolled_at'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE enrollments ADD COLUMN enrolled_at TEXT"))
                else:
                    conn.execute(text("ALTER TABLE enrollments ADD COLUMN enrolled_at TIMESTAMP WITH TIME ZONE"))
                print("  ✓ Added enrollments.enrolled_at")

            if not column_exists(inspector, 'enrollments', 'completed_at'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE enrollments ADD COLUMN completed_at TEXT"))
                else:
                    conn.execute(text("ALTER TABLE enrollments ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE"))
                print("  ✓ Added enrollments.completed_at")

            if not column_exists(inspector, 'enrollments', 'is_common_enrollment'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE enrollments ADD COLUMN is_common_enrollment INTEGER NOT NULL DEFAULT 0"))
                else:
                    conn.execute(text("ALTER TABLE enrollments ADD COLUMN is_common_enrollment BOOLEAN NOT NULL DEFAULT FALSE"))
                print("  ✓ Added enrollments.is_common_enrollment")

            # Backfill is_common_enrollment on every run, not only when the column is added: an older app
            # version still running against this database creates enrollments without setting it
            if is_sqlite:
                conn.execute(text("""
                    UPDATE enrollments
                    SET is_common_enrollment = CASE
                        WHEN domain_id IN (SELECT id FROM domains WHERE is_common = 1) THEN 1
                        ELSE 0
                    END
                """))
            else:
                # PostgreSQL requires TRUE/FALSE for boolean columns
                conn.execute(text("""
                    UPDATE enrollments
                    SET is_common_enrollment = CASE
                        WHEN domain_id IN (SELECT id FROM domains WHERE is_common = TRUE) THEN TRUE
                        ELSE FALSE
                    END
                """))

            # Create partial unique index: one active non-common enrollment per student
            if not index_exists(conn, 'uq_one_active_domain_enrollment'):
                if is_sqlite:
                    conn.execute(text("""
                        CREATE UNIQUE INDEX uq_one_active_domain_enrollment
                        ON enrollments(user_id)
                        WHERE status = 'active' AND is_common_enrollment = 0
                    """))
                else:
                    conn.execute(text("""
                        CREATE UNIQUE INDEX uq_one_active_domain_enrollment
                        ON enrollments(user_id)
                        WHERE status = 'active' AND is_common_enrollment = false
                    """))
                print("  ✓ Created partial unique index for one active domain per student")

        # ============================================================
        # 3. Slots: domain_id + UniqueConstraint
        # ============================================================
        if table_exists(inspector, 'slots'):
            print("📋 Migrating slots table...")
            if not column_exists(inspector, 'slots', 'domain_id'):
                # CRITICAL: Add domain_id column
                if is_sqlite:
                    conn.execute(text("ALTER TABLE slots ADD COLUMN domain_id INTEGER REFERENCES domains(id)"))
                else:
                    conn.execute(text("ALTER TABLE slots ADD COLUMN domain_id INTEGER REFERENCES domains(id)"))
                print("  ✓ Added slots.domain_id")

            # Backfill domain_id from level_id on every run: an older app version still running against this
            # database creates slots without it
            filled = conn.execute(text("""
                UPDATE slots
                SET domain_id = (SELECT domain_id FROM levels WHERE levels.id = slots.level_id)
                WHERE domain_id IS NULL
            """)).rowcount
            if filled:
                print(f"  ✓ Backfilled slots.domain_id from levels ({filled} slot(s))")

            # Remove duplicates before creating unique index
            if not index_exists(conn, 'idx_slots_level_time_venue'):
                # First, update foreign key references before deleting duplicates
                if is_sqlite:
                    # SQLite: Create mapping and update exam_keys
                    conn.execute(text("""
                        UPDATE exam_keys
                        SET slot_id = (
                            SELECT MIN(s2.rowid)
                            FROM slots s1
                            JOIN slots s2 ON s1.level_id = s2.level_id
                                AND s1.starts_at = s2.starts_at
                                AND s1.venue = s2.venue
                            WHERE s1.rowid = exam_keys.slot_id
                        )
                        WHERE slot_id IS NOT NULL
                    """))

                    # Now safe to delete duplicates
                    conn.execute(text("""
                        DELETE FROM slots
                        WHERE rowid NOT IN (
                            SELECT MIN(rowid)
                            FROM slots
                            GROUP BY level_id, starts_at, venue
                        )
                    """))
                else:
                    # PostgreSQL: Update exam_keys to point to the slot we're keeping
                    conn.execute(text("""
                        UPDATE exam_keys
                        SET slot_id = keeper.id
                        FROM (
                            SELECT
                                s1.id as old_id,
                                MIN(s2.id) as id
                            FROM slots s1
                            JOIN slots s2 ON s1.level_id = s2.level_id
                                AND s1.starts_at = s2.starts_at
                                AND s1.venue = s2.venue
                            GROUP BY s1.id
                        ) keeper
                        WHERE exam_keys.slot_id = keeper.old_id
                    """))
                    print("  ✓ Updated exam_keys foreign key references")

                    # Now safe to delete duplicates (use id instead of ctid for clarity)
                    conn.execute(text("""
                        DELETE FROM slots
                        WHERE id NOT IN (
                            SELECT MIN(id)
                            FROM slots
                            GROUP BY level_id, starts_at, venue
                        )
                    """))

                print(f"  ✓ Removed duplicate slots (keeping first occurrence)")

                # Now create the unique index
                conn.execute(text(
                    "CREATE UNIQUE INDEX idx_slots_level_time_venue ON slots (level_id, starts_at, venue)"
                ))
                print("  ✓ Created unique index on slots (level_id, starts_at, venue)")

        # ============================================================
        # 4. SlotBookings: status, booked_at, change_cancel_deadline, acknowledgement_acknowledged_at
        # ============================================================
        if table_exists(inspector, 'slot_bookings'):
            print("📋 Migrating slot_bookings table...")
            if not column_exists(inspector, 'slot_bookings', 'status'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE slot_bookings ADD COLUMN status TEXT NOT NULL DEFAULT 'booked'"))
                else:
                    conn.execute(text("ALTER TABLE slot_bookings ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'booked'"))
                print("  ✓ Added slot_bookings.status")

            if not column_exists(inspector, 'slot_bookings', 'booked_at'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE slot_bookings ADD COLUMN booked_at TEXT"))
                else:
                    conn.execute(text("ALTER TABLE slot_bookings ADD COLUMN booked_at TIMESTAMP WITH TIME ZONE"))
                print("  ✓ Added slot_bookings.booked_at")

            if not column_exists(inspector, 'slot_bookings', 'change_cancel_deadline'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE slot_bookings ADD COLUMN change_cancel_deadline TEXT"))
                else:
                    conn.execute(text("ALTER TABLE slot_bookings ADD COLUMN change_cancel_deadline TIMESTAMP WITH TIME ZONE"))
                print("  ✓ Added slot_bookings.change_cancel_deadline")

            if not column_exists(inspector, 'slot_bookings', 'acknowledgement_acknowledged_at'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE slot_bookings ADD COLUMN acknowledgement_acknowledged_at TEXT"))
                else:
                    conn.execute(text("ALTER TABLE slot_bookings ADD COLUMN acknowledgement_acknowledged_at TIMESTAMP WITH TIME ZONE"))
                print("  ✓ Added slot_bookings.acknowledgement_acknowledged_at")

        # ============================================================
        # 5. Certificates: domain_id, student_name, domain_name, verification_token, status
        # ============================================================
        if table_exists(inspector, 'certificates'):
            print("📋 Migrating certificates table...")
            if not column_exists(inspector, 'certificates', 'domain_id'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN domain_id INTEGER REFERENCES domains(id)"))
                else:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN domain_id INTEGER REFERENCES domains(id)"))
                print("  ✓ Added certificates.domain_id")

                # Backfill domain_id from level_id
                conn.execute(text("""
                    UPDATE certificates
                    SET domain_id = (SELECT domain_id FROM levels WHERE levels.id = certificates.level_id)
                    WHERE domain_id IS NULL
                """))
                print("  ✓ Backfilled certificates.domain_id")

            if not column_exists(inspector, 'certificates', 'student_name'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN student_name TEXT"))
                else:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN student_name VARCHAR(120)"))
                print("  ✓ Added certificates.student_name")

            if not column_exists(inspector, 'certificates', 'domain_name'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN domain_name TEXT"))
                else:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN domain_name VARCHAR(100)"))
                print("  ✓ Added certificates.domain_name")

            if not column_exists(inspector, 'certificates', 'verification_token'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN verification_token TEXT"))
                else:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN verification_token VARCHAR(64)"))
                print("  ✓ Added certificates.verification_token")

                if not index_exists(conn, 'idx_certs_verif_token'):
                    if is_sqlite:
                        conn.execute(text(
                            "CREATE UNIQUE INDEX idx_certs_verif_token ON certificates (verification_token) WHERE verification_token IS NOT NULL"
                        ))
                    else:
                        conn.execute(text(
                            "CREATE UNIQUE INDEX idx_certs_verif_token ON certificates (verification_token) WHERE verification_token IS NOT NULL"
                        ))
                    print("  ✓ Created index on verification_token")

            if not column_exists(inspector, 'certificates', 'status'):
                if is_sqlite:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN status TEXT DEFAULT 'valid'"))
                else:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN status VARCHAR(20) DEFAULT 'valid'"))
                print("  ✓ Added certificates.status")

        # ============================================================
        # 6. Badges table (new table)
        # ============================================================
        if not table_exists(inspector, 'badges'):
            print("📋 Creating badges table...")
            if is_sqlite:
                conn.execute(text("""
                    CREATE TABLE badges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        domain_id INTEGER NOT NULL REFERENCES domains(id),
                        level_id INTEGER NOT NULL REFERENCES levels(id),
                        awarded_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                """))
            else:
                conn.execute(text("""
                    CREATE TABLE badges (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        domain_id INTEGER NOT NULL REFERENCES domains(id),
                        level_id INTEGER NOT NULL REFERENCES levels(id),
                        awarded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
            print("  ✓ Created badges table")

            if not index_exists(conn, 'idx_badges_user_level'):
                conn.execute(text(
                    "CREATE UNIQUE INDEX idx_badges_user_level ON badges (user_id, level_id)"
                ))
                print("  ✓ Created unique index on badges (user_id, level_id)")

        # ============================================================
        # 7. ExamKeys: slot_id (may already exist from earlier migration)
        # ============================================================
        if table_exists(inspector, 'exam_keys'):
            if not column_exists(inspector, 'exam_keys', 'slot_id'):
                print("📋 Migrating exam_keys table...")
                if is_sqlite:
                    conn.execute(text("ALTER TABLE exam_keys ADD COLUMN slot_id INTEGER REFERENCES slots(id)"))
                else:
                    conn.execute(text("ALTER TABLE exam_keys ADD COLUMN slot_id INTEGER REFERENCES slots(id)"))
                print("  ✓ Added exam_keys.slot_id")

        # ============================================================
        # 8. ExamKeys: domain_id, and level_id optional (slot-based keys)
        #    Databases created before slot-based keys have no domain_id and require level_id,
        #    so listing or issuing keys fails until these are changed.
        # ============================================================
        if table_exists(inspector, 'exam_keys'):
            if not column_exists(inspector, 'exam_keys', 'domain_id'):
                print("📋 Migrating exam_keys table (domain_id)...")
                conn.execute(text("ALTER TABLE exam_keys ADD COLUMN domain_id INTEGER REFERENCES domains(id)"))
                print("  ✓ Added exam_keys.domain_id")
            # Existing keys get the domain of their slot, or else of their level
            conn.execute(text("""
                UPDATE exam_keys SET domain_id = COALESCE(
                    (SELECT s.domain_id FROM slots s WHERE s.id = exam_keys.slot_id),
                    (SELECT l.domain_id FROM levels l WHERE l.id = exam_keys.level_id))
                WHERE domain_id IS NULL
            """))
            level_col = next((c for c in inspector.get_columns('exam_keys') if c['name'] == 'level_id'), None)
            if level_col is not None and not level_col['nullable']:
                if is_sqlite:
                    print("  ⚠️ exam_keys.level_id is still required (SQLite cannot relax it in place); recreate the table to issue slot-only keys")
                else:
                    conn.execute(text("ALTER TABLE exam_keys ALTER COLUMN level_id DROP NOT NULL"))
                    print("  ✓ Made exam_keys.level_id optional")

        # ============================================================
        # 9. Skill-gap reports: narrative summary and categorical readiness
        # ============================================================
        if table_exists(inspector, 'skill_gap_analysis'):
            print("📋 Migrating skill_gap_analysis report fields...")
            if not is_sqlite:
                conn.execute(text(
                    "ALTER TABLE skill_gap_analysis "
                    "ALTER COLUMN overall_summary TYPE TEXT USING overall_summary::TEXT"
                ))

            rows = conn.execute(text(
                "SELECT id, overall_summary, readiness FROM skill_gap_analysis"
            )).mappings().all()
            for row in rows:
                category, details = _readiness_category(row["readiness"])
                summary = row["overall_summary"] or ""
                if details and details.casefold() not in summary.casefold():
                    summary = f"{summary.rstrip()}\n\nReadiness details: {details}".strip()
                if category != row["readiness"] or summary != row["overall_summary"]:
                    conn.execute(
                        text(
                            "UPDATE skill_gap_analysis "
                            "SET overall_summary = :summary, readiness = :readiness WHERE id = :id"
                        ),
                        {"summary": summary, "readiness": category, "id": row["id"]},
                    )

            if not is_sqlite:
                conn.execute(text(
                    "ALTER TABLE skill_gap_analysis "
                    "ALTER COLUMN readiness TYPE VARCHAR(20) USING readiness::VARCHAR(20)"
                ))
            print("  ✓ Normalized readiness values and updated report field types")

    print("✅ Migration completed successfully!")
    return True

if __name__ == "__main__":
    try:
        success = run_migration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
