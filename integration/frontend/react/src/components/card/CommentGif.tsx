import type { ThreadFSGif } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ImageOff } from "lucide-react";
import { useState } from "react";

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
  const [failed, setFailed] = useState(false);
  const scale = Math.min(1, MAX_HEIGHT / gif.height);

  if (failed) return <MediaFailed kind="GIF" url={gif.url} />;

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
      onError={() => setFailed(true)}
      className={cn("bg-muted my-1 h-auto max-w-full rounded-lg", className)}
      style={{ aspectRatio: `${gif.width} / ${gif.height}` }}
    />
  );
}

/**
 * In place of a GIF or image that didn't load: its host deleted it, is down, or is blocked where the reader is (Imgur
 * in the UK). Says so, with a link to try it directly, rather than leaving an empty box.
 */
export function MediaFailed({ kind, url }: { kind: string; url: string }) {
  return (
    <span className="text-muted-foreground my-1 flex w-fit items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs">
      <ImageOff className="size-3.5 shrink-0" />
      <span>{kind} couldn&apos;t load</span>
      <a
        href={url}
        target="_blank"
        rel="noreferrer noopener nofollow ugc"
        className="hover:text-foreground underline"
      >
        Open it
      </a>
    </span>
  );
}
