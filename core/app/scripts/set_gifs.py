# app/scripts/set_gifs.py
"""Turns GIFs in a community's comment box on or off (app.core.gifs). The community's admins can do the same in the
moderation panel (Admin › GIFs).

    python -m app.scripts.set_gifs --community my-site --klipy-key <app key>
    python -m app.scripts.set_gifs --community my-site --off

The key is a KLIPY app key, from the API Keys page of their Partner Panel (partner.klipy.com). It isn't secret: the
widget searches from the reader's browser with it, as KLIPY's terms require. Set the content rating there too, as it
applies to every search with the key. Test keys allow 100 searches an hour; ask KLIPY for production access before
launch. Turning GIFs off hides the button; GIFs already posted stay.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.db.session import async_session_maker
from app.models.community import Community


async def main(args: argparse.Namespace) -> None:
    async with async_session_maker() as session:
        community = (
            await session.execute(select(Community).where(Community.slug == args.community))
        ).scalar_one_or_none()
        if community is None:
            raise SystemExit(f"No community with slug {args.community!r}")

        community.klipy_app_key = None if args.off else args.klipy_key
        await session.commit()

        print(f"GIFs for {community.slug}: {'on (KLIPY)' if community.klipy_app_key else 'off'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Turn GIFs in a community's comment box on or off")
    parser.add_argument("--community", required=True, help="The community's slug")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--klipy-key", help="A KLIPY app key, which turns GIFs on")
    choice.add_argument("--off", action="store_true", help="Turn GIFs off")
    asyncio.run(main(parser.parse_args()))
