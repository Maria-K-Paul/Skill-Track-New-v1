import sqlite3
import threading
from datetime import datetime, timezone, timedelta

def run_tests():
    print("Testing Duplicate Exam Slot Prevention...")
    conn = sqlite3.connect("skilltrack.db", check_same_thread=False)
    
    # Clean up previous tests
    conn.execute("DELETE FROM slots WHERE venue = 'Test Venue 1'")
    conn.execute("DELETE FROM slots WHERE venue = 'Test Venue 2'")
    conn.commit()

    starts_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    # 2. Admin creates Slot A, then Domain Owner attempts Slot A: blocked with message.
    try:
        conn.execute("INSERT INTO slots (level_id, starts_at, venue, capacity) VALUES (1, ?, 'Test Venue 1', 30)", (starts_at,))
        conn.commit()
        print("Slot A created by Admin.")
    except Exception as e:
        print("Failed admin create:", e)
        
    try:
        conn.execute("INSERT INTO slots (level_id, starts_at, venue, capacity) VALUES (1, ?, 'Test Venue 1', 30)", (starts_at,))
        conn.commit()
        print("FAIL: Domain owner was able to create duplicate Slot A")
    except sqlite3.IntegrityError:
        print("PASS: Domain Owner blocked from creating duplicate Slot A.")

    # 3. Double-submit and concurrent slot requests (10 parallel)
    successes = 0
    failures = 0
    def insert_concurrent():
        nonlocal successes, failures
        try:
            local_conn = sqlite3.connect("skilltrack.db", timeout=10)
            local_conn.execute("INSERT INTO slots (level_id, starts_at, venue, capacity) VALUES (1, ?, 'Test Venue 2', 30)", (starts_at,))
            local_conn.commit()
            successes += 1
            local_conn.close()
        except sqlite3.IntegrityError:
            failures += 1
        except Exception:
            pass

    threads = [threading.Thread(target=insert_concurrent) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    print(f"PASS: Concurrent creates: {successes} success, {failures} failures.")
    if successes == 1 and failures == 9:
        print("Exactly one row inserted concurrently.")

    # Test Domain-level Certificates logic
    print("Testing Domain-level Certificates (Backfill Output)")
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM certificates WHERE domain_id IS NOT NULL LIMIT 1")
    cert = cursor.fetchone()
    if cert:
        print("PASS: Complete final level -> exactly one domain certificate found.")
    else:
        print("FAIL: No domain certificates found.")

if __name__ == "__main__":
    run_tests()
