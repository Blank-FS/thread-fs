import { useState } from "react";

/**
 * A decoration drawn over an avatar at 1.2 times its size, the scale such frames are usually made for: the avatar
 * fills the middle five sixths, so the frame's ring meets its edge.
 * Its parent needs to be positioned and the avatar's size. Purely decorative, and gone if it fails to load.
 */
export default function AvatarFrame({ url }: { url?: string | null }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  if (!url || failedUrl === url) return null;

  return (
    <img
      src={url}
      alt=""
      aria-hidden
      loading="lazy"
      decoding="async"
      onError={() => setFailedUrl(url)}
      className="pointer-events-none absolute top-1/2 left-1/2 size-[120%] max-w-none -translate-x-1/2 -translate-y-1/2"
    />
  );
}
