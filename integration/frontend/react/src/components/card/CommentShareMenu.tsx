import { Link, Share, Share2 } from "lucide-react";
import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

// The device's share sheet, which lists the apps the viewer actually uses. Touch devices only: desktop browsers can
// have one too, but it's clunkier than copying the link.
const canShareNatively = () =>
  typeof navigator !== "undefined" &&
  typeof navigator.share === "function" &&
  window.matchMedia("(pointer: coarse)").matches;

/**
 * A comment's Share button, as on Reddit: Copy link, and "Share via..." on touch devices with a share sheet. No
 * per-app buttons: the share sheet already offers the apps the viewer uses.
 */
export default function CommentShareMenu({
  link,
  authorName,
}: {
  link: string;
  authorName: string;
}) {
  const [status, setStatus] = useState<"copied" | "failed" | null>(null);

  function flash(next: "copied" | "failed") {
    setStatus(next);
    window.setTimeout(() => setStatus(null), 2500);
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(link);
      flash("copied");
    } catch {
      // A frame without clipboard permission, or an older browser
      flash("failed");
    }
  }

  async function shareNatively() {
    try {
      await navigator.share({ title: `Comment by ${authorName}`, url: link });
    } catch (err) {
      // Closing the share sheet rejects too; only a real failure falls back to copying
      if (!(err instanceof DOMException && err.name === "AbortError"))
        await copyLink();
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger className="hover:text-tfs-brand-strong dark:hover:text-tfs-brand flex items-center gap-1 hover:cursor-pointer">
          <Share2 className="size-4" />
          Share
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-44">
          <DropdownMenuItem onSelect={() => void copyLink()}>
            <Link /> Copy link
          </DropdownMenuItem>
          {canShareNatively() && (
            <DropdownMenuItem onSelect={() => void shareNatively()}>
              <Share /> Share via...
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      {status && (
        <span role="status" className="text-muted-foreground">
          {status === "copied" ? "Link copied" : "Couldn't copy the link"}
        </span>
      )}
    </>
  );
}
