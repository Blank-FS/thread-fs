# app/core/images.py
"""Images attached to comments by link (the comment box's image button).

There are no uploads: a comment links an image on one of the community's image hosts (Community.image_hosts, set by
admins), the sites it trusts not to tell the poster who loaded it. The same list decides which images in comment text
show (the widget's lib/imageHosts.ts).
"""

from urllib.parse import urlparse

from fastapi import HTTPException, status


def is_allowed_image_url(url: str, hosts) -> bool:
    """https, from exactly one of the hosts: no subdomains or lookalikes, credentials or ports."""
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and not parsed.username
        and not parsed.password
        and not parsed.port
        and (parsed.hostname or "") in (hosts or [])
    )


def image_for_community(community, image):
    """The image as stored with a comment, after checking it's from one of the community's hosts; None for none."""
    if image is None:
        return None
    if not is_allowed_image_url(image.url, community.image_hosts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Images can only come from this community's image hosts",
        )
    return image.model_dump()
