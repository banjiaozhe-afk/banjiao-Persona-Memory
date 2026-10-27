from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import ConfigurationError
from .models import Persona


def _string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"persona field '{key}' must be a non-empty string")
    return value.strip()


def _string_list(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data.get(key)
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise ConfigurationError(f"persona field '{key}' must be a non-empty string array")
    return tuple(item.strip() for item in value)


def load_persona(path: str | Path) -> Persona:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"persona file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"invalid JSON in {path}: line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(data, dict):
        raise ConfigurationError("persona root must be a JSON object")

    raw_examples = data.get("examples", [])
    if not isinstance(raw_examples, list):
        raise ConfigurationError("persona field 'examples' must be an array")
    examples: list[dict[str, str]] = []
    for index, example in enumerate(raw_examples):
        if not isinstance(example, dict):
            raise ConfigurationError(f"example {index} must be an object")
        try:
            examples.append(
                {
                    "scenario": _string(example, "scenario"),
                    "user": _string(example, "user"),
                    "assistant": _string(example, "assistant"),
                }
            )
        except ConfigurationError as exc:
            raise ConfigurationError(f"invalid example {index}: {exc}") from exc

    return Persona(
        name=_string(data, "name"),
        background=_string(data, "background"),
        style=_string_list(data, "style"),
        likes=_string_list(data, "likes"),
        dislikes=_string_list(data, "dislikes"),
        response_rules=_string_list(data, "response_rules"),
        boundaries=_string_list(data, "boundaries"),
        examples=tuple(examples),
    )
