"""
Tests for Parts A-D of the new feature set.
Run: python -I test_new_features.py
Requires the server to be running on port 8002.
"""
import concurrent.futures
import random
import time
import requests

BASE = "http://localhost:8002"

ADMIN_TOKEN = None


def login(email, password="Password@123"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def get_admin_token():
    global ADMIN_TOKEN
    if ADMIN_TOKEN is None:
        ADMIN_TOKEN = login("admin@college.edu")
    return ADMIN_TOKEN


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def ok(label):
    print(f"  PASS  {label}")


def fail(label, reason):
    print(f"  FAIL  {label}: {reason}")


def make_student_sem3():
    """Register a fresh student and promote them to semester 3."""
    email = f"test_{random.randint(100000, 999999)}@test.com"
    r = requests.post(f"{BASE}/auth/register", json={
        "name": "Test Student", "email": email, "reg_no": f"T{random.randint(100000,999999)}",
        "password": "Password@123", "department": "CSE",
    })
    r.raise_for_status()
    user_id = r.json()["user"]["id"]
    token = r.json()["access_token"]

    # Promote to semester 3 via admin
    admin_tok = get_admin_token()
    # Promote twice (1->2, 2->3)
    for _ in range(2):
        r2 = requests.post(f"{BASE}/admin/promote", json={"student_ids": [user_id]}, headers=headers(admin_tok))
        assert r2.status_code == 200, r2.text

    return token, user_id


# ── Test 3: Domains API returns list ─────────────────────────────────────────

def test_domains_list():
    print("\n[T3] Part A -- Domain list API")
    token = login("arun@college.edu")
    r = requests.get(f"{BASE}/domains", headers=headers(token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "domains" in data
    assert "active_enrollment" in data
    assert "can_enroll" in data
    ok(f"Domain list returned {len(data['domains'])} domains, active={data['active_enrollment']}")

    # Test search
    r2 = requests.get(f"{BASE}/domains?search=full", headers=headers(token))
    assert r2.status_code == 200
    filtered = r2.json()["domains"]
    ok(f"Search 'full' returned {len(filtered)} domain(s)")


# ── Test 4: Domain detail API ─────────────────────────────────────────────────

def test_domain_detail():
    print("\n[T4] Part A -- Domain detail API")
    token = login("arun@college.edu")
    r = requests.get(f"{BASE}/domains", headers=headers(token))
    domain_id = r.json()["domains"][0]["id"]

    r = requests.get(f"{BASE}/domains/{domain_id}", headers=headers(token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "levels" in data and len(data["levels"]) > 0
    assert "topic_count" in data
    ok(f"Domain detail: {data['name']}, {len(data['levels'])} levels, {data['topic_count']} topics")
    # Each level has status field
    for lv in data["levels"]:
        assert "status" in lv, "Level missing status"
    ok("All levels have status field")


# ── Test 1: Single active enrollment ─────────────────────────────────────────

def test_single_active_enrollment():
    print("\n[T1] Part B -- Single active enrollment enforcement")
    token, _ = make_student_sem3()

    r = requests.get(f"{BASE}/domains", headers=headers(token))
    domains = r.json()["domains"]
    assert len(domains) >= 2, "Need at least 2 domains"
    d1, d2 = domains[0]["id"], domains[1]["id"]
    d1_name = domains[0]["name"]

    # Enroll in domain 1
    r = requests.post(f"{BASE}/enrollments", json={"domain_id": d1}, headers=headers(token))
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    ok(f"Enrolled in {d1_name}")

    # Try to enroll in domain 2 -- should get 409 with the right message
    r = requests.post(f"{BASE}/enrollments", json={"domain_id": d2}, headers=headers(token))
    if r.status_code == 409 and "already enrolled in another domain" in r.json().get("detail", ""):
        ok("Second enroll blocked with correct 409 message")
    else:
        fail("Second enroll should be 409", f"got {r.status_code}: {r.text}")


# ── Test 2: Parallel enroll requests ─────────────────────────────────────────

def test_parallel_enrollments():
    print("\n[T2] Part B -- 10 parallel enroll requests, exactly 1 ACTIVE")
    token, _ = make_student_sem3()

    r = requests.get(f"{BASE}/domains", headers=headers(token))
    domains = r.json()["domains"]
    d1 = domains[0]["id"]
    d2 = domains[1]["id"] if len(domains) > 1 else d1

    results = []

    def do_enroll(domain_id):
        r = requests.post(f"{BASE}/enrollments", json={"domain_id": domain_id}, headers=headers(token))
        return r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(do_enroll, d1 if i < 5 else d2) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    successes = results.count(201)
    if successes == 1:
        ok(f"Exactly 1 of 10 parallel enrollments succeeded (results: {sorted(results)})")
    else:
        fail(f"Expected 1 success, got {successes}", str(results))


# ── Test 5: Booking requires acknowledgement ──────────────────────────────────

def test_booking_acknowledgement():
    print("\n[T5] Part D -- Booking acknowledgement required")
    token = login("arun@college.edu")

    r = requests.get(f"{BASE}/me/dashboard", headers=headers(token))
    data = r.json()
    if not data["slots"]:
        print("  SKIP  No slots available for test (need upcoming slot)")
        return

    slot_id = data["slots"][0]["id"]

    # Without acknowledgement field -> 422
    r = requests.post(f"{BASE}/slots/{slot_id}/book", json={"acknowledgement": False}, headers=headers(token))
    if r.status_code == 422:
        ok("acknowledgement=False returns 422")
    else:
        fail("Expected 422", f"got {r.status_code}: {r.text}")

    # Empty body -> 422
    r = requests.post(f"{BASE}/slots/{slot_id}/book", json={}, headers=headers(token))
    if r.status_code == 422:
        ok("Empty body returns 422")
    else:
        fail("Expected 422 for empty body", f"got {r.status_code}: {r.text}")


# ── Test 6: Booking success + deadline ────────────────────────────────────────

def test_booking_success_and_cancel():
    print("\n[T6/T7] Part D -- Booking success + deadline + cancel within window")
    token, _ = make_student_sem3()

    r = requests.get(f"{BASE}/domains", headers=headers(token))
    d1 = r.json()["domains"][0]["id"]
    requests.post(f"{BASE}/enrollments", json={"domain_id": d1}, headers=headers(token))

    r = requests.get(f"{BASE}/me/dashboard", headers=headers(token))
    slots = r.json()["slots"]
    if not slots:
        print("  SKIP  No slots available")
        return

    slot = slots[0]

    # Book with acknowledgement
    r = requests.post(f"{BASE}/slots/{slot['id']}/book", json={"acknowledgement": True}, headers=headers(token))
    if r.status_code != 200:
        fail("Booking", f"got {r.status_code}: {r.text}")
        return

    booking = r.json()
    ok(f"Booking created id={booking['booking_id']}, window_expired={booking['window_expired']}")

    # Verify deadline = booked_at + 30 min
    from datetime import datetime, timezone

    def _parse_dt(s):
        # Normalize both naive and aware ISO strings to naive UTC for comparison
        s = s.replace("Z", "+00:00") if s else s
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    booked_at = _parse_dt(booking["booked_at"])
    deadline = _parse_dt(booking["change_cancel_deadline"])
    diff_minutes = (deadline - booked_at).total_seconds() / 60
    if 29.5 <= diff_minutes <= 30.5:
        ok(f"Deadline = booked_at + {diff_minutes:.1f} min")
    else:
        fail("Deadline check", f"diff={diff_minutes:.1f} min, expected ~30")

    if 1700 <= booking["seconds_remaining_in_window"] <= 1800:
        ok(f"seconds_remaining_in_window={booking['seconds_remaining_in_window']}")
    else:
        fail("Window seconds", f"got {booking['seconds_remaining_in_window']}, expected ~1800")

    # Refresh dashboard -- active_booking should show
    r = requests.get(f"{BASE}/me/dashboard", headers=headers(token))
    dash = r.json()
    if dash["active_booking"] and dash["active_booking"]["booking_id"] == booking["booking_id"]:
        ok("Dashboard shows active_booking with correct booking_id")
    else:
        fail("Dashboard active_booking", str(dash.get("active_booking")))

    # T7: Cancel within window
    r = requests.delete(f"{BASE}/me/bookings/{booking['booking_id']}", headers=headers(token))
    if r.status_code == 204:
        ok("Cancelled within window -> 204")
    else:
        fail("Cancel within window", f"got {r.status_code}: {r.text}")

    # After cancel, slot should be free again (seat count restored)
    r = requests.get(f"{BASE}/me/dashboard", headers=headers(token))
    dash = r.json()
    if dash["active_booking"] is None:
        ok("After cancel, active_booking=None")
    else:
        fail("active_booking should be None after cancel", str(dash["active_booking"]))

    return booking, token


# ── Test 8: After window expired, change/cancel rejected ─────────────────────

def test_after_window_expired():
    print("\n[T8] Part D -- After window: change/cancel rejected by API")
    # Simulate by manually setting a past deadline in the DB
    import sqlite3
    from datetime import datetime, timezone, timedelta

    token, user_id = make_student_sem3()
    r = requests.get(f"{BASE}/domains", headers=headers(token))
    d1 = r.json()["domains"][0]["id"]
    requests.post(f"{BASE}/enrollments", json={"domain_id": d1}, headers=headers(token))

    r = requests.get(f"{BASE}/me/dashboard", headers=headers(token))
    slots = r.json()["slots"]
    if not slots:
        print("  SKIP  No slots")
        return

    r = requests.post(f"{BASE}/slots/{slots[0]['id']}/book", json={"acknowledgement": True}, headers=headers(token))
    if r.status_code != 200:
        print(f"  SKIP  Could not book: {r.text}")
        return

    booking_id = r.json()["booking_id"]

    # Back-date the deadline to 31 minutes ago via direct DB
    past_deadline = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
    conn = sqlite3.connect("C:/Project/Skill-Track/Skill-Track/skilltrack-api/skilltrack.db")
    conn.execute(
        "UPDATE slot_bookings SET change_cancel_deadline=? WHERE id=?",
        (past_deadline, booking_id),
    )
    conn.commit()
    conn.close()

    # Cancel -> 403
    r = requests.delete(f"{BASE}/me/bookings/{booking_id}", headers=headers(token))
    if r.status_code == 403 and "expired" in r.json().get("detail", "").lower():
        ok("Cancel after window returns 403 with 'expired' message")
    else:
        fail("Expected 403 after window", f"got {r.status_code}: {r.text}")


# ── Test 9: Double booking same domain+level blocked ─────────────────────────

def test_double_booking():
    print("\n[T9] Part D -- Double booking same domain+level blocked")
    token, _ = make_student_sem3()
    r = requests.get(f"{BASE}/domains", headers=headers(token))
    d1 = r.json()["domains"][0]["id"]
    requests.post(f"{BASE}/enrollments", json={"domain_id": d1}, headers=headers(token))

    r = requests.get(f"{BASE}/me/dashboard", headers=headers(token))
    slots = r.json()["slots"]
    if len(slots) < 2:
        print("  SKIP  Need 2+ slots")
        return

    requests.post(f"{BASE}/slots/{slots[0]['id']}/book", json={"acknowledgement": True}, headers=headers(token))

    r = requests.post(f"{BASE}/slots/{slots[1]['id']}/book", json={"acknowledgement": True}, headers=headers(token))
    if r.status_code == 409 and "already have a booked" in r.json().get("detail", ""):
        ok("Double booking blocked with 409")
    else:
        fail("Expected 409", f"got {r.status_code}: {r.text}")


# ── Test 10: Capacity race (2 parallel for last seat) ────────────────────────

def test_capacity_race():
    print("\n[T10] Part D -- Capacity race: 2 parallel requests for same slot")
    tokens = []
    for _ in range(2):
        tok, _ = make_student_sem3()
        r = requests.get(f"{BASE}/domains", headers=headers(tok))
        d1 = r.json()["domains"][0]["id"]
        requests.post(f"{BASE}/enrollments", json={"domain_id": d1}, headers=headers(tok))
        tokens.append(tok)

    r = requests.get(f"{BASE}/me/dashboard", headers=headers(tokens[0]))
    slots = r.json()["slots"]
    if not slots:
        print("  SKIP  No slots")
        return

    slot_id = slots[0]["id"]
    seats = slots[0]["seats_left"]

    def do_book(tok):
        r = requests.post(f"{BASE}/slots/{slot_id}/book", json={"acknowledgement": True}, headers=headers(tok))
        return r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        results = list(ex.map(do_book, tokens))

    successes = results.count(200)
    ok(f"Slot had {seats} seats. Results: {results}. Successes: {successes}")
    if successes <= seats:
        ok("Capacity respected -- never overbooked")
    else:
        fail("OVERBOOKED!", f"successes={successes} > seats={seats}")


# ── Test 11: Cross-student isolation ─────────────────────────────────────────

def test_cross_student_isolation():
    print("\n[T11] Auth -- Student cannot modify another student's booking")
    tokens_ids = [make_student_sem3(), make_student_sem3()]
    for tok, _ in tokens_ids:
        r = requests.get(f"{BASE}/domains", headers=headers(tok))
        d1 = r.json()["domains"][0]["id"]
        requests.post(f"{BASE}/enrollments", json={"domain_id": d1}, headers=headers(tok))

    # Student 0 books a slot
    tok0 = tokens_ids[0][0]
    tok1 = tokens_ids[1][0]
    r = requests.get(f"{BASE}/me/dashboard", headers=headers(tok0))
    slots = r.json()["slots"]
    if not slots:
        print("  SKIP  No slots")
        return

    r = requests.post(f"{BASE}/slots/{slots[0]['id']}/book", json={"acknowledgement": True}, headers=headers(tok0))
    if r.status_code != 200:
        print(f"  SKIP  Could not book: {r.text}")
        return

    booking_id = r.json()["booking_id"]

    # Student 1 tries to cancel student 0's booking -> 404
    r = requests.delete(f"{BASE}/me/bookings/{booking_id}", headers=headers(tok1))
    if r.status_code == 404:
        ok("Cross-student cancel: 404")
    else:
        fail("Expected 404", f"got {r.status_code}")


# ── Test 12: No-show job idempotency ─────────────────────────────────────────

def test_noshow_idempotency():
    print("\n[T12] Part D -- No-show job runs twice, penalty applied once")
    import sys, os
    sys.path.insert(0, "C:/Project/Skill-Track/Skill-Track/skilltrack-api")
    os.chdir("C:/Project/Skill-Track/Skill-Track/skilltrack-api")
    from app.noshow import run_noshow_job

    n1 = run_noshow_job()
    n2 = run_noshow_job()
    ok(f"First run: {n1} booking(s) processed, second run: {n2}")
    if n2 == 0:
        ok("Idempotent (ok)")
    else:
        fail("Idempotency", f"second run processed {n2}, expected 0")


# ── Run all ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("SkillTrack Feature Tests (Parts A-D)")
    print("=" * 60)

    test_domains_list()
    test_domain_detail()
    test_single_active_enrollment()
    test_parallel_enrollments()
    test_booking_acknowledgement()
    test_booking_success_and_cancel()
    test_after_window_expired()
    test_double_booking()
    test_capacity_race()
    test_cross_student_isolation()
    test_noshow_idempotency()

    print("\nDone.")
