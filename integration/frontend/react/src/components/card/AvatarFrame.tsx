import { useState } from "react";

/**
 * A decoration drawn over an avatar, larger than it, as hosts' frames are made: the avatar fills the middle 72% or so.
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
      className="pointer-events-none absolute top-1/2 left-1/2 size-[140%] max-w-none -translate-x-1/2 -translate-y-1/2"
    />
  );
}
