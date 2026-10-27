from __future__ import annotations

import re
import sqlite3
from dataclasses import replace
from pathlib import Path

from .errors import DuplicateMemoryError, MemoryNotFoundError, ValidationError
from .models import Memory, utc_now
from .security import reject_sensitive_content


def normalize_content(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip()).casefold()


class SQLiteMemoryStore:
    def __init__(self, path: str | Path):
        self.path = ":memory:" if str(path) == ":memory:" else str(Path(path).expanduser())
        if self.path != ":memory:":
            Path(self.path).resolve().parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                normalized_content TEXT NOT NULL,
                subject TEXT NOT NULL,
                category TEXT NOT NULL,
                importance REAL NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(subject, normalized_content)
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_subject ON memories(subject)"
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteMemoryStore":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Memory:
        return Memory(
            id=row["id"],
            content=row["content"],
            subject=row["subject"],
            category=row["category"],
            importance=row["importance"],
            confidence=row["confidence"],
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def add(
        self,
        content: str,
        subject: str = "global",
        category: str = "other",
        importance: float = 0.5,
        confidence: float = 1.0,
        source: str = "manual",
    ) -> Memory:
        memory = Memory(
            id=None,
            content=content,
            subject=subject,
            category=category,
            importance=importance,
            confidence=confidence,
            source=source,
        ).validated()
        reject_sensitive_content(memory.content)
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO memories (
                    content, normalized_content, subject, category, importance,
                    confidence, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.content,
                    normalize_content(memory.content),
                    memory.subject,
                    memory.category,
                    memory.importance,
                    memory.confidence,
                    memory.source,
                    memory.created_at,
                    memory.updated_at,
                ),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateMemoryError(
                "an identical memory already exists for this subject"
            ) from exc
        return self.get(cursor.lastrowid)

    def get(self, memory_id: int) -> Memory:
        if isinstance(memory_id, bool) or not isinstance(memory_id, int) or memory_id < 1:
            raise ValidationError("memory id must be a positive integer")
        row = self._connection.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            raise MemoryNotFoundError(f"memory {memory_id} not found")
        return self._from_row(row)

    def list(self, subject: str | None = None, limit: int = 100) -> list[Memory]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10000:
            raise ValidationError("limit must be an integer between 1 and 10000")
        if subject is None:
            rows = self._connection.execute(
                "SELECT * FROM memories ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            subject = subject.strip()
            if not subject:
                raise ValidationError("subject must not be empty")
            rows = self._connection.execute(
                """
                SELECT * FROM memories WHERE subject = ?
                ORDER BY created_at DESC, id DESC LIMIT ?
                """,
                (subject, limit),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update(
        self,
        memory_id: int,
        content: str | None = None,
        subject: str | None = None,
        category: str | None = None,
        importance: float | None = None,
        confidence: float | None = None,
        source: str | None = None,
    ) -> Memory:
        current = self.get(memory_id)
        updated = replace(
            current,
            content=current.content if content is None else content,
            subject=current.subject if subject is None else subject,
            category=current.category if category is None else category,
            importance=current.importance if importance is None else importance,
            confidence=current.confidence if confidence is None else confidence,
            source=current.source if source is None else source,
            updated_at=utc_now(),
        ).validated()
        reject_sensitive_content(updated.content)
        try:
            self._connection.execute(
                """
                UPDATE memories SET content = ?, normalized_content = ?, subject = ?,
                    category = ?, importance = ?, confidence = ?, source = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.content,
                    normalize_content(updated.content),
                    updated.subject,
                    updated.category,
                    updated.importance,
                    updated.confidence,
                    updated.source,
                    updated.updated_at,
                    memory_id,
                ),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateMemoryError(
                "the update would duplicate another memory for this subject"
            ) from exc
        return self.get(memory_id)

    def delete(self, memory_id: int) -> None:
        self.get(memory_id)
        self._connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._connection.commit()
