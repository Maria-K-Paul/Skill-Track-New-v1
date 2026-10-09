from __future__ import annotations

import json
from typing import Any


class MockLLM:
    """Deterministic mock LLM used for local testing without an external model."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.counter = 0

    def invoke(self, *args, **kwargs) -> Any:
        self.counter += 1
        return {
            "content": json.dumps({
                "question": f"Which mock statement is correct for generated item {self.counter}?",
                "options": [
                    {"id": "A", "text": "This is the correct mock answer."},
                    {"id": "B", "text": "This is an incorrect mock answer."},
                    {"id": "C", "text": "This is another incorrect mock answer."},
                    {"id": "D", "text": "This is an unrelated mock answer."},
                ],
                "correct_option": "A",
                "explanation": "The deterministic mock marks option A as correct.",
            }),
        }

    def __call__(self, *args, **kwargs):
        return self.invoke(*args, **kwargs)
