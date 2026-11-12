# app/scripts/set_webhook.py
"""Sets a community's webhook endpoint (app.services.webhook_service).

    python -m app.scripts.set_webhook --community my-site --url https://example.com/hooks/threadfs
    python -m app.scripts.set_webhook --community my-site --rotate-secret
    python -m app.scripts.set_webhook --community my-site --disable

One endpoint per community here (the tables allow more). The secret is printed when it's made or rotated: give it to
the site, which verifies each delivery's webhook-signature with it.
"""

import argparse
import asyncio
from urllib.parse import urlparse

from sqlalchemy import select

from app.db.session import async_session_maker
from app.models.community import Community
from app.models.webhook import CommunityWebhook
from app.services.webhook_service import ALL_EVENTS, generate_secret


def valid_url(url: str) -> str:
    parsed = urlparse(url)
    local = parsed.hostname in ("localhost", "127.0.0.1") or (parsed.hostname or "").endswith(".localhost")
    # Plain HTTP only for this machine: deliveries carry user ids and are signed with a shared secret
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise argparse.ArgumentTypeError("The URL must be https (http only for localhost)")
    return url


async def main(args: argparse.Namespace) -> None:
    async with async_session_maker() as session:
        community = (
            await session.execute(select(Community).where(Community.slug == args.community))
        ).scalar_one_or_none()
        if community is None:
            raise SystemExit(f"No community with slug {args.community!r}")

        webhook = (
            await session.execute(
                select(CommunityWebhook)
                .where(CommunityWebhook.community_id == community.id)
                .order_by(CommunityWebhook.id)
            )
        ).scalars().first()

        new_secret = None
        if webhook is None:
            if not args.url:
                raise SystemExit("No webhook yet: give --url to create one")
            new_secret = generate_secret()
            webhook = CommunityWebhook(
                community_id=community.id,
                url=args.url,
                secret=new_secret,
                events=args.events or ",".join(ALL_EVENTS),
                is_enabled=True,
            )
            session.add(webhook)
        else:
            if args.url:
                webhook.url = args.url
            if args.events:
                webhook.events = args.events
            if args.rotate_secret:
                new_secret = generate_secret()
                webhook.secret = new_secret
            webhook.is_enabled = not args.disable

        await session.commit()

        print(f"Webhook for {community.slug}: {webhook.url}")
        print(f"Events: {webhook.events}  Enabled: {webhook.is_enabled}")
        if new_secret:
            print(f"Secret (shown once): {new_secret}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set a community's webhook endpoint")
    parser.add_argument("--community", required=True, help="The community's slug")
    parser.add_argument("--url", type=valid_url, help="Where events are POSTed")
    parser.add_argument("--events", help="Comma-separated event types (all of them when created)")
    parser.add_argument("--rotate-secret", action="store_true", help="Make a new secret; the old one stops working")
    parser.add_argument("--disable", action="store_true", help="Stop sending (queued events stay queued)")
    asyncio.run(main(parser.parse_args()))
