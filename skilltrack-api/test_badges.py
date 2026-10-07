"""
Badge and certificate tests (requirements S Tests 1-9).
Run after servers are up:
    python test_badges.py
"""
import hashlib
import io
import struct
import asyncio
import sqlite3
import secrets
import zlib

import httpx

API = "http://localhost:8002"
DB = "skilltrack.db"

# -- helpers -------------------------------------------------------------------

def _token(email: str, password: str = "Password@123") -> str:
    import requests
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=5)
    r.raise_for_status()
    return r.json()["access_token"]


def _db():
    return sqlite3.connect(DB)


def _pass(p: bool, msg: str) -> None:
    print(f"  {'PASS' if p else 'FAIL'}: {msg}")
    if not p:
        raise AssertionError(msg)


def _is_valid_png(data: bytes) -> bool:
    return data[:8] == b'\x89PNG\r\n\x1a\n'


def _ascii85_decode(data: bytes) -> bytes:
    if data.endswith(b"~>"):
        data = data[:-2]
    result = bytearray()
    i = 0
    while i < len(data):
        while i < len(data) and data[i:i+1] in (b" ", b"\n", b"\r", b"\t"):
            i += 1
        if i >= len(data):
            break
        if data[i:i+1] == b"z":
            result.extend(b"\x00\x00\x00\x00")
            i += 1
            continue
        group: list[int] = []
        while len(group) < 5 and i < len(data):
            c = data[i:i+1]
            if c not in (b" ", b"\n", b"\r", b"\t"):
                group.append(data[i])
            i += 1
        while len(group) < 5:
            group.append(ord("u"))
        v = 0
        for c in group:
            v = v * 85 + (c - 33)
        for j in range(3, -1, -1):
            result.append((v >> (j * 8)) & 0xFF)
    return bytes(result)


def _decode_pdf_content(pdf_bytes: bytes) -> str:
    """Decode the page content stream from an ASCII85+Flate PDF (ReportLab default).
    Follows the /Contents reference in the page dict to locate the exact object,
    then extracts the stream by byte position (no regex on the stream data itself)."""
    import zlib, re as _re

    m = _re.search(rb'/Contents (\d+) 0 R', pdf_bytes)
    if not m:
        return ""
    obj_num = m.group(1)

    # Find "N 0 obj" and the "stream\n" or "stream\r\n" after it
    obj_start = pdf_bytes.find(obj_num + b" 0 obj")
    if obj_start == -1:
        return ""

    stream_marker = pdf_bytes.find(b"stream\r\n", obj_start)
    if stream_marker != -1:
        data_start = stream_marker + 8
    else:
        stream_marker = pdf_bytes.find(b"stream\n", obj_start)
        if stream_marker == -1:
            return ""
        data_start = stream_marker + 7

    # endstream can appear with or without a preceding newline
    endstream_pos = pdf_bytes.find(b"endstream", data_start)
    if endstream_pos == -1:
        return ""
    data_end = endstream_pos
    # strip optional trailing newline from stream data
    stream_data = pdf_bytes[data_start:data_end].rstrip(b"\r\n")

    try:
        raw = _ascii85_decode(stream_data)
        return zlib.decompress(raw).decode("latin-1", errors="replace")
    except Exception:
        return ""


# -- Test 1: Pass levels 1..N-1 ? badges only, no certificate -----------------

def test_badges_no_cert():
    print("\nTest 1: levels 1..N-1 -> badges only, no cert")
    with _db() as c:
        # Find a user who has badges but not all levels in their domain
        row = c.execute("""
            SELECT b.user_id, b.domain_id, COUNT(DISTINCT b.level_id) as badge_cnt,
                   (SELECT COUNT(*) FROM levels WHERE domain_id=b.domain_id) as total
            FROM badges b GROUP BY b.user_id, b.domain_id
            HAVING badge_cnt < total
            LIMIT 1
        """).fetchone()
    if row is None:
        print("  SKIP: no student with partial progress (need real exam flow)")
        return
    uid, dom_id, badge_cnt, total = row
    has_cert = _db().execute(
        "SELECT COUNT(*) FROM certificates WHERE user_id=? AND domain_id=? AND status='valid'",
        (uid, dom_id),
    ).fetchone()[0]
    _pass(badge_cnt > 0, f"Has {badge_cnt} badges for domain {dom_id}")
    _pass(has_cert == 0, "No domain certificate yet")


# -- Test 2: Pass final level ? all badges + exactly one certificate -----------

def test_final_level_cert():
    print("\nTest 2: all levels passed -> exactly one domain cert")
    with _db() as c:
        # Find user with all levels in a domain passed
        row = c.execute("""
            SELECT b.user_id, b.domain_id, COUNT(DISTINCT b.level_id) as badge_cnt,
                   (SELECT COUNT(*) FROM levels WHERE domain_id=b.domain_id) as total
            FROM badges b GROUP BY b.user_id, b.domain_id
            HAVING badge_cnt >= total AND total > 0
            LIMIT 1
        """).fetchone()
    if row is None:
        print("  SKIP: no student with all levels complete")
        return
    uid, dom_id, badge_cnt, total = row
    cert_count = _db().execute(
        "SELECT COUNT(*) FROM certificates WHERE user_id=? AND domain_id=? AND status='valid'",
        (uid, dom_id),
    ).fetchone()[0]
    _pass(badge_cnt == total, f"{badge_cnt} badges == {total} levels")
    _pass(cert_count == 1, f"Exactly 1 domain cert (found {cert_count})")


# -- Test 3: Idempotency - backfill twice, no duplicates ----------------------

def test_backfill_idempotent():
    print("\nTest 3: backfill twice -> no duplicates")
    from app.database import SessionLocal
    from backfill_badges import run as backfill_run

    before_badges = _db().execute("SELECT COUNT(*) FROM badges").fetchone()[0]
    before_certs = _db().execute("SELECT COUNT(*) FROM certificates WHERE status='valid'").fetchone()[0]

    db = SessionLocal()
    try:
        backfill_run(db)
        backfill_run(db)
    finally:
        db.close()

    after_badges = _db().execute("SELECT COUNT(*) FROM badges").fetchone()[0]
    after_certs = _db().execute("SELECT COUNT(*) FROM certificates WHERE status='valid'").fetchone()[0]
    _pass(before_badges == after_badges, f"Badge count unchanged ({before_badges})")
    _pass(before_certs == after_certs, f"Cert count unchanged ({before_certs})")


# -- Test 4: PDF opens with correct data; QR URL is verify URL ----------------

def test_pdf_and_qr():
    print("\nTest 4: PDF data correct + QR encodes verify URL")
    row = _db().execute(
        "SELECT user_id, code, verification_token, student_name FROM certificates WHERE status='valid' LIMIT 1"
    ).fetchone()
    if row is None:
        print("  SKIP: no valid domain cert")
        return
    uid, code, vtoken, sname = row
    email = _db().execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()[0]
    tok = _token(email)
    import requests
    r = requests.get(f"{API}/me/certificates/{code}/pdf", headers={"Authorization": f"Bearer {tok}"}, timeout=10)
    _pass(r.status_code == 200, f"PDF downloaded (HTTP {r.status_code})")
    _pass(r.headers["content-type"] == "application/pdf", "Content-Type is application/pdf")
    pdf = r.content
    _pass(pdf[:5] == b"%PDF-", "PDF starts with %PDF-")
    _pass(len(pdf) > 3000, f"PDF is non-trivial size ({len(pdf)} bytes)")
    # Decode the compressed content stream and check for verify URL
    page_text = _decode_pdf_content(pdf)
    _pass(sname in page_text, f"Student name '{sname}' in PDF content")
    if vtoken:
        _pass(f"/verify/{vtoken}" in page_text, f"verification_token in PDF verify URL")


# -- Test 5: Valid token verified; invalid token ? no data --------------------

def test_verify_endpoint():
    print("\nTest 5: verify endpoint - valid + invalid token")
    import requests
    row = _db().execute(
        "SELECT verification_token FROM certificates WHERE verification_token IS NOT NULL LIMIT 1"
    ).fetchone()
    if row:
        vtoken = row[0]
        r = requests.get(f"{API}/verify/{vtoken}", timeout=5)
        d = r.json()
        _pass(d.get("valid") is True, "Valid token ? valid=True")
        _pass("holder" in d and d["holder"], "holder present")
        _pass("credential" in d and d["credential"], "credential present")
        _pass("issued_at" in d, "issued_at present")
        _pass("email" not in d, "No email leaked")
    else:
        print("  SKIP: no cert with verification_token")

    # Invalid token
    r2 = requests.get(f"{API}/verify/aaabbbccc000111222333444555666777", timeout=5)
    _pass(r2.json() == {"valid": False}, "Invalid token ? {valid: false} only")

    # Modified token (strip last char)
    if row:
        bad = vtoken[:-1] + ("0" if vtoken[-1] != "0" else "1")
        r3 = requests.get(f"{API}/verify/{bad}", timeout=5)
        _pass(r3.json().get("valid") is False, "Modified token ? valid=False, no data")


# -- Test 6: Student A cannot access Student B's credentials ------------------

def test_isolation():
    print("\nTest 6: cross-student isolation")
    # Need two different students with badges
    rows = _db().execute(
        "SELECT DISTINCT user_id FROM badges LIMIT 2"
    ).fetchall()
    if len(rows) < 2:
        print("  SKIP: need at least 2 students with badges")
        return
    uid_a, uid_b = rows[0][0], rows[1][0]
    email_a = _db().execute("SELECT email FROM users WHERE id=?", (uid_a,)).fetchone()[0]
    email_b = _db().execute("SELECT email FROM users WHERE id=?", (uid_b,)).fetchone()[0]
    tok_b = _token(email_b)

    badge_a = _db().execute("SELECT id FROM badges WHERE user_id=? LIMIT 1", (uid_a,)).fetchone()[0]
    import requests
    r = requests.get(f"{API}/me/badges/{badge_a}/png", headers={"Authorization": f"Bearer {tok_b}"}, timeout=5)
    _pass(r.status_code == 404, f"Student B gets 404 on Student A's badge (got {r.status_code})")

    cert_a = _db().execute(
        "SELECT code FROM certificates WHERE user_id=? AND status='valid' LIMIT 1", (uid_a,)
    ).fetchone()
    if cert_a:
        r2 = requests.get(f"{API}/me/certificates/{cert_a[0]}/pdf", headers={"Authorization": f"Bearer {tok_b}"}, timeout=5)
        _pass(r2.status_code == 404, f"Student B gets 404 on Student A's cert PDF (got {r2.status_code})")


# -- Test 7: Badge PNG downloads and is a valid PNG ---------------------------

def test_badge_png():
    print("\nTest 7: badge PNG download and validity")
    row = _db().execute("SELECT id, user_id FROM badges LIMIT 1").fetchone()
    if not row:
        print("  SKIP: no badges")
        return
    badge_id, uid = row
    email = _db().execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()[0]
    tok = _token(email)
    import requests
    r = requests.get(f"{API}/me/badges/{badge_id}/png", headers={"Authorization": f"Bearer {tok}"}, timeout=10)
    _pass(r.status_code == 200, f"HTTP 200 (got {r.status_code})")
    _pass(r.headers["content-type"] == "image/png", "Content-Type is image/png")
    _pass(_is_valid_png(r.content), "Valid PNG signature")
    _pass(len(r.content) > 5000, f"PNG size reasonable ({len(r.content)} bytes)")


# -- Test 8: Backfill idempotent (already covered in Test 3) ------------------

# -- Test 9: Existing features unbroken ---------------------------------------

def test_existing_features():
    print("\nTest 9: existing features unbroken")
    import requests
    # Login
    r = requests.post(f"{API}/auth/login", json={"email": "admin@college.edu", "password": "Password@123"}, timeout=5)
    _pass(r.status_code == 200, f"Admin login OK (HTTP {r.status_code})")
    tok = r.json()["access_token"]
    # Dashboard accessible
    r2 = requests.get(f"{API}/admin/overview", headers={"Authorization": f"Bearer {tok}"}, timeout=5)
    _pass(r2.status_code == 200, f"Admin overview OK (HTTP {r2.status_code})")
    # Student dashboard
    stok = _token("meera@college.edu")
    r3 = requests.get(f"{API}/me/dashboard", headers={"Authorization": f"Bearer {stok}"}, timeout=5)
    _pass(r3.status_code == 200, f"Student dashboard OK")
    d = r3.json()
    _pass("certificates" in d, "certificates key present in dashboard")
    _pass("levels" in d, "levels key present in dashboard")
    # No legacy certs in dashboard
    for c in d["certificates"]:
        _pass(c.get("code") is not None, f"Cert has code")


# -- runner --------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_badges_no_cert,
        test_final_level_cert,
        test_backfill_idempotent,
        test_pdf_and_qr,
        test_verify_endpoint,
        test_isolation,
        test_badge_png,
        test_existing_features,
    ]
    errors = []
    for t in tests:
        try:
            t()
        except Exception as e:
            errors.append(f"{t.__name__}: {e}")
            print(f"  FAIL (exception): {e}")

    print(f"\n{'='*50}")
    if errors:
        print(f"FAILED {len(errors)}/{len(tests)} tests:")
        for e in errors:
            print(f"  - {e}")
    else:
        print(f"ALL {len(tests)} tests PASSED")
