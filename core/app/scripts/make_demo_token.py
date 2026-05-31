# app/scripts/make_demo_token.py

from datetime import datetime, timedelta, timezone

from jose import jwt

secret = "dev-threadfs-secret"

payload = {
    "sub": "demo-user-1",
    "username": "Blank",
    "avatar_url": "https://api.dicebear.com/8.x/initials/svg?seed=Blank",
    "iss": "demo-site",
    "aud": "threadfs",
    "exp": datetime.now(timezone.utc) + timedelta(days=1),
}

token = jwt.encode(payload, secret, algorithm="HS256")

print(token)
