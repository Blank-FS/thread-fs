# @threadfs/server

Server-side utilities for integrating a host website with ThreadFS.

This package helps a host application issue short-lived ThreadFS user tokens. Those tokens allow the ThreadFS React component to authenticate comment creation, voting, editing, and deleting against ThreadFS Core.

## What This Package Does

`@threadfs/server` runs on the host website backend, not in the browser.

It creates JWTs containing host-user identity claims such as:

- external user ID
- username/display name
- avatar URL
- issuer
- audience
- expiration time

ThreadFS Core verifies these tokens and maps them to `CommunityUser` records.

## What This Package Does Not Do

This package does not replace your website’s authentication system.

Your host app is still responsible for:

- user signup/login
- sessions/cookies
- user profile storage
- permission checks inside your own app

ThreadFS only needs a signed token proving who the current host-site user is.

## Installation

This package is not published to npm yet.

For local development, install from a local package tarball or workspace.

### Local tarball

```json
{
  "dependencies": {
    "@threadfs/server": "file:../../../thread-fs/integration/backend/nodejs/threadfs-server-0.1.0.tgz"
  }
}
```

After making changes to this package:

```bash
npm run build
npm pack
```

Then refresh the consuming app’s lockfile:

```bash
rm -f package-lock.json
rm -rf node_modules
npm install
```

### Workspace

If your host app and ThreadFS packages are in the same monorepo, prefer a workspace dependency:

```json
{
  "dependencies": {
    "@threadfs/server": "workspace:*"
  }
}
```

## Basic Usage

Example host backend route:

```ts
import { createThreadFSToken } from "@threadfs/server";

export async function GET() {
  const user = await getCurrentUserSomehow();

  if (!user) {
    return Response.json({ token: null });
  }

  const token = await createThreadFSToken({
    secret: process.env.THREADFS_SECRET!,
    issuer: "example-site",
    subject: String(user.id),
    username: user.username,
    avatarUrl: user.avatarUrl,
    expiresInSeconds: 15 * 60,
  });

  return Response.json({ token });
}
```

Then in the frontend:

```tsx
<ThreadFSComments
  apiBaseUrl="https://threadfs-api.example.com"
  communityKey="tfspub_your_public_community_key"
  threadId="post:123"
  getAuthToken={async () => {
    const res = await fetch("/api/threadfs-token", {
      credentials: "include",
    });

    const data = await res.json();
    return data.token ?? null;
  }}
/>
```

## Token Claims

A generated token should contain enough information for ThreadFS Core to identify the user within a specific community.

Typical claims:

```json
{
  "sub": "123",
  "username": "Blank",
  "avatar_url": "https://example.com/avatar.png",
  "iss": "example-site",
  "aud": "threadfs",
  "exp": 1779726591
}
```

### `sub`

The stable user ID from the host website.

This should not change when the user edits their username.

### `username`

The display name shown in comments.

### `avatar_url`

Optional URL to the user’s avatar.

### `iss`

The issuer configured in ThreadFS Core for the community auth provider.

Example:

```text
example-site
aniworks
```

### `aud`

The intended audience.

Usually:

```text
threadfs
```

### `exp`

Expiration timestamp.

Recommended token lifetime:

```text
15 minutes
```

The frontend should use `getAuthToken` so it can refresh expired tokens when ThreadFS Core returns `401`.

## Environment Variables

On the host website backend:

```env
THREADFS_SECRET=tfssec_your_secret
THREADFS_ISSUER=example-site
```

`THREADFS_SECRET` must only exist on the server. Never expose it in frontend code.

The public `communityKey` is safe to expose in frontend code, but the signing secret is not.

## Next.js Route Example

Example App Router route:

```ts
// app/api/threadfs-token/route.ts

import { createThreadFSToken } from "@threadfs/server";
import { NextResponse } from "next/server";

export async function GET() {
  const user = await getCurrentUser();

  if (!user) {
    return NextResponse.json({ token: null });
  }

  const token = await createThreadFSToken({
    secret: process.env.THREADFS_SECRET!,
    issuer: process.env.THREADFS_ISSUER ?? "example-site",
    subject: String(user.id),
    username: user.username,
    avatarUrl: user.avatarUrl,
    expiresInSeconds: 15 * 60,
  });

  return NextResponse.json({ token });
}
```

## Security Notes

- Only run this package on the server.
- Never expose `THREADFS_SECRET` to the browser.
- Use short-lived tokens.
- Use HTTPS in production.
- Use stable user IDs for `subject`.
- Make sure the token issuer matches the community auth provider configured in ThreadFS Core.
- Rotate secrets if they are leaked.

## ThreadFS Core Setup

The ThreadFS Core deployment must have a community auth provider configured with the same issuer and secret.

Example setup command:

```bash
python -m app.scripts.setup_community \
  --owner-email admin@example.com \
  --name "Example Site" \
  --slug example-site \
  --description "Example Site comments" \
  --origin https://example.com \
  --origin https://www.example.com \
  --issuer example-site
```

The setup script prints:

```text
Community key: tfspub_...
THREADFS_SECRET=tfssec_...
```

Use:

```text
Community key -> frontend ThreadFSComments communityKey
THREADFS_SECRET -> host backend only
```

## Local Development

Build:

```bash
npm run build
```

Pack:

```bash
npm pack
```

Use the generated tarball in a host app:

```json
{
  "dependencies": {
    "@threadfs/server": "file:../../../thread-fs/integration/backend/nodejs/threadfs-server-0.1.0.tgz"
  }
}
```

## Docker Notes for Host Apps

If the host app depends on this package as a local tarball, Docker must build from a context that includes the tarball.

Example:

```text
workspace/
  aniworks/
    frontend/
      visitor/
  thread-fs/
    integration/
      backend/
        nodejs/
          threadfs-server-0.1.0.tgz
```

Build from `workspace/`:

```bash
docker build \
  -f aniworks/frontend/visitor/Dockerfile \
  -t aniworks-visitor:latest \
  .
```

If the tarball changes, regenerate the host app lockfile before running `npm ci`:

```bash
rm -f package-lock.json
rm -rf node_modules
npm install
```

## Roadmap

- Stable token API
- RS256 support
- Secret rotation helpers
- Better framework examples
- Published npm package
- More validation utilities
