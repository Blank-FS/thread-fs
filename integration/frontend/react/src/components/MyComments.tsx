import {
  ArrowBigDown,
  ArrowBigUp,
  ExternalLink,
  MessageSquare,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  deleteComment,
  getEmbedMe,
  listMyComments,
  updateComment,
  voteComment,
} from "../lib/api";
import { ThreadFSApiError } from "../lib/errors";
import {
  type EmbedMe,
  type ThreadFSComment,
  type ThreadFSCommentUser,
  type ThreadFSRequestContext,
} from "../lib/types";
import { cn } from "../lib/utils";
import CommentTimestamp from "./card/CommentTimestamp";
import { CollapsibleContent } from "./common/CollapsibleContent";
import { MarkdownContent } from "./common/MarkdownContent";
import CommentEditor from "./editor/CommentEditor";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";
import { TooltipProvider } from "./ui/tooltip";

export type ThreadFSMyCommentsProps = {
  apiBaseUrl: string;
  communityKey: string;

  /**
   * The external (platform-side) user id whose comments should be listed.
   * Public: works without the viewer being signed in, subject to the
   * community's anonymous-read policy. Omit to default to the signed-in
   * viewer's own comments (requires authToken/getAuthToken).
   */
  externalUserId?: string;

  authToken?: string | null;
  getAuthToken?: () => Promise<string | null>;

  onAuthRequired?: () => void;
  /** Build the link back to the source thread for a comment. Defaults to comment.thread.source_url. */
  threadUrl?: (comment: ThreadFSComment) => string | null;

  title?: string;
  className?: string;
  pageSize?: number;
};

export function ThreadFSMyComments({
  apiBaseUrl,
  communityKey,
  externalUserId,
  authToken,
  getAuthToken,
  onAuthRequired,
  threadUrl,
  title,
  className,
  pageSize = 10,
}: ThreadFSMyCommentsProps) {
  const [comments, setComments] = useState<ThreadFSComment[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [me, setMe] = useState<EmbedMe | null>(null);
  const [resolvedAuthToken, setResolvedAuthToken] = useState<string | null>(
    authToken ?? null,
  );
  const [editingCommentId, setEditingCommentId] = useState<string | null>(null);
  const [deletingCommentId, setDeletingCommentId] = useState<string | null>(
    null,
  );

  const currentUserForEditor: ThreadFSCommentUser | null = me?.authenticated
    ? {
        id: me.community_user_id!,
        identity_provider: me.identity_provider ?? "external",
        external_user_id: me.external_user_id ?? "",
        display_name: me.display_name,
        avatar_url: me.avatar_url,
      }
    : null;

  const resolveAuthToken = useCallback(async (): Promise<string | null> => {
    if (authToken) {
      setResolvedAuthToken(authToken);
      return authToken;
    }

    if (!getAuthToken) {
      setResolvedAuthToken(null);
      return null;
    }

    const token = await getAuthToken();
    setResolvedAuthToken(token);
    return token;
  }, [authToken, getAuthToken]);

  const requestContext = useMemo<ThreadFSRequestContext>(
    () => ({
      apiBaseUrl,
      communityKey,
      authToken: resolvedAuthToken,
    }),
    [apiBaseUrl, communityKey, resolvedAuthToken],
  );

  const isAuthenticated = Boolean(me?.authenticated && me.community_user_id);
  const requiresViewerAuth = !externalUserId;
  const canLoad = Boolean(externalUserId) || isAuthenticated;

  useEffect(() => {
    let isMounted = true;

    async function bootstrap() {
      setIsLoading(true);
      setError(null);
      setComments([]);
      setMe(null);

      try {
        // Token is optional when viewing someone else's public comments;
        // it's still resolved (if available) so viewer_vote / edit-own
        // detection works for the signed-in viewer.
        const token = await resolveAuthToken();

        if (!token && requiresViewerAuth) {
          return;
        }

        const ctx: ThreadFSRequestContext = {
          apiBaseUrl,
          communityKey,
          authToken: token,
        };

        const [resolvedMe, page] = await Promise.all([
          token ? getEmbedMe(ctx).catch(() => null) : Promise.resolve(null),
          listMyComments(ctx, { externalUserId, pageSize }),
        ]);

        if (!isMounted) return;

        setMe(resolvedMe);
        setComments(page.items);
        setNextOffset(page.next_offset);
        setHasMore(page.has_more);
      } catch (err: unknown) {
        if (isMounted) {
          setError(
            err instanceof Error ? err.message : "Failed to load comments",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void bootstrap();

    return () => {
      isMounted = false;
    };
  }, [
    apiBaseUrl,
    communityKey,
    externalUserId,
    pageSize,
    requiresViewerAuth,
    resolveAuthToken,
  ]);

  async function refreshAuthToken(): Promise<string | null> {
    if (!getAuthToken) {
      return authToken ?? resolvedAuthToken;
    }

    const token = await getAuthToken();
    setResolvedAuthToken(token);
    return token;
  }

  async function withAuthRetry<T>(
    action: (ctx: ThreadFSRequestContext) => Promise<T>,
  ): Promise<T> {
    try {
      return await action(requestContext);
    } catch (err) {
      if (!(err instanceof ThreadFSApiError) || err.status !== 401) {
        throw err;
      }

      const freshToken = await refreshAuthToken();

      if (!freshToken) {
        setMe(null);
        onAuthRequired?.();
        throw err;
      }

      const freshContext: ThreadFSRequestContext = {
        apiBaseUrl,
        communityKey,
        authToken: freshToken,
      };

      try {
        const result = await action(freshContext);

        const resolvedMe = await getEmbedMe(freshContext).catch(() => null);
        setMe(resolvedMe);

        return result;
      } catch (retryErr) {
        if (retryErr instanceof ThreadFSApiError && retryErr.status === 401) {
          setMe(null);
          onAuthRequired?.();
        }

        throw retryErr;
      }
    }
  }

  async function handleLoadMore() {
    if (nextOffset == null || isLoadingMore) return;

    try {
      setError(null);
      setIsLoadingMore(true);

      const page = await listMyComments(requestContext, {
        externalUserId,
        pageSize,
        offset: nextOffset,
      });

      setComments((current) => [...current, ...page.items]);
      setNextOffset(page.next_offset);
      setHasMore(page.has_more);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load more comments",
      );
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function handleEdit(commentId: string, body: string) {
    try {
      setError(null);

      const updated = await withAuthRetry((ctx) =>
        updateComment(ctx, commentId, body),
      );

      setComments((current) =>
        current.map((comment) =>
          comment.id === commentId
            ? { ...comment, ...updated, thread: comment.thread }
            : comment,
        ),
      );
      setEditingCommentId(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to edit comment");
    }
  }

  async function handleDelete(commentId: string) {
    const confirmed = window.confirm(
      "Delete this comment? This cannot be undone.",
    );

    if (!confirmed) return;

    try {
      setError(null);
      setDeletingCommentId(commentId);

      const deleted = await withAuthRetry((ctx) =>
        deleteComment(ctx, commentId),
      );

      setComments((current) =>
        current.map((comment) =>
          comment.id === commentId
            ? { ...comment, ...deleted, thread: comment.thread }
            : comment,
        ),
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete comment");
    } finally {
      setDeletingCommentId(null);
    }
  }

  async function handleVote(commentId: string, value: 1 | -1) {
    if (!isAuthenticated) {
      onAuthRequired?.();
      return;
    }

    const previous = comments.find((comment) => comment.id === commentId);
    const nextValue = previous?.viewer_vote === value ? 0 : value;

    try {
      setError(null);

      const updated = await withAuthRetry((ctx) =>
        voteComment(ctx, commentId, nextValue),
      );

      setComments((current) =>
        current.map((comment) =>
          comment.id === commentId
            ? { ...comment, ...updated, thread: comment.thread }
            : comment,
        ),
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to vote");
    }
  }

  function getThreadHref(comment: ThreadFSComment): string | null {
    if (threadUrl) return threadUrl(comment);
    return comment.thread?.source_url ?? null;
  }

  return (
    <TooltipProvider>
      <section
        className={cn("threadfs-root mx-auto w-full space-y-2", className)}
        data-threadfs-community-key={communityKey}
      >
        {title && (
          <h2 className="border-l-4 border-cyan-500 pl-4 text-lg font-bold tracking-tight sm:text-xl dark:border-cyan-200">
            {title}
          </h2>
        )}

        {error && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {isLoading ? (
          <MyCommentsSkeleton />
        ) : !canLoad ? (
          <div className="rounded-md border border-dashed px-6 py-10 text-center">
            <p className="font-medium">Sign in to see your comments</p>
            {onAuthRequired && (
              <button
                type="button"
                onClick={onAuthRequired}
                className="mt-2 text-sm text-cyan-500 hover:cursor-pointer hover:underline dark:text-cyan-200"
              >
                Sign in
              </button>
            )}
          </div>
        ) : comments.length === 0 ? (
          <div className="rounded-md border border-dashed p-16 text-center">
            <p className="font-medium">No comments yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {comments.map((comment) => {
              const isDeleted = comment.status === "deleted";
              const threadHref = getThreadHref(comment);
              const threadLabel = comment.thread?.title ?? "View thread";
              const viewerVote = comment.viewer_vote ?? null;
              const isOwnComment =
                isAuthenticated &&
                me?.external_user_id != null &&
                comment.community_user?.external_user_id ===
                  me.external_user_id;

              return (
                <div
                  key={comment.id}
                  className="hover:bg-primary/10 rounded-lg p-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    {threadHref ? (
                      <a
                        href={threadHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-sm text-cyan-500 hover:underline dark:text-cyan-200"
                      >
                        <MessageSquare className="size-3.5" />
                        {threadLabel}
                        <ExternalLink className="size-3.5" />
                      </a>
                    ) : (
                      <span className="text-muted-foreground inline-flex items-center gap-1 text-sm">
                        <MessageSquare className="size-3.5" />
                        {threadLabel}
                      </span>
                    )}

                    <CommentTimestamp value={comment.created_at} />
                  </div>

                  {isDeleted ? (
                    <p className="text-muted-foreground mt-2 text-sm italic">
                      This comment was deleted
                    </p>
                  ) : editingCommentId === comment.id ? (
                    <div className="mt-2">
                      <CommentEditor
                        currentUser={currentUserForEditor}
                        submitLabel="Save"
                        placeholder="Edit your comment..."
                        initialMarkdown={comment.content}
                        onSubmit={(body) => handleEdit(comment.id, body)}
                        onAuthRequired={onAuthRequired}
                      />

                      <button
                        type="button"
                        onClick={() => setEditingCommentId(null)}
                        className="text-muted-foreground mt-2 text-sm hover:underline"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <CollapsibleContent
                      maxHeight={240}
                      className="mt-2 text-sm leading-6"
                    >
                      <MarkdownContent markdown={comment.content} />
                    </CollapsibleContent>
                  )}

                  {!isDeleted && (
                    <div className="text-muted-foreground mt-2 flex items-center gap-4 text-sm font-medium">
                      <button
                        type="button"
                        onClick={() => void handleVote(comment.id, 1)}
                        aria-pressed={viewerVote === 1}
                        className={cn(
                          "flex items-center gap-1 hover:cursor-pointer hover:text-cyan-200",
                          viewerVote === 1 && "text-cyan-200",
                        )}
                      >
                        <ArrowBigUp
                          className={cn(
                            "size-4",
                            viewerVote === 1 && "fill-current",
                          )}
                        />
                        {comment.upvote_count}
                      </button>

                      <button
                        type="button"
                        onClick={() => void handleVote(comment.id, -1)}
                        aria-pressed={viewerVote === -1}
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
                        {comment.downvote_count}
                      </button>

                      <span>
                        {comment.reply_count}{" "}
                        {comment.reply_count === 1 ? "reply" : "replies"}
                      </span>

                      {isOwnComment && (
                        <>
                          <button
                            type="button"
                            onClick={() => setEditingCommentId(comment.id)}
                            className="hover:cursor-pointer hover:text-cyan-200 hover:underline"
                          >
                            Edit
                          </button>

                          <button
                            type="button"
                            disabled={deletingCommentId === comment.id}
                            onClick={() => void handleDelete(comment.id)}
                            className="hover:cursor-pointer hover:text-rose-500 hover:underline disabled:opacity-60"
                          >
                            {deletingCommentId === comment.id
                              ? "Deleting..."
                              : "Delete"}
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {hasMore && (
          <div className="mt-4 flex justify-center">
            <Button
              type="button"
              variant="secondary"
              disabled={isLoadingMore}
              onClick={() => void handleLoadMore()}
              className="hover:cursor-pointer hover:underline"
            >
              {isLoadingMore ? "Loading..." : "Load more comments"}
            </Button>
          </div>
        )}
      </section>
    </TooltipProvider>
  );
}

function MyCommentsSkeleton() {
  return (
    <div className="space-y-4">
      {[0, 1, 2].map((item) => (
        <div key={item} className="space-y-2">
          <Skeleton className="h-4 w-32 rounded" />
          <Skeleton className="h-4 w-full rounded" />
          <Skeleton className="h-4 w-3/4 rounded" />
        </div>
      ))}
    </div>
  );
}
