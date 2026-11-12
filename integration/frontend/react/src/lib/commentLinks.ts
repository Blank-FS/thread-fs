// Links to one comment use the page's address with a #c-<id> hash, the id in hexadecimal to keep it short ("#c-34" for
// comment 52). A hash never reaches the server, so a host site's caching, canonical URLs and
// crawler rules see the same page, and it works on any page that shows the thread. Not a secret: ids are in every API
// response, and hexadecimal is just shorter.

const PREFIX = "#c-";

/** "#c-34" for comment 52. */
export function commentHash(commentId: string | number): string {
  return `${PREFIX}${Number(commentId).toString(16)}`;
}

/** The comment a hash like "#c-34" points at (as a decimal id, "52"), or null. */
export function commentIdFromHash(
  hash: string | null | undefined,
): string | null {
  if (!hash?.startsWith(PREFIX)) return null;
  const encoded = hash.slice(PREFIX.length).toLowerCase();
  if (!/^[0-9a-f]{1,13}$/.test(encoded)) return null;
  const id = parseInt(encoded, 16);
  return Number.isSafeInteger(id) && id > 0 ? String(id) : null;
}

/**
 * A link to a comment on its thread's page: `url` with its hash replaced by #c-<id>. Where the widget lists comments
 * outside their thread (My Comments, moderation), so a click lands on the comment rather than the top.
 */
export function linkToComment(
  url: string | null | undefined,
  commentId: string | number,
): string | null {
  if (!url) return null;
  try {
    const link = new URL(url, window.location.href);
    link.hash = commentHash(commentId);
    return link.toString();
  } catch {
    return url;
  }
}
