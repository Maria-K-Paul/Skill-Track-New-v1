from __future__ import annotations

from collections import defaultdict

from langchain_core.chat_history import InMemoryChatMessageHistory


_HISTORIES: dict[str, InMemoryChatMessageHistory] = defaultdict(InMemoryChatMessageHistory)


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    """Return the in-memory conversation history for one generation run."""
    return _HISTORIES[session_id]


def clear_session_history(session_id: str) -> None:
    _HISTORIES.pop(session_id, None)