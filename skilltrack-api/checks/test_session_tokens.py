"""Session checks: access tokens tied to server-side sessions, the httpOnly refresh cookie, rotation with reuse
detection (token theft), sign-out, sign-out everywhere, one session per student, idle timeout and deactivation.

    DATABASE_URL=<test db> python checks/set_demo_passwords.py
    DATABASE_URL=<test db> python checks/test_session_tokens.py
"""
import os
import time
import uuid
import warnings
from datetime import datetime, timedelta, timezone

from _guard import require_test_database

require_test_database()
warnings.filterwarnings("ignore")
os.environ["REFRESH_COOKIE_PATH"] = "/auth"  # the test client calls the API directly, without the /api proxy prefix

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

import seed  # noqa: E402
from app import security  # noqa: E402
from app.config import REFRESH_COOKIE_NAME  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ActivityLog, AuthSession, RefreshToken, User  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  -> ' + str(detail)) if detail else ''}")


def browser():
    return TestClient(app, base_url="https://testserver")  # https, so the Secure cookie is sent back


def sign_in(client, email):
    r = client.post("/auth/login", json={"email": email, "password": seed.PASSWORD})
    return r, r.json().get("access_token")


def me(client, token):
    return client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def claims(token):
    return jwt.decode(token, options={"verify_signature": False})


def refresh_with(raw_refresh_token):
    """A request carrying a copied refresh cookie (another tab, or a thief who stole it)."""
    return browser().post("/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE_NAME}={raw_refresh_token}"})


def db_session(token):
    with SessionLocal() as db:
        return db.get(AuthSession, claims(token)["sid"])


# 1. Sign-in: access token in the body, refresh token only in an httpOnly cookie
alice = browser()
r, access = sign_in(alice, "admin@college.edu")
cookie_header = r.headers.get("set-cookie", "")
check("sign-in works", r.status_code == 200 and access, r.status_code)
check("no refresh token in the response body", "refresh_token" not in r.json())
check("refresh cookie is HttpOnly, Secure, SameSite=Strict",
      all(flag in cookie_header.lower() for flag in ("httponly", "secure", "samesite=strict")), cookie_header[:120])
check("access token names its session and lasts 15 min",
      "sid" in claims(access) and round((claims(access)["exp"] - time.time()) / 60) == security.ACCESS_TOKEN_MINUTES)
check("access token works", me(alice, access).status_code == 200)

# 2. Rotation: every refresh issues a new refresh token
first_refresh = alice.cookies.get(REFRESH_COOKIE_NAME)
r = alice.post("/auth/refresh")
access = r.json().get("access_token")
check("refresh gives a new access token", r.status_code == 200 and me(alice, access).status_code == 200)
check("refresh cookie was replaced", alice.cookies.get(REFRESH_COOKIE_NAME) not in (None, first_refresh))

# 3. Two tabs refreshing at the same moment: the replaced token right after use is refused but the session lives
check("just-replaced token within the grace window -> 409, no logout", refresh_with(first_refresh).status_code == 409)
check("...and the session is still open", me(alice, access).status_code == 200)

# 4. Theft: the old refresh token used again later -> the whole session ends, including the victim's access token
with SessionLocal() as db:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == security.hash_refresh_token(first_refresh)))
    row.used_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()
check("stolen old refresh token refused", refresh_with(first_refresh).status_code == 401)
check("victim's access token stops working at once", me(alice, access).status_code == 401)
check("victim's current refresh cookie is refused too", alice.post("/auth/refresh").status_code == 401)
check("session marked as reused", (db_session(access).revoke_reason == "refresh token reused"))
with SessionLocal() as db:
    logged = db.scalar(select(ActivityLog).where(ActivityLog.action.like("%used again%")).order_by(ActivityLog.id.desc()))
check("theft logged for the admin", logged is not None)

# 5. Sign-out ends the session on the server
bob = browser()
_, access = sign_in(bob, "admin@college.edu")
check("sign-out -> 204", bob.post("/auth/logout").status_code == 204)
check("access token refused after sign-out", me(bob, access).status_code == 401)
check("refresh refused after sign-out", bob.post("/auth/refresh").status_code == 401)

# 6. Sign out everywhere (staff may have several sessions)
laptop, phone = browser(), browser()
_, laptop_access = sign_in(laptop, "admin@college.edu")
_, phone_access = sign_in(phone, "admin@college.edu")
check("staff keep two sessions", me(laptop, laptop_access).status_code == 200 and me(phone, phone_access).status_code == 200)
r = laptop.post("/auth/logout-all", headers={"Authorization": f"Bearer {laptop_access}"})
check("sign out everywhere -> 204", r.status_code == 204)
check("both devices signed out", me(laptop, laptop_access).status_code == 401 and me(phone, phone_access).status_code == 401)

# 7. One session per student: signing in on a second computer ends the first
pc1, pc2 = browser(), browser()
_, pc1_access = sign_in(pc1, "arun@college.edu")
_, pc2_access = sign_in(pc2, "arun@college.edu")
check("student's first session ended by the second sign-in", me(pc1, pc1_access).status_code == 401)
check("student's second session works", me(pc2, pc2_access).status_code == 200)

# 8. Idle timeout: a session not refreshed for over an hour ends
with SessionLocal() as db:
    s = db.get(AuthSession, claims(pc2_access)["sid"])
    s.last_used_at = datetime.now(timezone.utc) - timedelta(minutes=61)
    db.commit()
check("idle session refused at refresh", pc2.post("/auth/refresh").status_code == 401)

# 9. Fixed 1-day limit: an expired session refuses its access token too
lab = browser()
_, lab_access = sign_in(lab, "arun@college.edu")
with SessionLocal() as db:
    db.get(AuthSession, claims(lab_access)["sid"]).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
check("expired session refuses its access token", me(lab, lab_access).status_code == 401)

# 10. Deactivation signs the student out everywhere
_, admin_access = sign_in(browser(), "admin@college.edu")
student = browser()
_, student_access = sign_in(student, "arun@college.edu")
with SessionLocal() as db:
    arun_id = db.scalar(select(User.id).where(User.email == "arun@college.edu"))
patch = lambda active: browser().patch(f"/admin/users/{arun_id}", json={"is_active": active},  # noqa: E731
                                       headers={"Authorization": f"Bearer {admin_access}"})
check("admin deactivates the student", patch(False).status_code == 200)
check("deactivated student's token refused", me(student, student_access).status_code == 401)
check("deactivated student's refresh refused", student.post("/auth/refresh").status_code == 401)
check("student reactivated (cleanup)", patch(True).status_code == 200)

# 11. Tokens from before this change, and forged ones, are refused
old_style = jwt.encode({"sub": "1", "role": "admin", "type": "access", "exp": int(time.time()) + 600},
                       security.SECRET_KEY, algorithm="HS256")
check("token without a session id refused", me(browser(), old_style).status_code == 401)
forged = jwt.encode({"sub": "1", "role": "admin", "sid": "x" * 32, "type": "access", "exp": int(time.time()) + 600},
                    security.SECRET_KEY, algorithm="HS256")
check("token naming a session that does not exist refused", me(browser(), forged).status_code == 401)
check("refresh with no cookie refused", browser().post("/auth/refresh").status_code == 401)

# 12. Registration signs in with a cookie; failed sign-ins are logged
newbie = browser()
email = f"session.check.{uuid.uuid4().hex[:8]}@example.com"
r = newbie.post("/auth/register", json={"name": "Session Check", "email": email, "reg_no": uuid.uuid4().hex[:12],
                                         "password": "a-test-password", "department": "CSE"})
check("register signs in with the cookie", r.status_code == 201 and newbie.cookies.get(REFRESH_COOKIE_NAME))
browser().post("/auth/login", json={"email": "admin@college.edu", "password": "wrong-password"})
with SessionLocal() as db:
    failed = db.scalar(select(ActivityLog).where(ActivityLog.action == "Failed sign-in for admin@college.edu"))
check("failed sign-in logged", failed is not None)

print(f"\n{sum(results)}/{len(results)} checks passed")
raise SystemExit(0 if all(results) else 1)
