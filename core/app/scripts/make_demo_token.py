# app/scripts/make_demo_token.py

import json
from datetime import datetime, timedelta, timezone

from jose import jwt

# Users from the demo seed (app/db/init_db.py), one of each kind the widgets treat differently
DEMO_USERS = [
    {"id": "demo-user-1", "name": "Blank", "role": None, "avatar": True},
    {"id": "demo-user-5", "name": "Nova", "role": None, "avatar": False},
    {"id": "demo-user-2", "name": "Sora", "role": "moderator", "avatar": True},
    {"id": "demo-user-3", "name": "Shiro", "role": "admin", "avatar": True},
]

# The seed's development secret, so these only ever work on a local demo
SECRET = "dev-threadfs-secret"


def make_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "username": user["name"],
        "avatar_url": f"https://api.dicebear.com/8.x/initials/svg?seed={user['name']}" if user["avatar"] else None,
        "iss": "demo-site",
        "aud": "threadfs",
        "exp": datetime.now(timezone.utc) + timedelta(days=365),
    }

    if user["role"]:
        payload["threadfs_role"] = user["role"]

    return jwt.encode(payload, SECRET, algorithm="HS256")


users = [
    {"id": user["id"], "name": user["name"], "role": user["role"], "token": make_token(user)}
    for user in DEMO_USERS
]

print(f"VITE_THREADFS_DEMO_USERS={json.dumps(users, separators=(',', ':'))}")
