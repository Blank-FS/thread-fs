# @threadfs/react

React components for embedding ThreadFS comments into a host website.

ThreadFS is an open-source embeddable discussion system similar to Disqus. This package provides the frontend comment component that connects to a deployed ThreadFS Core API.

## Features

- Embeddable React comment section
- Loads comments for a host-defined thread ID
- Supports authenticated posting through host-issued ThreadFS tokens
- Supports replies and nested comment loading
- Supports comment voting
- Supports edit/delete for own comments
- Supports pagination and sorting
- Supports login redirect callbacks
- Supports author profile URL callbacks
- Uses the host website’s styling context where possible

## Installation

This package is not published to npm yet.

For local development, install from a local package tarball or workspace.

### Local tarball

```json
{
  "dependencies": {
    "@threadfs/react": "file:../../../thread-fs/integration/frontend/react/threadfs-react-0.1.0.tgz"
  }
}
```

After making changes to this package, rebuild and repack it:

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

If your app and ThreadFS packages are in the same monorepo, prefer a workspace dependency:

```json
{
  "dependencies": {
    "@threadfs/react": "workspace:*"
  }
}
```

## Basic Usage

```tsx
import { ThreadFSComments } from "@threadfs/react";

export function CommentsSection({ threadId }: { threadId: number }) {
  return (
    <ThreadFSComments
      apiBaseUrl="https://threadfs-api.example.com"
      communityKey="tfspub_your_public_community_key"
      threadId={`thread:${threadId}`}
      getAuthToken={async () => {
        const res = await fetch("/api/threadfs-token", {
          credentials: "include",
        });

        const data = await res.json();
        return data.token ?? null;
      }}
      onAuthRequired={() => {
        window.location.href = `/login?next=${encodeURIComponent(
          window.location.href,
        )}`;
      }}
      authorProfileUrl={(user) =>
        user.external_user_id ? `/users/${user.external_user_id}` : null
      }
    />
  );
}
```

## Props

```ts
type ThreadFSCommentsProps = {
  apiBaseUrl: string;
  communityKey: string;
  threadId: string;

  authToken?: string | null;
  getAuthToken?: () => Promise<string | null>;

  title?: string;
  className?: string;
  pageSize?: number;

  onAuthRequired?: () => void;
  authorProfileUrl?: (user: ThreadFSCommentUser) => string | null;
};
```

### `apiBaseUrl`

The base URL of your deployed ThreadFS Core API.

Example:

```tsx
apiBaseUrl = "https://threadfs-api.example.com";
```

### `communityKey`

The public key for the ThreadFS community.

Example:

```tsx
communityKey = "tfspub_abc123";
```

This key is public and safe to expose in frontend code. It identifies the community but does not authenticate users.

### `threadId`

The host website’s stable ID for the current discussion thread.

Examples:

```tsx
threadId="blog:hello-world"
threadId={`discussion:${discussion.id}`}
threadId={`post:${post.id}`}
```

ThreadFS Core creates the internal thread lazily when the first authenticated comment is posted.

### `getAuthToken`

A function that asks the host website backend for a short-lived ThreadFS user token.

The token should be issued by the host backend using `@threadfs/server`.

```tsx
getAuthToken={async () => {
  const res = await fetch("/api/threadfs-token", {
    credentials: "include",
  });

  const data = await res.json();
  return data.token ?? null;
}}
```

Use this instead of hardcoding an `authToken`.

### `authToken`

A direct token value. Useful for local development, demos, or tests.

For production, prefer `getAuthToken`.

### `onAuthRequired`

Called when the user attempts an authenticated action while logged out.

Example:

```tsx
onAuthRequired={() => {
  window.location.href = `/login?next=${encodeURIComponent(
    window.location.href,
  )}`;
}}
```

### `authorProfileUrl`

Maps a ThreadFS comment author to a host website profile URL.

```tsx
authorProfileUrl={(user) =>
  user.external_user_id ? `/users/${user.external_user_id}` : null
}
```

Return `null` if the author should not be linked.

## Authentication Flow

ThreadFS does not own the host website’s user sessions.

Instead:

1. The host website authenticates users normally.
2. The host backend issues a short-lived ThreadFS JWT.
3. The React component sends that token to ThreadFS Core.
4. ThreadFS Core verifies the token and maps it to a `CommunityUser`.

Recommended flow:

```text
Host frontend
  -> getAuthToken()
  -> Host backend /api/threadfs-token
  -> @threadfs/server signs token
  -> ThreadFS React uses token for write actions
  -> ThreadFS Core verifies token
```

## API Requirements

The deployed ThreadFS Core API must allow the host website origin through both:

1. CORS configuration
2. Community allowed-origin configuration

Example allowed origins:

```text
https://example.com
https://www.example.com
http://localhost:3000
```

## Styling

The component is designed to be embedded inside host websites and should inherit much of the surrounding theme.

If your app uses Tailwind, make sure the package styles are included in your build setup if needed.

Exact styling/theming APIs are still evolving.

## Local Development

Build the package:

```bash
npm run build
```

Create a local tarball:

```bash
npm pack
```

Use the generated `.tgz` in a host app:

```json
{
  "dependencies": {
    "@threadfs/react": "file:../../../thread-fs/integration/frontend/react/threadfs-react-0.1.0.tgz"
  }
}
```

## Docker Notes for Host Apps

If a host app depends on the local tarball, Docker must build from a context that includes both the host app and the ThreadFS tarball.

Example structure:

```text
workspace/
  aniworks/
    frontend/
      visitor/
  thread-fs/
    integration/
      frontend/
        react/
          threadfs-react-0.1.0.tgz
```

Build from `workspace/`, not from the host app folder alone:

```bash
docker build \
  -f aniworks/frontend/visitor/Dockerfile \
  -t aniworks-visitor:latest \
  .
```

## Roadmap

- Better theming API
- Stable public TypeScript types
- More customization hooks
- Better loading/error states
- Published npm package
- Storybook/demo site
- Stronger accessibility pass
