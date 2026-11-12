import {
  ArrowBigDown,
  ArrowBigUp,
  CircleMinus,
  CirclePlus,
  CornerDownRight,
  Reply,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent,
  type PointerEvent,
} from "react";
import type { CommentRemoval } from "../../lib/moderationApi";
import type {
  ThreadFSComment,
  ThreadFSCommentUser,
  ThreadFSReason,
  ThreadFSGif,
} from "../../lib/types";
import { cn } from "../../lib/utils";
import defaultAvatarUrl from "../assets/default-avatar.png";
import { CommentGif } from "./CommentGif";
import { CollapsibleContent } from "../common/CollapsibleContent";
import { MarkdownContent } from "../common/MarkdownContent";
import CommentEditor from "../editor/CommentEditor";
import { OTHER_REASON } from "../moderation/shared";
import { Badge } from "../ui/badge";
import AvatarFrame from "./AvatarFrame";
import CommentActionsMenu from "./CommentActionsMenu";
import CommentShareMenu from "./CommentShareMenu";
import CommentTimestamp from "./CommentTimestamp";
import RemoveCommentForm from "./RemoveCommentForm";
import ReportDetailsForm from "./ReportDetailsForm";
import ThreadConnector from "./ThreadConnector";

// Every level of indent costs a phone reading width, so deeper replies line up and say who they answer
const MAX_PHONE_INDENT = 4;

// "N more replies": muted, as Reddit's, so it reads as part of the thread rather than an action competing with it
const MORE_REPLIES_CLASS =
  "text-muted-foreground hover:text-foreground flex items-center text-xs font-medium hover:cursor-pointer hover:underline disabled:opacity-60";

// What a click on a comment is meant for, rather than hiding it
const COMMENT_CONTROLS =
  "a, button, input, textarea, label, form, [role=button], [contenteditable=true], [data-no-collapse]";

// Muted, and the text colour on hover, like "N more replies": the thread's own controls look alike
const COLLAPSE_BUTTON_CLASS =
  "text-muted-foreground hover:text-foreground flex items-center justify-center hover:cursor-pointer";

type CommentCardProps = {
  comment: ThreadFSComment;
  currentCommunityUserId?: string | null;
  currentUser?: ThreadFSCommentUser | null;
  depth?: number;
  /** Who this replies to, shown where the indent no longer says so. */
  parentName?: string;
  canReply: boolean;
  isLocked?: boolean;
  onReply: (
    parentId: string,
    body: string,
    gif: ThreadFSGif | null,
  ) => Promise<void> | void;
  onVote?: (commentId: string, value: 1 | -1) => Promise<void> | void;
  onEdit?: (
    commentId: string,
    body: string,
    gif: ThreadFSGif | null,
  ) => Promise<void> | void;
  onDelete?: (commentId: string) => Promise<void> | void;
  /** Resolves to whether the report went through. */
  onReport?: (
    commentId: string,
    reason: string,
    details?: string,
  ) => Promise<boolean>;
  reportReasons?: ThreadFSReason[];
  /** Only passed for moderators. */
  onRemove?: (commentId: string, removal: CommentRemoval) => Promise<void>;
  onLoadReplies?: (parentId: string) => Promise<void> | void;
  onLoadMoreReplies?: (parentId: string) => Promise<void> | void;
  onAuthRequired?: () => void;
  authorProfileUrl?: (user: ThreadFSCommentUser) => string | null;
  /** The comment a link points at: highlighted, and scrolled to when it appears. */
  highlightedCommentId?: string | null;
  /** A link to a comment, for its Share button. */
  commentUrl?: (commentId: string) => string | null;
  /** Opens a comment as the root of its own view, where a thread deeper than `continueDepth` continues. */
  onContinueThread?: (commentId: string) => void;
  /** The depth at which replies continue in their own view instead of nesting (lib/threadDepth.ts). */
  continueDepth?: number;

  /**
   * Internal: parent comment uses this to measure child reply avatars.
   * Public callers should not pass this.
   */
  avatarRef?: (node: HTMLImageElement | null) => void;
};

function CommentCard({
  comment,
  currentCommunityUserId = null,
  currentUser = null,
  depth = 0,
  parentName,
  canReply,
  isLocked = false,
  onReply,
  onVote,
  onEdit,
  onDelete,
  onReport,
  reportReasons = [],
  onRemove,
  onLoadReplies,
  onLoadMoreReplies,
  onAuthRequired,
  authorProfileUrl,
  highlightedCommentId = null,
  commentUrl,
  onContinueThread,
  continueDepth,
  avatarRef,
}: CommentCardProps) {
  const viewerVote = comment.viewer_vote ?? null;
  const [isReplying, setIsReplying] = useState(false);
  // Replies that came with the comment (a link's context) start open; otherwise they load on View more
  const [areRepliesExpanded, setAreRepliesExpanded] = useState(
    () => (comment.replies?.length ?? 0) > 0,
  );
  const [isLoadingReplies, setIsLoadingReplies] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isReported, setIsReported] = useState(false);
  const [isDescribingReport, setIsDescribingReport] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isRailHovered, setIsRailHovered] = useState(false);
  const reportFormRef = useRef<HTMLDivElement>(null);
  const [isRemoving, setIsRemoving] = useState(false);

  const isDeleted = comment.status === "deleted";
  const isHidden = comment.status === "hidden";
  const authorUrl = comment.community_user
    ? authorProfileUrl?.(comment.community_user)
    : null;

  const {
    measureVersion,
    containerRef,
    parentAvatarRef,
    repliesButtonRef,
    replyAvatarRefs,
    setContainerRef,
    setParentAvatarRef,
    setRepliesButtonRef,
    getReplyAvatarRef,
  } = useConnectorRefs(avatarRef);

  const isHighlighted =
    highlightedCommentId != null &&
    String(comment.id) === String(highlightedCommentId);

  // Brought into view once, when the linked comment appears
  useEffect(() => {
    if (isHighlighted)
      containerRef.current?.scrollIntoView({ block: "center" });
    // Only on becoming highlighted, not on every re-render
  }, [isHighlighted]);

  const link = commentUrl?.(String(comment.id)) ?? null;

  const isOwnComment =
    currentCommunityUserId != null &&
    comment.community_user_id === currentCommunityUserId;

  const displayName = getDisplayName(comment);
  const avatarUrl = getAvatarUrl(comment);

  // The server leaves a removed comment's text out for everyone but its author
  const isRemovedForViewer = isHidden && !isOwnComment;
  const removalReason = comment.removal_detail ?? comment.removal_reason;

  const hasReplies = comment.reply_count > 0;
  const loadedReplies = comment.replies ?? [];
  const hasLoadedReplies = loadedReplies.length > 0;

  // Before any are open, every reply below counts (reply_count), like Reddit's; after, the direct replies still to load
  const showMoreReplies =
    hasReplies && (!areRepliesExpanded || Boolean(comment.replies_has_more));
  const moreRepliesCount = !areRepliesExpanded
    ? comment.reply_count
    : comment.replies_total != null
      ? comment.replies_total - loadedReplies.length
      : null;
  const isLoadingMoreReplies = areRepliesExpanded
    ? Boolean(comment.replies_is_loading_more)
    : isLoadingReplies;

  // Past a certain depth the replies continue in their own view (Reddit's "Continue this thread"), from their own button
  const continuesElsewhere =
    continueDepth != null &&
    depth >= continueDepth &&
    hasReplies &&
    Boolean(onContinueThread);

  async function handleViewReplies() {
    if (!hasReplies) return;

    if (!hasLoadedReplies && onLoadReplies) {
      try {
        setIsLoadingReplies(true);
        await onLoadReplies(comment.id);
      } finally {
        setIsLoadingReplies(false);
      }
    }

    setAreRepliesExpanded(true);
  }

  function handleReplyClick() {
    if (!canReply) {
      onAuthRequired?.();
      return;
    }

    setIsReplying((value) => !value);
  }

  async function handleReport(reason: string, details?: string) {
    if (await onReport?.(comment.id, reason, details)) {
      setIsReported(true);
      setIsDescribingReport(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this comment? This cannot be undone.")) return;

    try {
      setIsDeleting(true);
      await onDelete?.(comment.id);
    } finally {
      setIsDeleting(false);
    }
  }

  function collapse() {
    setIsCollapsed(true);
    // What was hovered is about to disappear, so it won't report the mouse leaving
    setIsRailHovered(false);
  }

  // A real mouse only: a tap would leave them lit, with nothing to end the hover
  const railHoverProps = {
    onPointerEnter: (event: PointerEvent) => {
      if (event.pointerType === "mouse") setIsRailHovered(true);
    },
    onPointerLeave: () => setIsRailHovered(false),
  };

  // On the thread line, which only a comment with replies has
  const collapseButton = hasReplies && (
    <button
      type="button"
      onClick={collapse}
      {...railHoverProps}
      aria-expanded
      aria-label="Collapse comment"
      title="Collapse comment"
      className={cn(
        COLLAPSE_BUTTON_CLASS,
        "absolute top-1/2 -left-11 z-30 h-6 w-8 -translate-y-1/2",
        isRailHovered && "text-foreground",
      )}
    >
      <CircleMinus
        strokeWidth={1.5}
        className="bg-background size-4 rounded-full"
      />
    </button>
  );

  // Clicking the comment itself hides it, or brings it back, as long as the click wasn't meant for something in it
  function handleCommentClick(event: MouseEvent<HTMLDivElement>) {
    const { target, currentTarget } = event;

    // A menu's clicks reach here through React, though it's rendered elsewhere on the page
    if (!(target instanceof Element) || !currentTarget.contains(target)) return;
    if (target.closest(COMMENT_CONTROLS)) return;
    if (window.getSelection()?.toString()) return;

    setIsCollapsed((value) => !value);
  }

  return (
    <article ref={setContainerRef} className="threadfs-comment relative py-1">
      <ThreadConnector
        containerRef={containerRef}
        parentAvatarRef={parentAvatarRef}
        repliesButtonRef={repliesButtonRef}
        replyAvatarRefs={replyAvatarRefs}
        replies={continuesElsewhere ? [] : loadedReplies}
        hasReplies={hasReplies && !isCollapsed}
        areRepliesExpanded={areRepliesExpanded && !continuesElsewhere}
        measureVersion={measureVersion}
        onRailClick={collapse}
        isHighlighted={isRailHovered}
        hoverProps={railHoverProps}
      />

      {/* No z-index of its own, so the collapse button on the thread line can sit above the line's click area */}
      <div className="relative flex gap-3">
        {isHighlighted && (
          // From the avatar's middle to the column's edge, like Reddit's; behind the comment rather than padding it, so the
          // thread lines still meet the avatars
          <div
            aria-hidden
            className="bg-foreground/5 ring-foreground/15 pointer-events-none absolute -inset-y-1 right-0 left-4 rounded-lg ring-1"
          />
        )}
        <div className="relative size-8 shrink-0">
          <img
            ref={setParentAvatarRef}
            src={avatarUrl}
            onError={(e) => {
              e.currentTarget.src = defaultAvatarUrl;
              e.currentTarget.onerror = null;
            }}
            alt={`${displayName}'s avatar`}
            // Kept in place when collapsed: the parent's connector lands on it
            className={cn(
              "border-muted size-8 rounded-full border object-cover",
              isCollapsed && "invisible",
            )}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
          {!isCollapsed && (
            <AvatarFrame url={comment.community_user?.avatar_frame_url} />
          )}
          {isCollapsed && (
            <button
              type="button"
              onClick={() => setIsCollapsed(false)}
              aria-expanded={false}
              aria-label="Expand comment"
              title="Expand comment"
              className={cn(COLLAPSE_BUTTON_CLASS, "absolute inset-0 z-30")}
            >
              <CirclePlus
                strokeWidth={1.5}
                className="bg-background size-4 rounded-full"
              />
            </button>
          )}
        </div>

        <div
          onClick={handleCommentClick}
          className={cn(
            "min-w-0 flex-1",
            isCollapsed ? "hover:cursor-pointer" : "mb-2",
          )}
        >
          {/* As tall as the avatar, so the name sits level with its middle */}
          <div className="flex min-h-8 min-w-0 flex-col justify-center overflow-hidden">
            <div className="flex flex-wrap items-center gap-2">
              {authorUrl ? (
                <a
                  href={authorUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-tfs-brand-strong dark:text-tfs-brand text-sm font-semibold hover:cursor-pointer hover:underline"
                >
                  {displayName}
                </a>
              ) : (
                <span className="text-tfs-brand-strong dark:text-tfs-brand text-sm font-semibold">
                  {displayName}
                </span>
              )}

              {isOwnComment && <Badge>You</Badge>}
              <CommentTimestamp value={comment.created_at} />
              {comment.edited_at && comment.status === "visible" && (
                <span className="text-muted-foreground text-xs">(edited)</span>
              )}
            </div>

            {parentName && depth > MAX_PHONE_INDENT && !isCollapsed && (
              <p className="text-muted-foreground mt-0.5 flex items-center gap-1 text-xs sm:hidden">
                <CornerDownRight aria-hidden className="size-3 shrink-0" />
                <span className="truncate">Replying to {parentName}</span>
              </p>
            )}
          </div>

          {/* Hidden rather than removed, so open replies and a half-written reply are still there on expanding */}
          <div className={cn(isCollapsed && "hidden")}>
            {isDeleted ? (
              <p className="text-muted-foreground text-sm italic">
                This comment was deleted
              </p>
            ) : isRemovedForViewer ? (
              <p className="text-muted-foreground text-sm italic">[removed]</p>
            ) : isEditing ? (
              <div data-no-collapse className="mt-4">
                <CommentEditor
                  key={`edit-${comment.id}-${comment.modified_at}`}
                  currentUser={currentUser}
                  authorProfileUrl={authorProfileUrl}
                  submitLabel="Save"
                  placeholder="Edit your comment..."
                  startOpen
                  disabled={!canReply}
                  initialMarkdown={comment.content}
                  initialGif={comment.gif ?? null}
                  onSubmit={async (body, gif) => {
                    await onEdit?.(comment.id, body, gif);
                    setIsEditing(false);
                  }}
                  onAuthRequired={onAuthRequired}
                />

                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="text-muted-foreground mt-2 text-sm hover:underline"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <CollapsibleContent
                maxHeight={320}
                className="threadfs-comment-content overflow-wrap-anywhere overflow-hidden text-sm leading-6 wrap-break-word"
              >
                <MarkdownContent markdown={comment.content} />
                {comment.gif && <CommentGif gif={comment.gif} />}
              </CollapsibleContent>
            )}

            {isHidden && isOwnComment && (
              <p className="text-muted-foreground mt-2 text-xs italic">
                Removed by a moderator
                {removalReason ? `: ${removalReason}` : ""}. Only you can see
                this.
              </p>
            )}

            {comment.status === "visible" && (
              <div className="text-muted-foreground relative mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-medium">
                {collapseButton}
                <button
                  type="button"
                  onClick={() => onVote?.(comment.id, 1)}
                  aria-pressed={viewerVote === 1}
                  aria-label={`Upvote (${comment.upvote_count ?? 0})`}
                  className={cn(
                    "hover:text-tfs-brand-strong dark:hover:text-tfs-brand flex items-center gap-1 hover:cursor-pointer",
                    viewerVote === 1 &&
                      "text-tfs-brand-strong dark:text-tfs-brand",
                  )}
                >
                  <ArrowBigUp
                    className={cn("size-4", viewerVote === 1 && "fill-current")}
                  />
                  <span>{comment.upvote_count ?? 0}</span>
                </button>

                <button
                  type="button"
                  onClick={() => onVote?.(comment.id, -1)}
                  aria-pressed={viewerVote === -1}
                  aria-label={`Downvote (${comment.downvote_count ?? 0})`}
                  className={cn(
                    "flex items-center gap-1 hover:cursor-pointer hover:text-rose-500",
                    viewerVote === -1 && "text-rose-500",
                  )}
                >
                  <ArrowBigDown
                    className={cn(
                      "size-4",
                      viewerVote === -1 && "fill-current",
                    )}
                  />
                  <span>{comment.downvote_count ?? 0}</span>
                </button>

                {!isLocked && (
                  <button
                    type="button"
                    onClick={handleReplyClick}
                    className="hover:text-tfs-brand-strong dark:hover:text-tfs-brand flex items-center gap-1 hover:cursor-pointer"
                  >
                    <Reply className="size-4" />
                    Reply
                  </button>
                )}
                {link && (
                  <CommentShareMenu link={link} authorName={displayName} />
                )}
                <CommentActionsMenu
                  isOwnComment={isOwnComment}
                  canReport={canReply}
                  isReported={isReported}
                  reportReasons={reportReasons}
                  isDeleting={isDeleting}
                  onEdit={() => setIsEditing(true)}
                  onDelete={() => void handleDelete()}
                  onReport={
                    onReport &&
                    ((reason) =>
                      reason === OTHER_REASON
                        ? setIsDescribingReport(true)
                        : void handleReport(reason))
                  }
                  onRemove={onRemove && (() => setIsRemoving(true))}
                  onAuthRequired={onAuthRequired}
                  onCloseAutoFocus={(event) => {
                    if (!isDescribingReport) return;
                    event.preventDefault();
                    reportFormRef.current?.querySelector("textarea")?.focus();
                  }}
                />
              </div>
            )}

            {comment.status !== "visible" && hasReplies && (
              <div className="relative mt-3 h-6">{collapseButton}</div>
            )}

            {isDescribingReport && comment.status === "visible" && (
              <div ref={reportFormRef}>
                <ReportDetailsForm
                  onReport={(details) => handleReport(OTHER_REASON, details)}
                  onCancel={() => setIsDescribingReport(false)}
                />
              </div>
            )}

            {isRemoving && onRemove && comment.status === "visible" && (
              <RemoveCommentForm
                authorName={displayName}
                reasons={reportReasons}
                onRemove={(removal) => onRemove(comment.id, removal)}
                onCancel={() => setIsRemoving(false)}
              />
            )}

            {isReplying && (
              <div data-no-collapse className="mt-4">
                <CommentEditor
                  key={`reply-${comment.id}`}
                  currentUser={currentUser}
                  authorProfileUrl={authorProfileUrl}
                  submitLabel="Reply"
                  placeholder={`Reply to ${displayName}...`}
                  startOpen
                  disabled={!canReply}
                  onSubmit={async (body, gif) => {
                    // Adding this reply makes the rest look loaded, with no View more left to fetch them
                    const hadUnloadedReplies = hasReplies && !hasLoadedReplies;

                    await onReply(comment.id, body, gif);
                    setIsReplying(false);
                    if (hadUnloadedReplies) await onLoadReplies?.(comment.id);
                    setAreRepliesExpanded(true);
                  }}
                  onAuthRequired={onAuthRequired}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      <div className={cn(isCollapsed && "hidden")}>
        {areRepliesExpanded && hasLoadedReplies && !continuesElsewhere && (
          <div className="relative mt-2">
            {/* No z-index on this one, so a reply's collapse buttons can sit above this comment's line */}
            {loadedReplies.map((reply) => (
              <div
                key={reply.id}
                className={cn("relative", getReplyIndentClass(depth + 1))}
              >
                <CommentCard
                  comment={reply}
                  avatarRef={getReplyAvatarRef(reply.id)}
                  currentCommunityUserId={currentCommunityUserId}
                  currentUser={currentUser}
                  depth={depth + 1}
                  parentName={displayName}
                  canReply={canReply}
                  isLocked={isLocked}
                  onReply={onReply}
                  onVote={onVote}
                  onEdit={onEdit}
                  onDelete={onDelete}
                  onReport={onReport}
                  reportReasons={reportReasons}
                  onRemove={onRemove}
                  onLoadReplies={onLoadReplies}
                  onLoadMoreReplies={onLoadMoreReplies}
                  onAuthRequired={onAuthRequired}
                  authorProfileUrl={authorProfileUrl}
                  highlightedCommentId={highlightedCommentId}
                  commentUrl={commentUrl}
                  onContinueThread={onContinueThread}
                  continueDepth={continueDepth}
                />
              </div>
            ))}
          </div>
        )}

        {/* Reddit's "+ N more replies": where the next reply would be, on its own branch of the thread line, for replies
            not loaded yet as well as the rest of a page */}
        {/* Too deep to nest here: the same "N more replies", but it opens them in their own view */}
        {continuesElsewhere && (
          <div
            className={cn("relative z-10 mt-1", getReplyIndentClass(depth + 1))}
          >
            <button
              ref={setRepliesButtonRef}
              type="button"
              onClick={() => onContinueThread?.(comment.id)}
              className={MORE_REPLIES_CLASS}
            >
              <span className="mr-1.5 flex h-8 w-4 shrink-0 items-center">
                <CirclePlus
                  data-connector-anchor
                  strokeWidth={1.5}
                  className="bg-background size-4 rounded-full"
                />
              </span>
              <span>{moreRepliesLabel(comment.reply_count)}</span>
            </button>
          </div>
        )}

        {showMoreReplies && !continuesElsewhere && (
          <div
            className={cn("relative z-10 mt-1", getReplyIndentClass(depth + 1))}
          >
            <button
              ref={setRepliesButtonRef}
              type="button"
              onClick={() =>
                void (areRepliesExpanded
                  ? onLoadMoreReplies?.(comment.id)
                  : handleViewReplies())
              }
              disabled={isLoadingMoreReplies}
              className={MORE_REPLIES_CLASS}
            >
              {/* As wide as an avatar, so the circle sits where a reply's avatar would; the thread line meets it */}
              <span className="mr-1.5 flex h-8 w-4 shrink-0 items-center">
                <CirclePlus
                  data-connector-anchor
                  strokeWidth={1.5}
                  className="bg-background size-4 rounded-full"
                />
              </span>
              <span>
                {isLoadingMoreReplies
                  ? "Loading replies..."
                  : moreRepliesLabel(moreRepliesCount)}
              </span>
            </button>
          </div>
        )}
      </div>
    </article>
  );
}

export default CommentCard;

function useConnectorRefs(
  externalAvatarRef?: (node: HTMLImageElement | null) => void,
) {
  const [measureVersion, setMeasureVersion] = useState(0);

  const containerRef = useRef<HTMLElement | null>(null);
  const parentAvatarRef = useRef<HTMLImageElement | null>(null);
  const repliesButtonRef = useRef<HTMLButtonElement | null>(null);
  const replyAvatarRefs = useRef<Map<string, HTMLImageElement>>(new Map());
  const replyAvatarCallbackRefs = useRef<
    Map<string, (node: HTMLImageElement | null) => void>
  >(new Map());

  const frameRef = useRef<number | null>(null);

  const bumpMeasureVersion = useCallback(() => {
    if (frameRef.current != null) {
      window.cancelAnimationFrame(frameRef.current);
    }

    frameRef.current = window.requestAnimationFrame(() => {
      frameRef.current = null;
      setMeasureVersion((version) => version + 1);
    });
  }, []);

  useEffect(() => {
    return () => {
      if (frameRef.current != null) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, []);

  const setContainerRef = useCallback(
    (node: HTMLElement | null) => {
      if (containerRef.current === node) return;

      containerRef.current = node;

      if (node) {
        bumpMeasureVersion();
      }
    },
    [bumpMeasureVersion],
  );

  const setParentAvatarRef = useCallback(
    (node: HTMLImageElement | null) => {
      if (parentAvatarRef.current === node) return;

      parentAvatarRef.current = node;
      externalAvatarRef?.(node);

      if (node) {
        bumpMeasureVersion();
      }
    },
    [externalAvatarRef, bumpMeasureVersion],
  );

  const setRepliesButtonRef = useCallback(
    (node: HTMLButtonElement | null) => {
      if (repliesButtonRef.current === node) return;

      repliesButtonRef.current = node;

      if (node) {
        bumpMeasureVersion();
      }
    },
    [bumpMeasureVersion],
  );

  const getReplyAvatarRef = useCallback(
    (commentId: string) => {
      const existing = replyAvatarCallbackRefs.current.get(commentId);

      if (existing) return existing;

      const callback = (node: HTMLImageElement | null) => {
        const previous = replyAvatarRefs.current.get(commentId) ?? null;

        if (previous === node) return;

        if (node) {
          replyAvatarRefs.current.set(commentId, node);
          bumpMeasureVersion();
        } else {
          replyAvatarRefs.current.delete(commentId);
        }
      };

      replyAvatarCallbackRefs.current.set(commentId, callback);
      return callback;
    },
    [bumpMeasureVersion],
  );

  return {
    measureVersion,
    containerRef,
    parentAvatarRef,
    repliesButtonRef,
    replyAvatarRefs,
    setContainerRef,
    setParentAvatarRef,
    setRepliesButtonRef,
    getReplyAvatarRef,
  };
}

// "6 more replies", or "More replies" when the count isn't known
function moreRepliesLabel(count: number | null): string {
  if (count == null || count < 1) return "More replies";
  return `${count} more ${count === 1 ? "reply" : "replies"}`;
}

function getDisplayName(comment: ThreadFSComment): string {
  if (comment.status === "hidden" && !comment.community_user) {
    return "[removed]";
  }

  return comment.community_user?.display_name?.trim() || "Anonymous";
}

function getAvatarUrl(comment: ThreadFSComment): string {
  return comment.community_user?.avatar_url || defaultAvatarUrl;
}

// The same step at every level and width, so every branch of the thread line has the same short curve: half an avatar
// to the line, then the curve and a short straight part (ThreadConnector). Narrow widgets nest fewer levels instead
// (lib/threadDepth.ts), rather than squeezing them.
function getReplyIndentClass(depth: number): string {
  if (depth <= 0) return "ml-0";
  return depth <= MAX_PHONE_INDENT ? "ml-8" : "ml-0 sm:ml-8";
}
