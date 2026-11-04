# app/scripts/make_demo_token.py

import argparse
from datetime import datetime, timedelta, timezone

from jose import jwt

parser = argparse.ArgumentParser(description="Print a demo embed token")
parser.add_argument(
    "--role",
    choices=["moderator", "admin"],
    help="make the token's user staff, for the moderation widget",
)
args = parser.parse_args()

secret = "dev-threadfs-secret"

payload = {
    "sub": "demo-user-1",
    "username": "Blank",
    "avatar_url": "https://api.dicebear.com/8.x/initials/svg?seed=Blank",
    "iss": "demo-site",
    "aud": "threadfs",
    "exp": datetime.now(timezone.utc) + timedelta(days=30),
}

if args.role:
    payload["threadfs_role"] = args.role

token = jwt.encode(payload, secret, algorithm="HS256")

print(token)
