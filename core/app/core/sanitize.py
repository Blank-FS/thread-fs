# app/core/sanitize.py

import re

_SCRIPT_RE = re.compile(
    r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL
)
_DANGEROUS_TAG_RE = re.compile(
    r"<\s*/?\s*(script|style|iframe|object|embed|link|meta|base|form)\b[^>]*>",
    re.IGNORECASE,
)
_EVENT_ATTR_RE = re.compile(
    r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE
)


def sanitize_comment_markdown(markdown: str) -> str:
    cleaned = _SCRIPT_RE.sub("", markdown or "")
    cleaned = _DANGEROUS_TAG_RE.sub("", cleaned)
    cleaned = _EVENT_ATTR_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
