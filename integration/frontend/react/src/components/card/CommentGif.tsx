import type { ThreadFSGif } from "@/lib/types";
import { cn } from "@/lib/utils";

// Tall enough to read, short enough that a GIF reply doesn't take over a thread
const MAX_HEIGHT = 200;

/**
 * A comment's GIF, under its text, from the provider's URL as it was given. Its size is known before it loads, so the
 * thread doesn't jump.
 */
export function CommentGif({
  gif,
  className,
}: {
  gif: ThreadFSGif;
  className?: string;
}) {
  const scale = Math.min(1, MAX_HEIGHT / gif.height);

  return (
    <img
      src={gif.url}
      alt={gif.title || "GIF"}
      title={gif.title || undefined}
      width={Math.round(gif.width * scale)}
      height={Math.round(gif.height * scale)}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      className={cn("bg-muted my-1 h-auto max-w-full rounded-lg", className)}
      style={{ aspectRatio: `${gif.width} / ${gif.height}` }}
    />
  );
}

/** For one-line previews (the moderation lists), where a GIF is named rather than shown. */
export function GifLabel() {
  return (
    <span className="text-muted-foreground border-border rounded border px-1 text-[10px] font-semibold tracking-wide">
      GIF
    </span>
  );
}
