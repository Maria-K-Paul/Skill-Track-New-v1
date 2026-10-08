import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value


BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG = {
    "LLM_PROVIDER": get_env("LLM_PROVIDER", "ollama"),
    "OLLAMA_MODEL": get_env("OLLAMA_MODEL", get_env("LLM_MODEL", "qwen3.5:9b")),
    "GEMINI_MODEL": get_env("GEMINI_MODEL", "gemini-3.5-flash"),
    "GEMINI_API_KEY": get_env("GEMINI_API_KEY", get_env("GEMINI_API")),
    "OLLAMA_BASE_URL": get_env("OLLAMA_BASE_URL", "http://localhost:11434"),
    "MAX_REGENERATION_ROUNDS": int(get_env("MAX_REGENERATION_ROUNDS", "3")),
    "DUPLICATE_SIMILARITY_THRESHOLD": float(get_env("DUPLICATE_SIMILARITY_THRESHOLD", "0.85")),
    "VECTOR_DB_PATH": get_env("VECTOR_DB_PATH", str(BASE_DIR / "vector_db")),
    "MOCK_LLM": get_env("MOCK_LLM", "false").lower() == "true",
}


def get_llm_settings() -> dict:
    return CONFIG.copy()
