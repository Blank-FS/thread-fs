import type { ReactNode } from "react";

// Says a comment was removed, and why, to the few who still see it (its author, staff). In the same red as the edge
// beside its text, since it's the one thing on the card its author most needs to notice.
export default function RemovalNote({
  reason,
  audience,
  children,
}: {
  reason?: string | null;
  /** Who else can see it: "you", "moderators" or "moderators and you". */
  audience: string;
  /** Actions beside it, like staff's Restore. */
  children?: ReactNode;
}) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      <p className="font-medium text-rose-500">
        Removed by a moderator{reason ? `: ${reason}` : ""}
        <span className="text-muted-foreground font-normal italic">
          {" "}
          · Only {audience} can see this
        </span>
      </p>
      {children}
    </div>
  );
}

// The red edge that sets a removed comment's text apart from the live comments around it
export const REMOVED_CONTENT_CLASS =
  "border-l-2 border-rose-500/60 pl-2 opacity-70";
