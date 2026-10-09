import os
from pathlib import Path


def _load_env() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env()

# The app only runs on the Neon PostgreSQL database; there is no fallback to a local SQLite file
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
# Neon (like Render) hands out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg driver named
for _prefix in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(_prefix):
        DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(_prefix):]
if not DATABASE_URL.startswith("postgresql+psycopg://"):
    raise RuntimeError(
        "DATABASE_URL must be the Neon PostgreSQL connection string. "
        "Set it in skilltrack-api/.env locally, or in the service's environment on Render."
    )
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
# Anyone who knows the key can sign tokens for any user, so refuse to start with a missing, short or sample key
if len(SECRET_KEY) < 32 or SECRET_KEY.startswith("change-me"):
    raise RuntimeError(
        "SECRET_KEY must be a random string of at least 32 characters. "
        "Set it in skilltrack-api/.env locally (python -c \"import secrets; print(secrets.token_hex(32))\"); "
        "Render generates one."
    )
ACCESS_TOKEN_MINUTES = int(os.environ.get("ACCESS_TOKEN_MINUTES", "15"))
# A sign-in lasts at most this long (the refresh token is rotated on every use but never extends it)
REFRESH_TOKEN_MINUTES = int(os.environ.get("REFRESH_TOKEN_MINUTES", "1440"))
# A session that has not refreshed for this long ends (e.g. a lab computer left signed in). The exam page
# talks to the API every 30 seconds, so an exam in progress never goes idle.
SESSION_IDLE_MINUTES = int(os.environ.get("SESSION_IDLE_MINUTES", "60"))
# Two tabs can refresh at the same moment with the same cookie; a just-replaced refresh token used within this
# window is refused without ending the session. Later use means it was copied, so the session is ended.
REFRESH_REUSE_GRACE_SECONDS = int(os.environ.get("REFRESH_REUSE_GRACE_SECONDS", "20"))
# Students may have one signed-in session at a time: signing in again ends the others (stops sharing a sign-in)
ONE_SESSION_PER_STUDENT = os.environ.get("ONE_SESSION_PER_STUDENT", "true").lower() == "true"
# The refresh token lives in an httpOnly cookie that page scripts cannot read. The website reaches the API
# through its own address (/api/* is rewritten to the API), so the cookie path is /api/auth.
REFRESH_COOKIE_NAME = "skilltrack_refresh"
REFRESH_COOKIE_PATH = os.environ.get("REFRESH_COOKIE_PATH", "/api/auth")
ALGORITHM = "HS256"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
# Defaults are free-tier models; when Google retires one, pick a current one from ai.google.dev/gemini-api/docs/models
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.8-flash"
# Tried in order when the main model is overloaded (503) or rate-limited (429). Comma-separated; empty disables.
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite,gemini-3.7-flash").split(",") if m.strip()
]
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
# Public base URL used in QR codes (can differ from FRONTEND_URL behind a reverse proxy)
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", FRONTEND_URL).rstrip("/")
# How many minutes after booking a student may change or cancel their slot
BOOKING_WINDOW_MINUTES = int(os.environ.get("BOOKING_WINDOW_MINUTES", "30"))
