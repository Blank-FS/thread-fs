# ThreadFS Core

ThreadFS Core is the backend comment engine for ThreadFS, an open-source embeddable discussion system similar to Disqus. It provides the API used by the ThreadFS React component to load threads, post comments, reply, vote, edit/delete own comments, and validate host-site authentication tokens.

The intended production flow is:

```text
Host website frontend
  -> ThreadFS React component
  -> ThreadFS Core API

Host website backend
  -> issues short-lived ThreadFS JWT using @threadfs/server
  -> frontend passes token to ThreadFS component
```

## Features

- Embeddable comment API
- Community public keys
- Allowed-origin checks per community
- External user authentication via host-site-issued JWTs
- Anonymous read support
- Authenticated comment creation
- Nested replies
- Pagination and sorting
- Voting
- Edit/delete own comments
- GIFs from KLIPY, optional per community (see GIFs below)
- Soft-deleted comments
- HTML sanitization
- Basic rate limiting
- Alembic migrations
- Deployment-friendly FastAPI backend

## Tech Stack

- Python 3.12
- FastAPI
- SQLAlchemy async ORM
- PostgreSQL
- Alembic
- asyncpg
- Uvicorn/Gunicorn
- Docker-ready

## Project Structure

```text
core/
  app/
    api/
      routes/
      deps.py
      rate_limits.py
    core/
      config.py
      rate_limit.py
      sanitize.py
    db/
      base.py
      session.py
    models/
    repositories/
    schemas/
    scripts/
    services/
    main.py
  alembic/
  alembic.ini
  pyproject.toml
  Dockerfile
  docker-compose.yml
  README.md
```

## Environment Variables

Create a `.env` file in the `core/` directory.

```env
ENVIRONMENT=development
DB_CREATE_DROP=false

DATABASE_URL=postgresql+asyncpg://threadfs_user:threadfs_password@localhost:5432/threadfs

CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:5173

RATE_LIMIT_ENABLED=true
RATE_LIMIT_READ_PER_MINUTE=120
RATE_LIMIT_COMMENT_CREATE_PER_MINUTE=5
RATE_LIMIT_COMMENT_EDIT_PER_HOUR=20
RATE_LIMIT_COMMENT_DELETE_PER_HOUR=20
RATE_LIMIT_VOTE_PER_MINUTE=60

# Webhooks (see Webhooks below): the loop that sends queued events, and how often it looks
WEBHOOK_DELIVERY_ENABLED=true
WEBHOOK_POLL_SECONDS=2
# Development only: give the seeded demo community a webhook (see Webhooks › Trying it locally)
# DEMO_WEBHOOK_URL=http://localhost:8787/webhooks
# Development only: turn GIFs on in the seeded demo community with a KLIPY test key (see GIFs below)
# DEMO_KLIPY_APP_KEY=...
```

For production:

```env
ENVIRONMENT=production
DB_CREATE_DROP=false

DATABASE_URL=postgresql+asyncpg://threadfs_user:STRONG_PASSWORD@YOUR_DB_HOST:5432/threadfs

CORS_ALLOW_ORIGINS=https://example.com,https://www.example.com

RATE_LIMIT_ENABLED=true
RATE_LIMIT_READ_PER_MINUTE=120
RATE_LIMIT_COMMENT_CREATE_PER_MINUTE=5
RATE_LIMIT_COMMENT_EDIT_PER_HOUR=20
RATE_LIMIT_COMMENT_DELETE_PER_HOUR=20
RATE_LIMIT_VOTE_PER_MINUTE=60
```

Never enable `DB_CREATE_DROP=true` in production.

## Local Development

ThreadFS Core uses `uv` for Python environment and dependency management.

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or with Homebrew:

```bash
brew install uv
```

### 2. Create virtual environment & Install dependencies

```bash
uv venv
source .venv/bin/activate

uv sync
```

### 3. Start PostgreSQL

Use local PostgreSQL, Docker, or RDS. Example with Docker:

```bash
docker run --name threadfs-postgres \
  -e POSTGRES_DB=threadfs \
  -e POSTGRES_USER=threadfs_user \
  -e POSTGRES_PASSWORD=threadfs_password \
  -p 5432:5432 \
  -d postgres:17
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Create a local community integration

```bash
python -m app.scripts.setup_community \
  --owner-email admin@threadfs.local \
  --name "Demo Local" \
  --slug demo-local \
  --description "Local ThreadFS demo community" \
  --origin http://localhost:3000 \
  --origin http://localhost:5173 \
  --issuer demo-local
```

The script prints:

```text
Community key: tfspub_...
THREADFS_SECRET=tfssec_...
```

Use the community key in the React component and store `THREADFS_SECRET` only in the host website backend.

### 6. Run the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Host Website Integration

The host website backend should issue short-lived ThreadFS tokens using `@threadfs/server`.

Example Next.js route:

```ts
import { NextResponse } from "next/server";
import { createThreadFSToken } from "@threadfs/server";

export async function GET() {
  const user = await getCurrentUserSomehow();

  if (!user) {
    return NextResponse.json({ token: null });
  }

  const token = await createThreadFSToken({
    secret: process.env.THREADFS_SECRET!,
    issuer: "threadfs-local",
    subject: String(user.id),
    username: user.username,
    avatarUrl: user.avatarUrl,
    expiresInSeconds: 15 * 60,
  });

  return NextResponse.json({ token });
}
```

Frontend usage:

```tsx
<ThreadFSComments
  apiBaseUrl="http://localhost:8000"
  communityKey="tfspub_..."
  threadId="demo-thread"
  getAuthToken={async () => {
    const res = await fetch("/api/threadfs-token", {
      credentials: "include",
    });

    const data = await res.json();
    return data.token ?? null;
  }}
  onAuthRequired={() => {
    window.location.href = `/login?next=${encodeURIComponent(window.location.href)}`;
  }}
  authorProfileUrl={(user) =>
    user.external_user_id ? `/users/${user.external_user_id}` : null
  }
/>
```

## API Overview

### Read comments

```http
GET /api/v1/embed/comments?thread_id=demo-thread&limit=20&offset=0&sort=latest
```

Top-level comments default to latest sorting.

Replies:

```http
GET /api/v1/embed/comments?thread_id=demo-thread&parent_comment_id=123&limit=20&offset=0&sort=oldest
```

Replies should generally use oldest sorting.

One comment in context, for a link to it:

```http
GET /api/v1/embed/comments/123/context?thread_id=demo-thread&limit=20
```

Returns `{ "focused_comment_id": 123, "root": … }`: the comment's top-level comment, holding each reply down to it, one
per level (siblings left out), with the comment's own first page of replies (oldest first, `replies_has_more` and
`replies_next_offset` for the rest). An ancestor with other replies says so (`replies_has_more`, `replies_next_offset`
0), so they can be loaded with the usual replies listing, skipping the one already shown. 404 when the comment isn't
in that thread, so a widget can fall back to the list.

### Create comment

```http
POST /api/v1/embed/comments
Authorization: Bearer <threadfs-user-token>
X-ThreadFS-Community-Key: tfspub_...
Origin: https://your-site.com
Content-Type: application/json
```

```json
{
  "thread_id": "demo-thread",
  "title": "Demo Thread Page",
  "source_url": "https://your-site.com/example/1",
  "content": "<p>Hello!</p>",
  "parent_comment_id": null
}
```

Where the community has GIFs on, a comment can also carry one, and then needs no text (see GIFs below):

```json
{
  "thread_id": "demo-thread",
  "content": "",
  "gif": {
    "provider": "klipy",
    "slug": "hello-hi-662",
    "url": "https://static.klipy.com/ii/.../hello.webp",
    "width": 220,
    "height": 220,
    "title": "Hello"
  }
}
```

Thread rows are created lazily only when an authenticated user posts the first comment.

### Vote

```http
POST /api/v1/embed/comments/{comment_id}/votes
```

```json
{
  "value": 1
}
```

Use:

```text
1  = upvote
-1 = downvote
0  = remove vote
```

Clicking the same vote again should toggle it off.

### Edit own comment

```http
PATCH /api/v1/embed/comments/{comment_id}
```

```json
{
  "content": "<p>Updated comment</p>"
}
```

`gif` works as when creating: left out, the comment keeps its GIF; `null` removes it.

### Delete own comment

```http
DELETE /api/v1/embed/comments/{comment_id}
```

Comments are soft-deleted so reply trees remain intact.

## Security Model

ThreadFS uses multiple layers:

### Community key

The community key is public and intended to be embedded in frontend code.

```text
X-ThreadFS-Community-Key: tfspub_...
```

It identifies the community but is not a secret.

### Allowed origins

Each community has allowed origins. Browser requests from unapproved origins are rejected.

This is useful protection for normal browser embeds, but it is not cryptographic proof because non-browser clients can spoof `Origin`.

### User JWT

Write actions require a valid user JWT issued by the host website backend. This is the primary protection for commenting, voting, editing, and deleting.

### CORS

CORS controls which browsers are allowed to call the API.

CORS should be configured with explicit origins:

```env
CORS_ALLOW_ORIGINS=https://example.com,https://www.example.com
```

Do not use `allow_origins=["*"]` with credentials.

### Rate limiting

ThreadFS includes basic rate limiting for reads, comments, votes, edits, and deletes. For a single-instance prototype, the in-memory limiter is acceptable. For multi-instance deployment, replace it with Redis.

## Thread titles and links

Threads are created by their first comment, so a browser-sent title and link can't be trusted: anyone signed in can send anything. Hosts should have their server vouch for them, by signing these claims into the embed token:

```json
{
  "threadfs_signed_threads": true,
  "threadfs_thread": { "id": "anime:1:ep:1", "title": "Frieren Episode 1", "url": "https://example.com/anime/1/episode/1" }
}
```

With `threadfs_signed_threads`, browser-sent details are ignored, and a token can only create the thread named in `threadfs_thread`. It can still comment on any existing thread. A matching claim also updates an existing thread's details.

Without it, a thread keeps the details of its first comment, and a link is dropped unless it's on one of the community's allowed origins. The title isn't checked, so a host that shows titles should sign them.

## GIFs

The comment box can offer GIFs from [KLIPY](https://docs.klipy.com). It's off until a community has a KLIPY app key,
which its admins set in the moderation panel (Admin › GIFs; logged, without the key), or from the server:

```bash
uv run python -m app.scripts.set_gifs --community my-site --klipy-key <app key>
uv run python -m app.scripts.set_gifs --community my-site --off
```

- **The key** comes from the API Keys page of KLIPY's Partner Panel (partner.klipy.com). It isn't a secret: KLIPY's
  terms have the reader's browser search with it, rather than a server in between, so the community's config hands it
  to the widget. Test keys allow 100 searches an hour; ask KLIPY for production access before launch.
- **Content rating** is set on the Partner Panel, where it applies to every search with the key.
- **What's stored:** the GIF's slug, its URL exactly as KLIPY gave it, its size and title. Their terms don't allow
  copying or rewriting their files, so they're shown from KLIPY's servers. The API accepts a GIF only from KLIPY's media
  hosts (`static.klipy.com`, `static1.`, `static2.`), so a comment can't use one to load an image from anywhere else.
- **Moderation:** a GIF is part of its comment. Removing the comment hides it, and moderators still see it.
- **Webhooks:** a comment that's only a GIF has `[GIF]` as its excerpt.
- Turning GIFs off hides the button. GIFs already posted stay.

## Webhooks

ThreadFS tells your site when something happens, so it can notify its users, following the
[Standard Webhooks](https://www.standardwebhooks.com) spec.

### Setting one up

```bash
python -m app.scripts.set_webhook --community my-site --url https://example.com/hooks/threadfs
```

It prints a secret (`whsec_...`) once: keep it on your server. A new endpoint gets every event; `--events` picks some
(comma-separated). `--rotate-secret` makes a new one, `--disable` stops
sending (queued events wait), and `--url` changes the address. URLs must be `https` (`http` only for localhost).

### Events

**`comment.reply`**: someone replied to a comment. Not sent for replying to yourself, or to a comment that's deleted or
removed.

```json
{
  "type": "comment.reply",
  "timestamp": "2026-11-11T21:30:00+00:00",
  "data": {
    "thread": { "id": "anime:1:ep:5", "title": "Frieren Episode 5", "url": "https://example.com/anime/1/episode/5" },
    "comment": {
      "id": 812,
      "excerpt": "Agreed, the ending of this one was...",
      "created_at": "2026-11-11T21:30:00+00:00",
      "author": { "identity_provider": "external", "external_user_id": "42", "display_name": "Sora" }
    },
    "parent_comment": {
      "id": 790,
      "author": { "identity_provider": "external", "external_user_id": "7", "display_name": "Mira" }
    }
  }
}
```

**`comment.created`**: any new comment, top-level or a reply. ThreadFS has no idea who a thread belongs to, so this is
how a site tells, say, the owner of a profile or a post about comments on it. The same `thread` and `comment` as
above, and `parent_comment_id` (`null` for a top-level comment) instead of `parent_comment`. A reply sends both events.

`external_user_id` is the `sub` your site put in the user's token. Link to the reply with the thread's page plus
`#c-<id in hexadecimal>` (the React widget's `commentHash`).

### Verifying a delivery

Each POST carries `webhook-id`, `webhook-timestamp` (Unix seconds) and `webhook-signature` (`v1,<base64>`): the
HMAC-SHA256 of `<webhook-id>.<webhook-timestamp>.<raw body>`, keyed with the secret's base64-decoded part after
`whsec_`. Compare in constant time, reject timestamps more than a few minutes off, and remember the `webhook-id`s you've
handled: a delivery can arrive more than once. Any Standard Webhooks library does all of this.

Answer with any 2xx. Anything else, or no answer in 10 seconds, is retried after 5 seconds, 5 minutes, 30 minutes, 2,
5, 10 and 10 hours, then dropped.

### Trying it locally

```bash
python -m app.scripts.webhook_listener          # prints each delivery and checks its signature
python -m app.scripts.webhook_listener --fail   # answers 500, to watch the retries
```

Set `DEMO_WEBHOOK_URL=http://localhost:8787/webhooks` in `core/.env` and the dev seed gives the demo community a webhook
there, with a development secret the listener already knows. Then reply to a comment on the demo page and the event
appears in the listener. The seed reads it at startup, and `--reload` only restarts for code changes, so after changing
it stop and start the server. (For another community, run `set_webhook` with that URL and pass the secret it prints as
`--secret`.)

### How it works

Events are written to `webhook_deliveries` in the same transaction as the comment (an outbox), so one is never lost or
sent for a comment that wasn't saved. Every worker runs the delivery loop and claims rows with `SKIP LOCKED`, so several
workers don't send the same event at once.

## Deployment on EC2

The examples below use Aniworks as a sample host website. Replace the domain, issuer, and thread IDs with your own application values.

### 1. Provision infrastructure

Recommended prototype setup:

```text
EC2 instance
PostgreSQL RDS or PostgreSQL container
Nginx or Caddy reverse proxy
Cloudflare DNS/TLS
```

Security group:

```text
Allow 80/443 from the internet
Do not expose port 8000 publicly
Allow database access only from the backend host/security group
```

### 2. Clone repository

```bash
git clone <your-repo-url>
cd thread-fs/core
```

### 3. Create `.env`

```bash
nano .env
```

Use production values:

```env
ENVIRONMENT=production
DB_CREATE_DROP=false
DATABASE_URL=postgresql+asyncpg://threadfs_user:STRONG_PASSWORD@YOUR_DB_HOST:5432/threadfs
CORS_ALLOW_ORIGINS=https://aniworks.net,https://www.aniworks.net
RATE_LIMIT_ENABLED=true
```

### 4. Build and run with Docker Compose

```bash
docker compose build
docker compose up -d
docker compose logs -f
```

A typical `docker-compose.yml` command should run migrations before starting the server:

```bash
alembic upgrade head && gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000
```

### 5. Configure reverse proxy

Example Nginx config:

```nginx
server {
    listen 80;
    server_name api.threadfs.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

If using Cloudflare, make sure the backend receives the real client IP through `CF-Connecting-IP` or a trusted proxy header.

### 6. Run migrations

If not already run by Compose:

```bash
alembic upgrade head
```

### 7. Create production community

```bash
python -m app.scripts.setup_community \
  --owner-email admin@aniworks.net \
  --name "Aniworks" \
  --slug aniworks \
  --description "Aniworks production comments" \
  --origin https://aniworks.net \
  --origin https://www.aniworks.net \
  --issuer aniworks
```

Save the printed values:

```text
Community key -> frontend ThreadFSComments communityKey
THREADFS_SECRET -> host website backend only
```

### 8. Smoke test

Health:

```bash
curl https://api.threadfs.example.com/health
```

Read comments:

```bash
curl -i \
  -H "Origin: https://aniworks.net" \
  -H "X-ThreadFS-Community-Key: tfspub_..." \
  "https://api.threadfs.example.com/api/v1/embed/comments?thread_id=test"
```

Expected response:

```json
{
  "items": [],
  "limit": 20,
  "offset": 0,
  "next_offset": null,
  "has_more": false,
  "total": 0
}
```

## Production Checklist

Before exposing to users:

- [ ] `ENVIRONMENT=production`
- [ ] `DB_CREATE_DROP=false`
- [ ] PostgreSQL database is reachable
- [ ] `alembic upgrade head` succeeds
- [ ] `/health` returns OK
- [ ] Production community created
- [ ] Allowed origins include your host site
- [ ] Host backend has `THREADFS_SECRET`
- [ ] React component uses production `communityKey`
- [ ] CORS allows the host site
- [ ] Rate limiting enabled
- [ ] HTML sanitization enabled
- [ ] Port 8000 is not publicly exposed
- [ ] API is served through HTTPS

## Development Notes

### Regenerate migration

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

### Reset local database

Only do this in development:

```bash
dropdb threadfs
createdb threadfs
alembic upgrade head
```

### Run setup script again

The setup script is idempotent. It will reuse existing community/auth provider records and will not print an existing secret again.

## Roadmap

Near-term:

- Report comment endpoint
- Minimal admin scripts
- Redis-backed rate limiting
- Docker production hardening
- Better deployment examples

Later:

- Admin dashboard
- Moderation queue
- Signed embed context
- RS256 host-site auth provider support
