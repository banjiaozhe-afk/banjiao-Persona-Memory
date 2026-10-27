from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from .models import ScoredMemory, require_text
from .store import SQLiteMemoryStore, normalize_content

WORD_PATTERN = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]+", re.IGNORECASE)


def tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in WORD_PATTERN.finditer(text.casefold()):
        value = match.group(0)
        if value.isascii():
            tokens.add(value)
        elif len(value) == 1:
            tokens.add(value)
        else:
            tokens.update(value[index : index + 2] for index in range(len(value) - 1))
    return tokens


class MemoryRetriever:
    def __init__(self, store: SQLiteMemoryStore):
        self.store = store

    def search(
        self,
        query: str,
        subject: str | None = None,
        limit: int = 5,
        min_score: float = 0.12,
    ) -> list[ScoredMemory]:
        if not query or not query.strip():
            return []
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0 and 1")

        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        if subject is not None:
            subject = require_text(subject, "subject", 100)
            allowed_subjects = {subject, "global"}
        else:
            allowed_subjects = {"global"}
        candidates = [
            item
            for item in self.store.list(limit=10000)
            if item.subject in allowed_subjects
        ]

        now = datetime.now(timezone.utc)
        best_by_content: dict[str, ScoredMemory] = {}
        for memory in candidates:
            memory_tokens = tokenize(memory.content)
            overlap = len(query_tokens & memory_tokens)
            if overlap == 0:
                continue
            relevance = overlap / len(query_tokens)
            age_days = max(
                0.0,
                (now - datetime.fromisoformat(memory.created_at)).total_seconds() / 86400,
            )
            recency = math.exp(-age_days / 30.0)
            subject_match = 1.0 if subject is not None and memory.subject == subject else 0.0
            score = (
                0.65 * relevance
                + 0.15 * memory.importance
                + 0.10 * recency
                + 0.05 * memory.confidence
                + 0.05 * subject_match
            )
            if score >= min_score:
                result = ScoredMemory(memory, score, relevance)
                key = normalize_content(memory.content)
                previous = best_by_content.get(key)
                if previous is None or result.score > previous.score:
                    best_by_content[key] = result

        results = sorted(
            best_by_content.values(),
            key=lambda item: (item.score, item.memory.id or 0),
            reverse=True,
        )
        return results[:limit]
