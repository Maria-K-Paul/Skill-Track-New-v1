from __future__ import annotations

import hashlib
import re
from typing import Any


class DuplicateChecker:
    @staticmethod
    def normalize_question_text(text: str) -> str:
        text = text.lower().strip()
        text = text.replace("?", "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def compute_hash_key(text: str) -> str:
        normalized = DuplicateChecker.normalize_question_text(text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def semantic_similarity(text_a: str, text_b: str) -> float:
        a = DuplicateChecker.normalize_question_text(text_a)
        b = DuplicateChecker.normalize_question_text(text_b)
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0
        score = 0.0
        a_words = set(a.split())
        b_words = set(b.split())
        overlap = len(a_words & b_words)
        total = len(a_words | b_words)
        if total:
            score = overlap / total
        return score

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    def check_exact_duplicates(self, new_question_text: str, history: list[str]) -> list[str]:
        key = self.compute_hash_key(new_question_text)
        matches = []
        for existing in history:
            if self.compute_hash_key(existing) == key:
                matches.append(existing)
        return matches

    def check_semantic_duplicates(self, new_question_text: str, history: list[str]) -> list[str]:
        matches = []
        for existing in history:
            similarity = self.semantic_similarity(new_question_text, existing)
            if similarity >= self.similarity_threshold:
                matches.append(existing)
        return matches

    def check_question(self, new_question_text: str, history: list[str]) -> dict[str, Any]:
        exact_matches = self.check_exact_duplicates(new_question_text, history)
        semantic_matches = self.check_semantic_duplicates(new_question_text, history)
        return {
            "exact_duplicate": bool(exact_matches),
            "semantic_duplicate": bool(semantic_matches),
            "duplicates": exact_matches,
            "semantic_duplicates": semantic_matches,
            "notes": [
                "Exact duplicate detected" if exact_matches else "",
                "Semantic duplicate detected" if semantic_matches else "",
            ],
        }
