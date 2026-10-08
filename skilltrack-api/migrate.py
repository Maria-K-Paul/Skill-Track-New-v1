import sqlite3
import sys

def run():
    print("Running migration...")
    conn = sqlite3.connect("skilltrack.db")
    c = conn.cursor()

    # Check duplicates for Slots
    c.execute('SELECT domain_id, starts_at, venue, COUNT(*) FROM slots GROUP BY domain_id, starts_at, venue HAVING COUNT(*) > 1')
    dups = c.fetchall()
    if dups:
        print("Duplicate slots found:", dups)
        print("Please resolve duplicates manually before migrating.")
        sys.exit(1)

    try:
        # Slot unique index (original migration)
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_slots_domain_time_venue ON slots (domain_id, starts_at, venue);")

        # certificates.domain_id (original migration)
        try:
            c.execute("ALTER TABLE certificates ADD COLUMN domain_id INTEGER REFERENCES domains(id);")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_certificates_user_domain ON certificates (user_id, domain_id);")

        # exam_keys.slot_id (previous migration)
        try:
            c.execute("ALTER TABLE exam_keys ADD COLUMN slot_id INTEGER REFERENCES slots(id);")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise

        # ── Badge + certificate enrichment migration ──────────────────────────

        # badges table
        c.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL REFERENCES users(id),
                domain_id INTEGER NOT NULL REFERENCES domains(id),
                level_id  INTEGER NOT NULL REFERENCES levels(id),
                awarded_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_badges_user_level ON badges (user_id, level_id)")

        # new columns on certificates
        new_cert_cols = [
            ("student_name",       "TEXT"),
            ("domain_name",        "TEXT"),
            ("verification_token", "TEXT"),
            ("status",             "TEXT DEFAULT 'valid'"),
        ]
        for col, defn in new_cert_cols:
            try:
                c.execute(f"ALTER TABLE certificates ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise

        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_certs_verif_token "
            "ON certificates (verification_token) WHERE verification_token IS NOT NULL"
        )

        # ── Domains: description + difficulty ────────────────────────────────
        for col, defn in [("description", "TEXT"), ("difficulty", "TEXT")]:
            try:
                c.execute(f"ALTER TABLE domains ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise

        # ── Enrollments: enrolled_at, completed_at, is_common_enrollment ──────
        for col, defn in [
            ("enrolled_at",          "TEXT"),
            ("completed_at",         "TEXT"),
            ("is_common_enrollment", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            try:
                c.execute(f"ALTER TABLE enrollments ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise

        # Backfill is_common_enrollment from the domains table
        c.execute("""
            UPDATE enrollments
            SET is_common_enrollment = 1
            WHERE domain_id IN (SELECT id FROM domains WHERE is_common = 1)
        """)

        # The partial unique index covers only non-common (domain) enrollments.
        # SQLite WHERE clauses in partial indexes cannot reference other tables,
        # so we use the denormalized is_common_enrollment flag.
        c.execute("""
            SELECT user_id, COUNT(*) as cnt
            FROM enrollments
            WHERE status = 'active' AND is_common_enrollment = 0
            GROUP BY user_id
            HAVING cnt > 1
        """)
        violations = c.fetchall()
        if violations:
            print("WARNING: Multiple active domain enrollments found for user_ids:", [v[0] for v in violations])
            print("Partial unique index NOT created. Resolve manually and re-run.")
        else:
            c.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_one_active_domain_enrollment
                ON enrollments(user_id)
                WHERE status = 'active' AND is_common_enrollment = 0
            """)
            print("Partial unique index uq_one_active_domain_enrollment created.")

        # ── SlotBookings: status, booked_at, change_cancel_deadline, ack ─────
        for col, defn in [
            ("status",                         "TEXT NOT NULL DEFAULT 'booked'"),
            ("booked_at",                      "TEXT"),
            ("change_cancel_deadline",         "TEXT"),
            ("acknowledgement_acknowledged_at","TEXT"),
        ]:
            try:
                c.execute(f"ALTER TABLE slot_bookings ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise

        # ── Question Generation Syllabus & Bloom fields ──────────────────────
        for col, defn in [
            ("bloom_level_ratio", "JSON"),
            ("question_generation_status", "TEXT NOT NULL DEFAULT 'idle'"),
        ]:
            try:
                c.execute(f"ALTER TABLE levels ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise

        c.execute("""
            CREATE TABLE IF NOT EXISTS syllabus_topics (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                level_id  INTEGER NOT NULL REFERENCES levels(id),
                name      TEXT NOT NULL,
                weightage INTEGER NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS syllabus_subtopics (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id  INTEGER NOT NULL REFERENCES syllabus_topics(id),
                name      TEXT NOT NULL,
                weightage INTEGER NOT NULL
            )
        """)

        conn.commit()
        print("Migration successful.")
    except Exception as e:
        print("Error during migration:", e)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    run()
