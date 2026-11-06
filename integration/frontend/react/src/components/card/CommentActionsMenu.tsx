import {
  ChevronLeft,
  Flag,
  MoreHorizontal,
  Pencil,
  ShieldX,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ThreadFSReason } from "../../lib/types";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

/** A comment's less common actions. Renders nothing when the viewer has none. */
export default function CommentActionsMenu({
  isOwnComment,
  canReport,
  isReported,
  reportReasons,
  isDeleting,
  onEdit,
  onDelete,
  onReport,
  onRemove,
  onAuthRequired,
  onCloseAutoFocus,
}: {
  isOwnComment: boolean;
  /** Whether the viewer is signed in, and so can pick a reason. */
  canReport: boolean;
  isReported: boolean;
  reportReasons: ThreadFSReason[];
  isDeleting: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onReport?: (reason: string) => void;
  /** Only passed for moderators. */
  onRemove?: () => void;
  onAuthRequired?: () => void;
  /** Lets an action that opens a form keep focus, instead of it returning to the menu's button. */
  onCloseAutoFocus?: (event: Event) => void;
}) {
  // The reasons replace the menu rather than open beside it: a narrow panel has no room for a second one
  const [isChoosingReason, setIsChoosingReason] = useState(false);
  const itemsRef = useRef<HTMLDivElement>(null);

  // Swapping the items removes the focused one, which would leave the keyboard stranded
  useEffect(() => {
    if (isChoosingReason)
      itemsRef.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus();
  }, [isChoosingReason]);

  const showReport =
    !isOwnComment && Boolean(onReport) && reportReasons.length > 0;
  const showRemove = !isOwnComment && Boolean(onRemove);

  if (!isOwnComment && !showReport && !showRemove) return null;

  return (
    <DropdownMenu
      onOpenChange={(isOpen) => {
        if (!isOpen) setIsChoosingReason(false);
      }}
    >
      <DropdownMenuTrigger
        aria-label="More actions"
        className="hover:text-tfs-brand -m-1 rounded-full p-1 hover:cursor-pointer"
      >
        <MoreHorizontal className="size-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="w-48"
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <div ref={itemsRef}>
          {isChoosingReason ? (
            <>
              <DropdownMenuItem
                onSelect={(event) => {
                  event.preventDefault();
                  setIsChoosingReason(false);
                }}
              >
                <ChevronLeft /> Back
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {reportReasons.map(({ key, label }) => (
                <DropdownMenuItem key={key} onSelect={() => onReport?.(key)}>
                  {label}
                </DropdownMenuItem>
              ))}
            </>
          ) : (
            <>
              {isOwnComment && (
                <>
                  <DropdownMenuItem onSelect={onEdit}>
                    <Pencil /> Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    variant="destructive"
                    disabled={isDeleting}
                    onSelect={onDelete}
                  >
                    <Trash2 /> {isDeleting ? "Deleting..." : "Delete"}
                  </DropdownMenuItem>
                </>
              )}
              {showReport &&
                (isReported ? (
                  <DropdownMenuItem disabled>
                    <Flag /> Reported
                  </DropdownMenuItem>
                ) : (
                  <DropdownMenuItem
                    onSelect={(event) => {
                      if (!canReport) {
                        onAuthRequired?.();
                        return;
                      }
                      event.preventDefault();
                      setIsChoosingReason(true);
                    }}
                  >
                    <Flag /> Report
                  </DropdownMenuItem>
                ))}
              {showRemove && (
                <DropdownMenuItem variant="destructive" onSelect={onRemove}>
                  <ShieldX /> Remove
                </DropdownMenuItem>
              )}
            </>
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
