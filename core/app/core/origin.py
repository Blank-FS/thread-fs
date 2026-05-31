# app/core/origin.py

from urllib.parse import urlparse


def normalize_origin(origin: str) -> str:
    parsed = urlparse(origin)

    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid origin")

    return f"{parsed.scheme}://{parsed.netloc}"
