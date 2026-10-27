from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .errors import ValidationError

MEMORY_CATEGORIES = {
    "preference",
    "profile",
    "event",
    "relationship",
    "project",
    "other",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_text(value: Any, name: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name} must be a non-empty string")
    value = value.strip()
    if len(value) > max_length:
        raise ValidationError(f"{name} exceeds {max_length} characters")
    return value


def require_probability(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be a number between 0 and 1")
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValidationError(f"{name} must be between 0 and 1")
    return value


@dataclass(frozen=True)
class Memory:
    id: int | None
    content: str
    subject: str = "global"
    category: str = "other"
    importance: float = 0.5
    confidence: float = 1.0
    source: str = "manual"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def validated(self) -> "Memory":
        content = require_text(self.content, "content", 2000)
        subject = require_text(self.subject, "subject", 100)
        if self.category not in MEMORY_CATEGORIES:
            allowed = ", ".join(sorted(MEMORY_CATEGORIES))
            raise ValidationError(f"category must be one of: {allowed}")
        return Memory(
            id=self.id,
            content=content,
            subject=subject,
            category=self.category,
            importance=require_probability(self.importance, "importance"),
            confidence=require_probability(self.confidence, "confidence"),
            source=require_text(self.source, "source", 200),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "subject": self.subject,
            "category": self.category,
            "importance": self.importance,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class Turn:
    role: str
    content: str

    def validated(self) -> "Turn":
        if self.role not in {"user", "assistant"}:
            raise ValidationError("turn role must be 'user' or 'assistant'")
        return Turn(self.role, require_text(self.content, "turn content", 4000))


@dataclass(frozen=True)
class Persona:
    name: str
    background: str
    style: tuple[str, ...]
    likes: tuple[str, ...]
    dislikes: tuple[str, ...]
    response_rules: tuple[str, ...]
    boundaries: tuple[str, ...]
    examples: tuple[dict[str, str], ...] = ()

    def to_prompt(self) -> str:
        sections = [
            f"姓名：{self.name}",
            f"背景：{self.background}",
            "说话风格：" + "；".join(self.style),
            "偏好：" + "；".join(self.likes),
            "不喜欢：" + "；".join(self.dislikes),
            "回复规则：" + "；".join(self.response_rules),
            "行为边界：" + "；".join(self.boundaries),
        ]
        if self.examples:
            rendered = []
            for example in self.examples:
                rendered.append(
                    f"场景：{example['scenario']}\n"
                    f"用户：{example['user']}\n"
                    f"回复：{example['assistant']}"
                )
            sections.append("风格示例：\n" + "\n".join(rendered))
        return "\n".join(sections)


@dataclass(frozen=True)
class ScoredMemory:
    memory: Memory
    score: float
    relevance: float


@dataclass(frozen=True)
class BuiltContext:
    prompt: str
    used_memory_ids: tuple[int, ...]
    used_turns: int
    dropped_memories: int
    dropped_turns: int
    summary_included: bool
    state_included: bool

    def metadata(self) -> dict[str, Any]:
        return {
            "characters": len(self.prompt),
            "used_memory_ids": list(self.used_memory_ids),
            "used_turns": self.used_turns,
            "dropped_memories": self.dropped_memories,
            "dropped_turns": self.dropped_turns,
            "summary_included": self.summary_included,
            "state_included": self.state_included,
        }
