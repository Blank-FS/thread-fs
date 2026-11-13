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
- A comment box laid out like Reddit's: GIF and **Aa** under the text, where **Aa** opens the formatting bar on top
  (one row, scrolling sideways when narrow), which ends with the switch to markdown. Once opened, the box stays open
  until **Cancel** or posting; Cancel asks before discarding anything written
- A **Rules** button in every comment box, linking to the community's rules page, which its admins set in the
  moderation panel (Admin › Comment rules). It's the same wherever the community's comments appear; without one, the
  button shows a short default line
- Images in comment text only from the community's image hosts; from anywhere else they show as links, so a comment
  can't load a tracking pixel (core README › Images in comments)
- GIFs from KLIPY, where the community has them on (core README › GIFs): the GIF button opens a search in a popover,
  and a comment can be just a GIF
- An image by link, where the community has image hosts: the image button beside GIF takes a link to an image on one
  of them and previews it. One GIF or one image a comment: once either is attached, both buttons wait until it's
  removed
- Enter starts a new line; Ctrl+Enter (⌘+Enter on a Mac) posts, as on GitHub and Reddit
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

  getAuthToken?: () => Promise<string | null>;

  title?: string;
  className?: string;
  pageSize?: number;
  replyPreview?: number;

  onAuthRequired?: () => void;
  authorProfileUrl?: (user: ThreadFSCommentUser) => string | null;

  focusCommentId?: string | null;
  commentUrl?: (commentId: string) => string | null;
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

For local development, demos, or tests, it can return a fixed token.

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

### `replyPreview`

How many replies show under each top-level comment before **N more replies**. Left out, the community's own setting
applies, which its admins choose in the Admin panel (0 for a new community). `0` hides them all until asked for, which
suits threads that are mostly one-off comments. `1` shows the best reply under each, and more give
a fuller conversation, up to `5`. The best is the highest scored, then the first posted. Opening the rest loads them in
their usual order, without repeating the ones already shown.

### Links to a comment: `focusCommentId`, `commentUrl`

A link to one comment is the page's address with a `#c-<id>` hash, the id in hexadecimal to keep it short (`#c-34` for
comment 52; not a secret, since ids are in every API response). Use a hash rather than a query string: it
never reaches your server, so caching, canonical URLs and crawler rules all see the same page. `commentHash(id)` and
`commentIdFromHash(location.hash)` build and read it.

- `focusCommentId` shows that comment in context, like Reddit: the chain from its top-level comment down to it is pinned
  above the rest of the list, the comment highlighted and scrolled into view with its first replies. Siblings along
  the chain aren't loaded, but their parents offer them ("N more replies"). A comment that's gone leaves the list
  as usual, with a short notice.
- `commentUrl` turns on a **Share** button on every comment: **Copy link**, plus **Share via...** (the device's share
  sheet) on touch devices. Return `null` for no link.

```tsx
import { commentHash, commentIdFromHash } from "@threadfs/react";

<ThreadFSComments
  {...props}
  focusCommentId={commentIdFromHash(location.hash)}
  commentUrl={(id) => `${location.origin}${location.pathname}${commentHash(id)}`}
/>
```

Deep threads stop nesting, as Reddit's do: past a certain level a comment's replies show as **N more replies**, which
opens the comment as the root of its own view, with **Back to the discussion**. Replies nest only while the deepest one
still has about 280px for its text, measured on the widget rather than the screen: three levels on most phones, more as
the widget widens, up to eight. A link to a comment deeper than that opens in this view too, with two parent comments
above it.

`ThreadFSMyComments` and the moderation views link each comment straight to its place: they add `#c-<id>` to
the thread's page (`threadUrl`, else the thread's stored `source_url`), so a host only says where a thread lives.
My Comments opens them in the same tab, like a profile's comments on Reddit, so Back returns to the list; the
moderation views open a new tab, so the queue stays as it was. `linkToComment(url, id)` does the same for links of
your own.

Keep `focusCommentId` in step with the hash (listen for `hashchange`) if links can be followed without a page load.
If the widget runs in an iframe on another origin, give it `allow="clipboard-write"`, or Copy link can't write to the
clipboard (it says so instead).

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

### Accent colour

The accent colour (usernames, links, upvotes, headings) defaults to cyan. Override it with CSS variables in the host app:

```css
:root {
  --threadfs-brand: oklch(91.7% 0.08 205.041); /* accents in dark mode */
  --threadfs-brand-strong: oklch(71.5% 0.143 215.221); /* accents in light mode */
}
```

They can point at the host's own theme variables (e.g. `--threadfs-brand: var(--brand);`) so the widget follows a theme switcher.

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

## Styles

Every rule in the stylesheet applies only inside `.threadfs-root` (`postcss-scope.mjs`), so it can't change the rest of your page, even if your site uses Tailwind too. A new component that renders outside the widget, such as a popup in a portal, needs that class on its own root.

## Moderation

Comments get a Report action, and a comment moderators removed shows as `[removed]`, except to its author. Pass `source` and `client` to `ThreadFSComments` to record where comments come from.

A viewer whose `getAuthToken` token carries a `threadfs_role` claim gets a Remove action on comments, so moderators can act where they read. Only sign that claim for your own staff, and stop signing it when their role ends.

ThreadFS records the role from each token, so a token without one reads as the user losing it, along with their protection from bans and their place on the staff list. Where you issue tokens without vouching for the user's role, for example in an embed on other sites, sign `"threadfs_role_unknown": true` instead. The token then acts with no role, and the recorded one is kept.

`ThreadFSModeration` is the moderators' screen: the report queue, removed comments, comment search, batch cleanup, users with their history and private notes, bans, and the action log.

```tsx
<ThreadFSModeration
  apiBaseUrl="https://threadfs.example.com"
  communityKey="tfspub_..."
  getAuthToken={fetchModeratorToken}
/>
```

The token must carry a `threadfs_role` claim of `moderator` or `admin`, signed by your server. Mint it only for your own staff, and add the moderation page's origin to the community's allowed origins.

Each community has its own reasons, used for both reporting and removing comments, and the author of a removed comment sees the reason. A community without any uses the defaults: Spam, Harassment or bullying, Hate speech, Threats or violence, Personal information, Sexual content, Off topic and Other. A reason with the key `other` has no meaning of its own: a report with it needs a description of up to 100 characters, and a removal with it needs up to 200 characters telling the author why, starting from what the report said. An `admin` token can edit the list in the widget's settings, or through the API:

```
PUT /api/v1/moderation/reasons
{"reasons": [{"key": "spam", "label": "Spam"}, {"key": "wrong_episode", "label": "Wrong episode or series"}]}
```

Reports and removals keep the label they were made with, so changing the list doesn't rewrite the past.

Moderators can ban regular users. Admins can also ban moderators, and only admins can lift a moderator's ban. Nobody can ban an admin or themselves. A banned moderator loses moderation access until the ban ends. ThreadFS knows staff by the role in their latest token, so someone who's just been given a role is protected from their next visit.

When your site removes a user's avatar or frame, ThreadFS keeps the old URL until that user's next token. To clear it at once, call this with a `moderator` or `admin` token, after removing the image on your side, since the next token sets both again from its claims:

```
POST /api/v1/moderation/users/clear-images
{"external_user_id": "123", "avatar": true, "frame": false}
```

`external_user_id` is the user's `sub`. Each image cleared is a line in the log.

Bulk actions are limited for moderators, by default to 50 comments at once and 200 a day. Clearing out one regular user's comments isn't limited, and admins have no limit. Each batch is one line in the log, where an admin can undo it, which puts back what it changed, including removal reasons.

An `admin` token also gets an Admin panel: staff activity, the moderator limits, the community's reasons, how many replies show under each comment and its allowed origins. Keys and allowed origins are changed from the server, with `setup_community`, never from a browser.
