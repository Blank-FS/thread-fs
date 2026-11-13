import { isAllowedImage, useImageHosts } from "@/lib/imageHosts";
import type {
  CommentMedia,
  ThreadFSComment,
  ThreadFSGif,
  ThreadFSImage,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { useState } from "react";
import { CommentGif, MediaFailed } from "./CommentGif";

// As tall as a GIF: enough to see, without one image taking over a thread
const MAX_HEIGHT = 200;

/** What a comment has attached, for an editor to start from. */
export function mediaOf(comment: {
  gif?: ThreadFSGif | null;
  image?: ThreadFSImage | null;
}): CommentMedia {
  return { gif: comment.gif ?? null, image: comment.image ?? null };
}

/**
 * An image linked under a comment's text. Shown while its host is still one of the community's image hosts; if admins
 * have since taken it off, it's a link, like any other image from elsewhere (lib/imageHosts.ts).
 */
export function CommentImage({
  image,
  className,
}: {
  image: ThreadFSImage;
  className?: string;
}) {
  const hosts = useImageHosts();
  const [failed, setFailed] = useState(false);

  if (failed) return <MediaFailed kind="Image" url={image.url} />;

  if (!isAllowedImage(image.url, hosts)) {
    return (
      <a
        href={image.url}
        target="_blank"
        rel="noreferrer noopener nofollow ugc"
        className="text-tfs-brand-strong dark:hover:text-tfs-brand my-1 inline-block text-sm underline"
      >
        image
      </a>
    );
  }

  const scale = Math.min(1, MAX_HEIGHT / image.height);
  return (
    <img
      src={image.url}
      // Posters don't describe their images, but this way a screen reader at least says there's one
      alt="Image"
      width={Math.round(image.width * scale)}
      height={Math.round(image.height * scale)}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={cn("bg-muted my-1 h-auto max-w-full rounded-lg", className)}
      style={{ aspectRatio: `${image.width} / ${image.height}` }}
    />
  );
}

/** A comment's GIF or image, under its text. */
export function CommentMediaView({ comment }: { comment: ThreadFSComment }) {
  if (comment.gif) return <CommentGif gif={comment.gif} />;
  if (comment.image) return <CommentImage image={comment.image} />;
  return null;
}

/** For one-line previews (the moderation lists), where a GIF or image is named rather than shown. */
export function MediaLabel({
  comment,
}: {
  comment: { gif?: ThreadFSGif | null; image?: ThreadFSImage | null };
}) {
  if (!comment.gif && !comment.image) return null;
  return (
    <span className="text-muted-foreground border-border rounded border px-1 text-[10px] font-semibold tracking-wide">
      {comment.gif ? "GIF" : "IMAGE"}
    </span>
  );
}
