from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .config import CONFIG
import logging


def get_llm() -> BaseChatModel:
    """Return a chat model compatible with LangChain based on the configured provider."""
    if CONFIG["MOCK_LLM"]:
        from .services.mock_llm import MockLLM

        return MockLLM()

    provider = (CONFIG["LLM_PROVIDER"] or "ollama").lower()

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            from langchain_community.chat_models import ChatOllama

        return ChatOllama(
            model=CONFIG["OLLAMA_MODEL"],
            base_url=CONFIG["OLLAMA_BASE_URL"],
            temperature=0.1,
        )

    if provider in {"gemini", "google", "google-gemini"}:
        if not CONFIG.get("GEMINI_API_KEY"):
            raise ValueError("GEMINI_API_KEY or GEMINI_API must be set when LLM_PROVIDER=gemini")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise ImportError("Install langchain-google-genai to use the Gemini provider.") from exc

        logging.info("-"* 100)
        logging.info("Using Gemini LLM")
        logging.info("-"* 100)

        return ChatGoogleGenerativeAI(
            model=CONFIG["GEMINI_MODEL"],
            google_api_key=CONFIG["GEMINI_API_KEY"],
            temperature=0.1,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}. Use 'ollama' or 'gemini'.")
