import {
  ArrowBigDown,
  ArrowBigUp,
  Lock,
  LockOpen,
  MessagesSquare,
  MoreHorizontal,
  UserRound,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { linkToComment } from "../../lib/commentLinks";
import {
  hideComment,
  restoreComment,
  setThreadLocked,
} from "../../lib/moderationApi";
import type { ModerationComment } from "../../lib/types";
import { cn } from "../../lib/utils";
import CommentTimestamp from "../card/CommentTimestamp";
import { CollapsibleContent } from "../common/CollapsibleContent";
import { MarkdownContent } from "../common/MarkdownContent";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Checkbox } from "../ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Input } from "../ui/input";
import {
  banBlockedReason,
  banExpiry,
  BanLengthSelect,
  OTHER_REASON,
  OtherReasonInput,
  ReasonSelect,
  useModeration,
  UserAvatar,
  UserLink,
  userName,
} from "./shared";

/** One comment and everything that can be done to it. It stays in place after an action, so another can follow. */
export function CommentRow({
  comment,
  run,
  onChange,
  isSelected,
  onSelect,
  defaultReasonKey = "",
  defaultReasonDetail = "",
  extraActions,
  children,
}: {
  comment: ModerationComment;
  run: (work: () => Promise<unknown>) => Promise<boolean>;
  /** Applies a change to every comment on the list it may touch. */
  onChange: (update: (item: ModerationComment) => ModerationComment) => void;
  isSelected?: boolean;
  onSelect?: (selected: boolean) => void;
  /** The reason the Remove form starts on. */
  defaultReasonKey?: string;
  /** What the author is told if the reason is Other. */
  defaultReasonDetail?: string;
  extraActions?: ReactNode;
  children?: ReactNode;
}) {
  const {
    request,
    threadUrl,
    openUser,
    showThreadComments,
    syncOpenReports,
    me,
  } = useModeration();
  const [isRemoving, setIsRemoving] = useState(false);
  const [reasonKey, setReasonKey] = useState("");
  const [reasonDetail, setReasonDetail] = useState("");
  const [note, setNote] = useState("");
  const [alsoBan, setAlsoBan] = useState(false);
  const [banDays, setBanDays] = useState("7");
  const [isBusy, setIsBusy] = useState(false);

  const isOther = reasonKey === OTHER_REASON;
  const user = comment.community_user ?? null;
  const canBan = user !== null && !banBlockedReason(me, user);
  const thread = comment.thread ?? null;
  const parent = comment.parent ?? null;
  // Straight to the comment on its thread's page
  const threadHref = linkToComment(
    threadUrl ? threadUrl(comment) : thread?.source_url,
    comment.id,
  );

  async function act(work: () => Promise<unknown>) {
    setIsBusy(true);
    const ok = await run(work);
    setIsBusy(false);
    return ok;
  }

  const replace = (updated: ModerationComment) =>
    onChange((item) => (item.id === updated.id ? updated : item));

  async function remove() {
    const ok = await act(async () => {
      replace(
        await request((ctx) =>
          hideComment(ctx, comment.id, {
            reasonKey: reasonKey || null,
            reasonDetail: isOther ? reasonDetail.trim() : null,
            note: note.trim() || null,
            ban: alsoBan,
            banExpiresAt: alsoBan ? banExpiry(banDays) : null,
          }),
        ),
      );
    });

    if (ok) {
      setIsRemoving(false);
      setNote("");
      setAlsoBan(false);
      syncOpenReports();
    }
  }

  const restore = () =>
    act(async () => {
      replace(await request((ctx) => restoreComment(ctx, comment.id)));
    });

  const toggleLock = () =>
    act(async () => {
      const updated = await request((ctx) =>
        setThreadLocked(ctx, thread!.unique_id, !thread!.is_locked),
      );
      onChange((item) =>
        item.thread?.id === updated.id ? { ...item, thread: updated } : item,
      );
    });

  return (
    <article>
      <Card
        className={cn(
          "flex-row gap-3 p-4 transition-colors",
          isSelected && "ring-tfs-brand-strong dark:ring-tfs-brand ring-2",
          comment.status !== "visible" && "bg-muted/40",
        )}
      >
        {onSelect && (
          <Checkbox
            checked={Boolean(isSelected)}
            onCheckedChange={(checked) => onSelect(checked === true)}
            aria-label={`Select comment by ${userName(user)}`}
            className="mt-2 hover:cursor-pointer"
          />
        )}

        <button
          type="button"
          disabled={!user}
          onClick={() => user && openUser(user)}
          aria-label={`View ${userName(user)}`}
          className="h-fit shrink-0 hover:cursor-pointer disabled:cursor-default"
        >
          <UserAvatar user={user} />
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <UserLink user={user} />
                <CommentTimestamp value={comment.created_at} />
                {comment.status === "hidden" && (
                  <Badge variant="destructive">
                    Removed
                    {comment.removal_reason
                      ? `: ${comment.removal_reason}`
                      : ""}
                  </Badge>
                )}
                {comment.status === "deleted" && (
                  <Badge variant="secondary">Deleted by author</Badge>
                )}
                {thread?.is_locked && <Badge variant="outline">Locked</Badge>}
              </div>

              <div className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs">
                {thread &&
                  (threadHref ? (
                    <a
                      href={threadHref}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="max-w-full truncate hover:underline"
                    >
                      {thread.title || thread.unique_id}
                    </a>
                  ) : (
                    <span className="max-w-full truncate">
                      {thread.title || thread.unique_id}
                    </span>
                  ))}
                {[comment.source, comment.client]
                  .filter(Boolean)
                  .map((value) => (
                    <span
                      key={value}
                      className="before:mr-1.5 before:content-['·']"
                    >
                      {value}
                    </span>
                  ))}
              </div>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  aria-label="More actions"
                  className="-mt-1 -mr-1 hover:cursor-pointer"
                >
                  <MoreHorizontal />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                {user && (
                  <DropdownMenuItem onSelect={() => openUser(user)}>
                    <UserRound /> View user
                  </DropdownMenuItem>
                )}
                {thread && (
                  <DropdownMenuItem onSelect={() => showThreadComments(thread)}>
                    <MessagesSquare /> Comments in this thread
                  </DropdownMenuItem>
                )}
                {thread && (
                  <DropdownMenuItem
                    disabled={isBusy}
                    onSelect={() => void toggleLock()}
                  >
                    {thread.is_locked ? <LockOpen /> : <Lock />}
                    {thread.is_locked ? "Unlock thread" : "Lock thread"}
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {parent && (
            <div className="text-muted-foreground border-tfs-brand-strong/50 dark:border-tfs-brand/40 mt-2 border-l-2 pl-3 text-xs">
              <p className="mb-0.5 font-medium">
                Replying to {userName(parent.community_user)}
              </p>
              {parent.status === "deleted" ? (
                <p className="italic">Deleted by its author</p>
              ) : (
                <div className="line-clamp-2 [&_*]:mb-0 [&_*]:text-xs [&_*]:leading-5">
                  <MarkdownContent markdown={parent.content} />
                </div>
              )}
            </div>
          )}

          {comment.status === "deleted" ? (
            <p className="text-muted-foreground mt-2 text-sm italic">
              The author deleted this comment
            </p>
          ) : (
            <CollapsibleContent
              maxHeight={200}
              className="overflow-wrap-anywhere mt-2 text-sm leading-6 wrap-break-word [&_*:last-child]:mb-0"
            >
              <MarkdownContent markdown={comment.content} />
            </CollapsibleContent>
          )}

          {comment.status === "hidden" && comment.removal && (
            <p className="text-muted-foreground mt-3 flex flex-wrap items-center gap-x-1.5 rounded-lg bg-rose-500/10 px-3 py-2 text-xs">
              <span>Removed by {userName(comment.removal.moderator)}</span>
              <CommentTimestamp value={comment.removal.created_at} />
              {comment.removal.reason && (
                <span className="text-foreground w-full">
                  {comment.removal.reason}
                </span>
              )}
            </p>
          )}

          {children}

          {(comment.status !== "deleted" || extraActions) && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {comment.status === "visible" && (
                <Button
                  type="button"
                  size="sm"
                  variant="destructive"
                  disabled={isBusy}
                  className="hover:cursor-pointer"
                  aria-expanded={isRemoving}
                  onClick={() => {
                    setReasonKey(defaultReasonKey);
                    setReasonDetail(defaultReasonDetail);
                    setIsRemoving((value) => !value);
                  }}
                >
                  Remove
                </Button>
              )}
              {comment.status === "hidden" && (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={isBusy}
                  className="hover:cursor-pointer"
                  onClick={() => void restore()}
                >
                  Restore
                </Button>
              )}
              {extraActions}
              {comment.status !== "deleted" && (
                <div className="text-muted-foreground ml-auto flex items-center gap-3 text-sm">
                  <span
                    aria-label={`${comment.upvote_count} upvotes`}
                    className="flex items-center gap-1"
                  >
                    <ArrowBigUp className="size-4" />
                    {comment.upvote_count}
                  </span>
                  <span
                    aria-label={`${comment.downvote_count} downvotes`}
                    className={cn(
                      "flex items-center gap-1",
                      comment.downvote_count > comment.upvote_count &&
                        "font-medium text-rose-500",
                    )}
                  >
                    <ArrowBigDown className="size-4" />
                    {comment.downvote_count}
                  </span>
                </div>
              )}
            </div>
          )}

          {isRemoving && comment.status === "visible" && (
            <form
              className="bg-muted/50 mt-3 space-y-3 rounded-lg p-3"
              onSubmit={(event) => {
                event.preventDefault();
                void remove();
              }}
            >
              <div className="grid gap-2 @lg:grid-cols-2">
                <ReasonSelect value={reasonKey} onChange={setReasonKey} />
                <Input
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  aria-label="Private note"
                  placeholder="Private note (optional)"
                  maxLength={1000}
                  className="md:text-sm"
                />
              </div>
              {isOther && (
                <OtherReasonInput
                  value={reasonDetail}
                  onChange={setReasonDetail}
                />
              )}
              <div className="flex flex-wrap items-center gap-3">
                {canBan && (
                  <label className="flex items-center gap-2 text-sm hover:cursor-pointer">
                    <Checkbox
                      checked={alsoBan}
                      onCheckedChange={(checked) =>
                        setAlsoBan(checked === true)
                      }
                    />
                    Also ban {userName(user)}
                  </label>
                )}
                {canBan && alsoBan && (
                  <BanLengthSelect
                    value={banDays}
                    onChange={setBanDays}
                    className="w-32"
                  />
                )}
                <Button
                  type="submit"
                  size="sm"
                  variant="destructive"
                  disabled={isBusy || (isOther && !reasonDetail.trim())}
                  className="ml-auto hover:cursor-pointer"
                >
                  {alsoBan ? "Remove and ban" : "Remove comment"}
                </Button>
              </div>
            </form>
          )}
        </div>
      </Card>
    </article>
  );
}
