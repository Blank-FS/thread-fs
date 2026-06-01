import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CommentSort,
  PageResponse,
  ThreadFSCommentUser,
  ThreadFSRequestContext,
  ThreadFSThread,
  type EmbedMe,
  type ThreadFSComment,
} from "../lib/types";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  createComment,
  deleteComment,
  getEmbedConfig,
  getEmbedMe,
  listThreadComments,
  resolveThread,
  updateComment,
  voteComment,
} from "../lib/api";
import { cn } from "../lib/utils";
import CommentEditor from "./editor/CommentEditor";
import CommentCard from "./card/CommentCard";
import { TooltipProvider } from "./ui/tooltip";
import { MessagesSquare } from "lucide-react";
import { Skeleton } from "./ui/skeleton";
import { ThreadFSApiError } from "@/lib/errors";
import { Button } from "./ui/button";

export type ThreadFSCommentsProps = {
  apiBaseUrl: string;
  communityKey: string;
  threadId: string;

  authToken?: string | null;
  getAuthToken?: () => Promise<string | null>;

  onAuthRequired?: () => void;
  authorProfileUrl?: (user: ThreadFSCommentUser) => string | null;

  title?: string;
  className?: string;
  pageSize?: number;
};

export function ThreadFSComments({
  apiBaseUrl,
  communityKey,
  threadId,
  authToken,
  getAuthToken,
  onAuthRequired,
  authorProfileUrl,
  title = "Discussion",
  className,
  pageSize = 10,
}: ThreadFSCommentsProps) {
  const [comments, setComments] = useState<ThreadFSComment[]>([]);
  const [topLevelSort, setTopLevelSort] = useState<CommentSort>("latest");
  const [isChangingSort, setIsChangingSort] = useState(false);
  const [topLevelNextOffset, setTopLevelNextOffset] = useState<number | null>(
    null,
  );
  const [hasMoreTopLevelComments, setHasMoreTopLevelComments] = useState(false);
  const [isLoadingMoreComments, setIsLoadingMoreComments] = useState(false);
  const [thread, setThread] = useState<ThreadFSThread | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [me, setMe] = useState<EmbedMe | null>(null);
  const [resolvedAuthToken, setResolvedAuthToken] = useState<string | null>(
    authToken ?? null,
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

  const requestContext = useMemo(
    () => ({
      apiBaseUrl,
      communityKey,
      authToken: resolvedAuthToken,
    }),
    [apiBaseUrl, communityKey, resolvedAuthToken],
  );

  const isAuthenticated = Boolean(me?.authenticated && me.community_user_id);

  useEffect(() => {
    let isMounted = true;

    async function bootstrap() {
      setIsLoading(true);
      setError(null);
      setComments([]);
      setThread(null);
      setMe(null);

      try {
        await getEmbedConfig({
          apiBaseUrl,
          communityKey,
          authToken: null,
        });

        const token = await resolveAuthToken();

        const authedRequestContext = {
          apiBaseUrl,
          communityKey,
          authToken: token,
        };

        const resolvedMe = token
          ? await getEmbedMe(authedRequestContext).catch(() => null)
          : null;

        const resolved = await resolveThread(authedRequestContext, {
          threadId,
          sourceUrl: window.location.href,
          title: document.title,
        });

        const page = await listThreadComments(authedRequestContext, {
          threadId,
          pageSize,
          sort: topLevelSort,
        });

        if (!isMounted) return;

        setMe(resolvedMe);
        setThread(resolved.thread);
        setComments(page.items);
        setTopLevelNextOffset(page.next_offset);
        setHasMoreTopLevelComments(page.has_more);
      } catch (err: unknown) {
        if (isMounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to initialize ThreadFS comments",
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
  }, [apiBaseUrl, communityKey, threadId, pageSize, resolveAuthToken]);

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

  async function handleChangeTopLevelSort(nextSort: CommentSort) {
    if (nextSort === topLevelSort) return;

    try {
      setIsChangingSort(true);
      setError(null);
      setTopLevelSort(nextSort);

      const page = await withAuthRetry((ctx) =>
        listThreadComments(ctx, {
          threadId,
          pageSize,
          sort: nextSort,
        }),
      );

      setComments(page.items);
      setTopLevelNextOffset(page.next_offset);
      setHasMoreTopLevelComments(page.has_more);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to sort comments");
    } finally {
      setIsChangingSort(false);
    }
  }

  async function handleLoadMoreComments() {
    if (topLevelNextOffset == null || isLoadingMoreComments) {
      return;
    }

    try {
      setError(null);
      setIsLoadingMoreComments(true);

      const page = await listThreadComments(requestContext, {
        threadId,
        pageSize,
        offset: topLevelNextOffset,
        sort: topLevelSort,
      });

      setComments((current) => [...current, ...page.items]);
      setTopLevelNextOffset(page.next_offset);
      setHasMoreTopLevelComments(page.has_more);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load comments");
    } finally {
      setIsLoadingMoreComments(false);
    }
  }

  async function handleLoadMoreReplies(parentId: string) {
    const parent = findCommentInTree(comments, parentId);

    if (!parent?.replies_has_more || parent.replies_next_offset == null) {
      return;
    }

    try {
      setError(null);

      setComments((current) => setRepliesLoading(current, parentId, true));

      const page = await listThreadComments(requestContext, {
        threadId,
        parentCommentId: parentId,
        pageSize,
        offset: parent.replies_next_offset,
        sort: "oldest",
      });

      setComments((current) => appendRepliesToComment(current, parentId, page));
    } catch (err: unknown) {
      setComments((current) => setRepliesLoading(current, parentId, false));
      setError(
        err instanceof Error ? err.message : "Failed to load more replies",
      );
    }
  }

  async function handleCreateComment(body: string, parentId?: string | null) {
    if (!isAuthenticated) {
      onAuthRequired?.();
      return;
    }

    try {
      setError(null);

      const createdComment = await withAuthRetry((ctx) =>
        createComment(ctx, {
          threadId,
          title: typeof document !== "undefined" ? document.title : null,
          sourceUrl:
            typeof window !== "undefined" ? window.location.href : null,
          body,
          parentId,
        }),
      );

      if (!thread) {
        // Thread was just created by the first comment.
        const resolved = await resolveThread(requestContext, {
          threadId,
          title: typeof document !== "undefined" ? document.title : null,
          sourceUrl:
            typeof window !== "undefined" ? window.location.href : null,
        });

        setThread(resolved.thread);
      } else {
        setThread((current) =>
          current
            ? {
                ...current,
                comment_count: current.comment_count + 1,
              }
            : current,
        );
      }

      if (parentId) {
        setComments((current) =>
          addReplyToCommentTree(current, parentId, createdComment),
        );
      } else {
        setComments((current) => [createdComment, ...current]);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create comment");
    }
  }

  async function handleEditComment(commentId: string, body: string) {
    if (!isAuthenticated) {
      onAuthRequired?.();
      return;
    }

    try {
      setError(null);

      const updatedComment = await withAuthRetry((ctx) =>
        updateComment(ctx, commentId, body),
      );

      setComments((current) => replaceCommentInTree(current, updatedComment));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to edit comment");
    }
  }

  async function handleDeleteComment(commentId: string) {
    if (!isAuthenticated) {
      onAuthRequired?.();
      return;
    }

    try {
      setError(null);

      const deletedComment = await withAuthRetry((ctx) =>
        deleteComment(ctx, commentId),
      );

      setComments((current) => replaceCommentInTree(current, deletedComment));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete comment");
    }
  }

  async function handleVote(commentId: string, value: 1 | -1) {
    if (!isAuthenticated) {
      onAuthRequired?.();
      return;
    }

    try {
      setError(null);

      const updatedComment = await withAuthRetry((ctx) =>
        voteComment(ctx, commentId, value),
      );

      setComments((current) => replaceCommentInTree(current, updatedComment));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to vote");
    }
  }

  function attachReplies(
    comments: ThreadFSComment[],
    parentId: string,
    page: PageResponse<ThreadFSComment>,
  ): ThreadFSComment[] {
    return comments.map((comment) => {
      if (comment.id === parentId) {
        return {
          ...comment,
          replies: page.items,
          replies_next_offset: page.next_offset,
          replies_has_more: page.has_more,
        };
      }

      if (comment.replies?.length) {
        return {
          ...comment,
          replies: attachReplies(comment.replies, parentId, page),
        };
      }

      return comment;
    });
  }

  async function handleLoadReplies(parentId: string) {
    try {
      setError(null);

      const page = await listThreadComments(requestContext, {
        threadId,
        parentCommentId: parentId,
        pageSize,
        sort: "oldest",
      });

      setComments((current) => attachReplies(current, parentId, page));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load replies");
    }
  }

  return (
    <TooltipProvider>
      <section
        className={cn("threadfs-root mx-auto w-full space-y-2", className)}
        data-threadfs-thread-id={threadId}
        data-threadfs-community-key={communityKey}
      >
        <h2 className="border-l-4 border-cyan-500 pl-4 text-lg font-bold tracking-tight sm:text-xl dark:border-cyan-200">
          {title}
        </h2>

        <div className="flex items-center justify-between border-b py-2">
          <div className="flex items-center gap-2 text-sm">
            <MessagesSquare className="size-4" />
            {isLoading ? (
              <Skeleton className="roundeded h-4 w-20" />
            ) : (
              <span className="mt-1">
                {thread?.comment_count ?? 0}{" "}
                {thread?.comment_count === 1 ? "comment" : "comments"}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground hidden sm:inline">
              Sort by
            </span>
            <Select
              value={topLevelSort}
              disabled={isLoading || isChangingSort}
              onValueChange={(val) =>
                void handleChangeTopLevelSort(val as CommentSort)
              }
            >
              <SelectTrigger className="w-24">
                <SelectValue placeholder="Options" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="latest">Latest</SelectItem>
                  <SelectItem value="oldest">Oldest</SelectItem>
                  <SelectItem value="top">Top</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
        </div>

        <CommentEditor
          isLoading={isLoading}
          currentUser={currentUserForEditor}
          authorProfileUrl={authorProfileUrl}
          disabled={!isAuthenticated || isLoading}
          placeholder={
            isAuthenticated
              ? "Join the discussion..."
              : "Sign in to join the discussion..."
          }
          onSubmit={(body) => handleCreateComment(body)}
          onAuthRequired={onAuthRequired}
        />

        {error && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mt-2">
          {isLoading ? (
            <CommentSkeleton />
          ) : (
            <>
              {comments.length > 0 ? (
                comments.map((comment, index) => (
                  <CommentCard
                    key={comment.id}
                    comment={comment}
                    currentCommunityUserId={me?.community_user_id}
                    currentUser={currentUserForEditor}
                    canReply={isAuthenticated}
                    onReply={(parentId, body) =>
                      handleCreateComment(body, parentId)
                    }
                    onVote={handleVote}
                    onEdit={handleEditComment}
                    onDelete={handleDeleteComment}
                    onLoadReplies={handleLoadReplies}
                    onLoadMoreReplies={handleLoadMoreReplies}
                    onAuthRequired={onAuthRequired}
                    authorProfileUrl={authorProfileUrl}
                  />
                ))
              ) : (
                <div className="rounded-md border border-dashed px-6 py-10 text-center">
                  <p className="font-medium">No comments yet</p>
                  <p className="text-muted-foreground mt-1 text-sm">
                    Start the conversation
                  </p>
                </div>
              )}
              {hasMoreTopLevelComments && (
                <div className="mt-4 flex justify-center">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={isLoadingMoreComments}
                    onClick={() => void handleLoadMoreComments()}
                    className="hover:cursor-pointer hover:underline"
                  >
                    {isLoadingMoreComments
                      ? "Loading..."
                      : "Load more comments"}
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </section>
    </TooltipProvider>
  );
}

function CommentSkeleton() {
  return (
    <div className="space-y-4">
      {[0, 1, 2].map((item) => (
        <div key={item} className="flex gap-3">
          <Skeleton className="size-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-full max-w-40 rounded" />
            <Skeleton className="h-4 w-full rounded" />
            <Skeleton className="h-4 w-3/4 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

function addReplyToCommentTree(
  comments: ThreadFSComment[],
  parentId: string,
  newReply: ThreadFSComment,
): ThreadFSComment[] {
  function visit(nodes: ThreadFSComment[]): {
    nodes: ThreadFSComment[];
    insertedInSubtree: boolean;
  } {
    let insertedSomewhere = false;

    const nextNodes = nodes.map((comment) => {
      if (comment.id === parentId) {
        insertedSomewhere = true;

        return {
          ...comment,
          reply_count: comment.reply_count + 1,
          replies: [...(comment.replies ?? []), newReply],
        };
      }

      if (comment.replies?.length) {
        const result = visit(comment.replies);

        if (result.insertedInSubtree) {
          insertedSomewhere = true;

          return {
            ...comment,
            reply_count: comment.reply_count + 1,
            replies: result.nodes,
          };
        }

        return comment;
      }

      return comment;
    });

    return {
      nodes: nextNodes,
      insertedInSubtree: insertedSomewhere,
    };
  }

  return visit(comments).nodes;
}

function replaceCommentInTree(
  comments: ThreadFSComment[],
  updatedComment: ThreadFSComment,
): ThreadFSComment[] {
  return comments.map((comment) => {
    if (comment.id === updatedComment.id) {
      return {
        ...comment,
        ...updatedComment,
        replies: comment.replies,
      };
    }

    if (comment.replies?.length) {
      return {
        ...comment,
        replies: replaceCommentInTree(comment.replies, updatedComment),
      };
    }

    return comment;
  });
}

function updateCommentInTree(
  comments: ThreadFSComment[],
  commentId: string,
  updater: (comment: ThreadFSComment) => ThreadFSComment,
): ThreadFSComment[] {
  return comments.map((comment) => {
    if (comment.id === commentId) {
      return updater(comment);
    }

    if (comment.replies?.length) {
      return {
        ...comment,
        replies: updateCommentInTree(comment.replies, commentId, updater),
      };
    }

    return comment;
  });
}

function appendRepliesToComment(
  comments: ThreadFSComment[],
  parentId: string,
  page: PageResponse<ThreadFSComment>,
): ThreadFSComment[] {
  return updateCommentInTree(comments, parentId, (comment) => ({
    ...comment,
    replies: [...(comment.replies ?? []), ...page.items],
    replies_next_offset: page.next_offset,
    replies_has_more: page.has_more,
    replies_is_loading_more: false,
  }));
}

function setRepliesLoading(
  comments: ThreadFSComment[],
  parentId: string,
  isLoading: boolean,
): ThreadFSComment[] {
  return updateCommentInTree(comments, parentId, (comment) => ({
    ...comment,
    replies_is_loading_more: isLoading,
  }));
}

function findCommentInTree(
  comments: ThreadFSComment[],
  commentId: string,
): ThreadFSComment | null {
  for (const comment of comments) {
    if (comment.id === commentId) {
      return comment;
    }

    if (comment.replies?.length) {
      const found = findCommentInTree(comment.replies, commentId);
      if (found) return found;
    }
  }

  return null;
}
