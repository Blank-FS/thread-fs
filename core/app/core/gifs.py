# app/core/gifs.py
"""GIFs in comments, from KLIPY (https://docs.klipy.com).

KLIPY's terms have the widget search from the reader's browser with the community's app key (public, like a site key):
routing it through this server needs their written approval. So all this server does is check what a comment says it
attached really is a KLIPY file, and keep it with the comment: the URL exactly as KLIPY gave it, which their terms
require, never copied or rewritten.
"""

from urllib.parse import urlparse

from fastapi import HTTPException, status

PROVIDER_KLIPY = "klipy"

# Where KLIPY serves media (docs.klipy.com/network-requirements)
KLIPY_MEDIA_HOSTS = frozenset({"static.klipy.com", "static1.klipy.com", "static2.klipy.com"})


def gif_for_community(community, gif):
    """The GIF as stored with a comment, after checking the community takes GIFs; None for none."""
    if gif is None:
        return None
    if not community.klipy_app_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GIFs are off in this community")
    return gif.model_dump()


def is_klipy_media_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in KLIPY_MEDIA_HOSTS and not parsed.username and not parsed.port
