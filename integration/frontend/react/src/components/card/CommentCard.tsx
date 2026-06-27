import { ArrowBigDown, ArrowBigUp, ChevronDown, ChevronUp } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ThreadFSComment, ThreadFSCommentUser } from "../../lib/types";
import { cn } from "../../lib/utils";
import defaultAvatarUrl from "../assets/default-avatar.svg";
import { MarkdownContent } from "../common/MarkdownContent";
import CommentEditor from "../editor/CommentEditor";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import CommentTimestamp from "./CommentTimestamp";
import ThreadConnector from "./ThreadConnector";

type CommentCardProps = {
  comment: ThreadFSComment;
  currentCommunityUserId?: string | null;
  currentUser?: ThreadFSCommentUser | null;
  depth?: number;
  canReply: boolean;
  onReply: (parentId: string, body: string) => Promise<void> | void;
  onVote?: (commentId: string, value: 1 | -1) => Promise<void> | void;
  onEdit?: (commentId: string, body: string) => Promise<void> | void;
  onDelete?: (commentId: string) => Promise<void> | void;
  onLoadReplies?: (parentId: string) => Promise<void> | void;
  onLoadMoreReplies?: (parentId: string) => Promise<void> | void;
  onAuthRequired?: () => void;
  authorProfileUrl?: (user: ThreadFSCommentUser) => string | null;

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
  canReply,
  onReply,
  onVote,
  onEdit,
  onDelete,
  onLoadReplies,
  onLoadMoreReplies,
  onAuthRequired,
  authorProfileUrl,
  avatarRef,
}: CommentCardProps) {
  const viewerVote = comment.viewer_vote ?? null;
  const [isReplying, setIsReplying] = useState(false);
  const [areRepliesExpanded, setAreRepliesExpanded] = useState(false);
  const [isLoadingReplies, setIsLoadingReplies] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const isDeleted = comment.status === "deleted";
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

  const isOwnComment =
    currentCommunityUserId != null &&
    comment.community_user_id === currentCommunityUserId;

  const displayName = getDisplayName(comment);
  const avatarUrl = getAvatarUrl(comment);

  const hasReplies = comment.reply_count > 0;
  const loadedReplies = comment.replies ?? [];
  const hasLoadedReplies = loadedReplies.length > 0;

  async function handleToggleReplies() {
    if (!hasReplies) return;

    if (areRepliesExpanded) {
      setAreRepliesExpanded(false);
      return;
    }

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

  return (
    <article ref={setContainerRef} className="threadfs-comment relative py-1">
      <ThreadConnector
        containerRef={containerRef}
        parentAvatarRef={parentAvatarRef}
        repliesButtonRef={repliesButtonRef}
        replyAvatarRefs={replyAvatarRefs}
        replies={loadedReplies}
        hasReplies={hasReplies}
        areRepliesExpanded={areRepliesExpanded}
        measureVersion={measureVersion}
      />

      <div className="relative z-10 flex gap-3">
        <div className="size-8 shrink-0 sm:size-10">
          <img
            ref={setParentAvatarRef}
            src={avatarUrl}
            onError={(e) => {
              e.currentTarget.src = defaultAvatarUrl;
              e.currentTarget.onerror = null;
            }}
            alt={`${displayName}'s avatar`}
            className="border-muted size-8 rounded-full border object-cover sm:size-10"
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        </div>

        <div className="mb-2 min-w-0 flex-1 overflow-hidden">
          <div className="flex flex-wrap items-center gap-2">
            {authorUrl ? (
              <a
                href={authorUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="font-semibold text-cyan-500 hover:cursor-pointer hover:underline dark:text-cyan-200"
              >
                {displayName}
              </a>
            ) : (
              <span className="font-semibold text-cyan-500 dark:text-cyan-200">
                {displayName}
              </span>
            )}

            {isOwnComment && <Badge>You</Badge>}
            <CommentTimestamp value={comment.created_at} />
            {comment.edited_at && comment.status === "visible" && (
              <span className="text-muted-foreground text-xs">(edited)</span>
            )}
          </div>

          {isDeleted ? (
            <p className="text-muted-foreground mt-2 text-sm italic">
              This comment was deleted
            </p>
          ) : isEditing ? (
            <div className="mt-4">
              <CommentEditor
                key={`edit-${comment.id}-${comment.modified_at}`}
                currentUser={currentUser}
                authorProfileUrl={authorProfileUrl}
                submitLabel="Save"
                placeholder="Edit your comment..."
                disabled={!canReply}
                initialMarkdown={comment.content}
                onSubmit={async (body) => {
                  await onEdit?.(comment.id, body);
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
            <div className="threadfs-comment-content overflow-wrap-anywhere mt-2 text-sm leading-6 wrap-break-word">
              <MarkdownContent markdown={comment.content} />
            </div>
          )}

          {!isDeleted && (
            <div className="text-muted-foreground mt-3 flex items-center gap-4 text-sm font-medium">
              <button
                type="button"
                onClick={() => onVote?.(comment.id, 1)}
                aria-pressed={viewerVote === 1}
                className={cn(
                  "hover:text-primary flex items-center gap-1 hover:cursor-pointer",
                  viewerVote === 1 && "text-primary",
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
                className={cn(
                  "hover:text-primary flex items-center gap-1 hover:cursor-pointer",
                  viewerVote === -1 && "text-primary",
                )}
              >
                <ArrowBigDown
                  className={cn("size-4", viewerVote === -1 && "fill-current")}
                />
                <span>{comment.downvote_count ?? 0}</span>
              </button>

              <button
                type="button"
                onClick={handleReplyClick}
                className="hover:text-primary hover:cursor-pointer hover:underline"
              >
                Reply
              </button>
              {isOwnComment && (
                <>
                  <button
                    type="button"
                    onClick={() => setIsEditing(true)}
                    className="hover:text-primary hover:cursor-pointer hover:underline"
                  >
                    Edit
                  </button>

                  <button
                    type="button"
                    disabled={isDeleting}
                    onClick={async () => {
                      const confirmed = window.confirm(
                        "Delete this comment? This cannot be undone.",
                      );

                      if (!confirmed) return;

                      try {
                        setIsDeleting(true);
                        await onDelete?.(comment.id);
                      } finally {
                        setIsDeleting(false);
                      }
                    }}
                    className="hover:text-destructive hover:cursor-pointer hover:underline disabled:opacity-60"
                  >
                    {isDeleting ? "Deleting..." : "Delete"}
                  </button>
                </>
              )}
            </div>
          )}

          {isReplying && (
            <div className="mt-4">
              <CommentEditor
                key={`reply-${comment.id}`}
                currentUser={currentUser}
                authorProfileUrl={authorProfileUrl}
                submitLabel="Reply"
                placeholder={`Reply to ${displayName}...`}
                disabled={!canReply}
                onSubmit={async (body) => {
                  await onReply(comment.id, body);
                  setIsReplying(false);
                  setAreRepliesExpanded(true);
                }}
                onAuthRequired={onAuthRequired}
              />
            </div>
          )}
        </div>
      </div>

      {hasReplies && (
        <div className="relative z-10 flex gap-3">
          <div className="w-8 shrink-0 sm:w-10" />

          <div className="min-w-0 flex-1">
            <button
              ref={setRepliesButtonRef}
              type="button"
              onClick={() => void handleToggleReplies()}
              disabled={isLoadingReplies}
              className="text-primary hover:bg-primary/10 inline-flex items-center gap-1 rounded-full px-2 py-1 text-sm font-medium hover:cursor-pointer hover:underline disabled:opacity-60"
            >
              {areRepliesExpanded ? (
                <ChevronUp className="size-4" />
              ) : (
                <ChevronDown className="size-4" />
              )}

              <span>
                {isLoadingReplies
                  ? "Loading replies..."
                  : areRepliesExpanded
                    ? "Hide replies"
                    : `${comment.reply_count} ${
                        comment.reply_count === 1 ? "reply" : "replies"
                      }`}
              </span>
            </button>
          </div>
        </div>
      )}

      {areRepliesExpanded && hasLoadedReplies && (
        <div className="relative z-10 mt-2">
          {loadedReplies.map((reply) => (
            <div
              key={reply.id}
              className={cn(
                "relative",
                getReplyIndentClass(Math.min(depth + 1, 3)),
              )}
            >
              <CommentCard
                comment={reply}
                avatarRef={getReplyAvatarRef(reply.id)}
                currentCommunityUserId={currentCommunityUserId}
                currentUser={currentUser}
                depth={depth + 1}
                canReply={canReply}
                onReply={onReply}
                onVote={onVote}
                onEdit={onEdit}
                onDelete={onDelete}
                onLoadReplies={onLoadReplies}
                onLoadMoreReplies={onLoadMoreReplies}
                onAuthRequired={onAuthRequired}
                authorProfileUrl={authorProfileUrl}
              />
            </div>
          ))}

          {comment.replies_has_more && (
            <div
              className={cn(
                "mt-2",
                getReplyIndentClass(Math.min(depth + 1, 3)),
              )}
            >
              <Button
                type="button"
                variant="secondary"
                disabled={comment.replies_is_loading_more}
                onClick={() => void onLoadMoreReplies?.(comment.id)}
                className="hover:cursor-pointer hover:underline"
              >
                {comment.replies_is_loading_more
                  ? "Loading replies..."
                  : "Load more replies"}
              </Button>
            </div>
          )}
        </div>
      )}
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

function getDisplayName(comment: ThreadFSComment): string {
  return comment.community_user?.display_name?.trim() || "Anonymous";
}

function getAvatarUrl(comment: ThreadFSComment): string {
  const displayName = getDisplayName(comment);

  return (
    comment.community_user?.avatar_url ||
    `https://api.dicebear.com/8.x/initials/svg?seed=${encodeURIComponent(
      displayName,
    )}`
  );
}

function getReplyIndentClass(depth: number): string {
  if (depth <= 0) return "ml-0";
  if (depth === 1) return "ml-6 sm:ml-[52px]";
  if (depth === 2) return "ml-4 sm:ml-10";
  return "ml-3 sm:ml-8";
}
