from __future__ import annotations

import re

from .errors import SensitiveContentError

SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\b(?:password|passwd|api[_ -]?key|secret|access[_ -]?token)(?!\s+(?:manager|reset|recovery|hashing|security|policy)\b)(?:\s*(?:is|=|:)\s*|\s+)[^\s,;，；]+"),
    re.compile(r"(?:密码|密钥|令牌|身份证号|家庭住址|详细住址)(?:\s*(?:是|为|：|:)\s*|\s+)[^\s，。；,;]+"),
    re.compile(r"(?i)\bsk-[a-z0-9_-]{8,}\b"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
)


def reject_sensitive_content(content: str) -> None:
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(content):
            raise SensitiveContentError(
                "memory appears to contain a credential or sensitive personal data; "
                "store a non-sensitive preference or fact instead"
            )
