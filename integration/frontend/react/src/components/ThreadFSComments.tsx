import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ThreadFSApiError } from "@/lib/errors";
import { ArrowLeft, MessageSquareOff, MessagesSquare } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createComment,
  deleteComment,
  getCommentContext,
  getEmbedConfig,
  getEmbedMe,
  listThreadComments,
  reportComment,
  resolveThread,
  updateComment,
  voteComment,
} from "../lib/api";
import {
  hideComment,
  restoreComment,
  type CommentRemoval,
} from "../lib/moderationApi";
import { GifConfigContext } from "../lib/gifs";
import { ImageHostsContext } from "../lib/imageHosts";
import { RulesUrlContext } from "../lib/rulesContext";
import { continueDepthFor } from "../lib/threadDepth";
import { useLatest } from "../lib/useLatest";
import {
  CommentSort,
  PageResponse,
  ThreadFSCommentUser,
  ThreadFSReason,
  ThreadFSRequestContext,
  ThreadFSThread,
  type EmbedMe,
  type ThreadFSComment,
  CommentMedia,
  ThreadFSGifConfig,
} from "../lib/types";
import { cn } from "../lib/utils";
import CommentCard from "./card/CommentCard";
import CommentEditor from "./editor/CommentEditor";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";
import { TooltipProvider } from "./ui/tooltip";

export type ThreadFSCommentsProps = {
  apiBaseUrl: string;
  communityKey: string;
  threadId: string;

  /** A token with a threadfs_role claim also gives the viewer a Remove action on comments. */
  getAuthToken?: () => Promise<string | null>;

  onAuthRequired?: () => void;
  authorProfileUrl?: (user: ThreadFSCommentUser) => string | null;

  /** Where comments are posted from (a site or app), which moderators can filter and clean up by. */
  source?: string | null;
  /** The kind of client posting them, e.g. "web" or "extension". */
  client?: string | null;

  /**
   * A comment to show in context: its chain from the top-level comment down is pinned above the rest of the list, and
   * it's highlighted and scrolled to. Usually read from the page's #c-<id> hash (commentIdFromHash).
   */
  focusCommentId?: string | null;
  /** A link to one comment, which turns on its Share button. Usually the page's address plus commentHash(id). */
  commentUrl?: (commentId: string) => string | null;

  title?: string;
  className?: string;
  pageSize?: number;
  /**
   * How many replies show under each top-level comment before "N more replies": 0 hides them all, 1 previews the best
   * one, more for a fuller conversation. The best first, at most 5. Left out, the community's own setting applies.
   */
  replyPreview?: number;
};

export function ThreadFSComments({
  apiBaseUrl,
  communityKey,
  threadId,
  getAuthToken,
  onAuthRequired,
  authorProfileUrl,
  source,
  client,
  focusCommentId = null,
  commentUrl,
  title = "Discussion",
  className,
  pageSize = 10,
  replyPreview,
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
  const [reportReasons, setReportReasons] = useState<ThreadFSReason[]>([]);
  const [communityRulesUrl, setCommunityRulesUrl] = useState<string | null>(
    null,
  );
  const [gifConfig, setGifConfig] = useState<ThreadFSGifConfig | null>(null);
  const [imageHosts, setImageHosts] = useState<string[]>([]);
  const [resolvedAuthToken, setResolvedAuthToken] = useState<string | null>(
    null,
  );
  // The linked comment (focusCommentId once found), highlighted; and whether a linked comment wasn't there
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [isFocusMissing, setIsFocusMissing] = useState(false);
  // A comment shown as the root of its own view: on phones, where a deep thread continues (Reddit's "Continue this
  // thread"). Looked up in `comments`, so votes, edits and replies there land in the one tree.
  const [threadRootId, setThreadRootId] = useState<string | null>(null);
  const sectionRef = useRef<HTMLElement>(null);
  // How deep threads nest here, from the widget's width (lib/threadDepth.ts), kept up to date as it resizes
  const [continueDepth, setContinueDepth] = useState(() =>
    continueDepthFor(typeof window === "undefined" ? 1024 : window.innerWidth),
  );
  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;
    const observer = new ResizeObserver(([entry]) =>
      setContinueDepth(continueDepthFor(entry.contentRect.width)),
    );
    observer.observe(section);
    return () => observer.disconnect();
  }, []);
  // Where the page was before continuing a thread, to go back to
  const scrollBeforeThread = useRef<number | null>(null);

  const currentUserForEditor: ThreadFSCommentUser | null = me?.authenticated
    ? {
        id: me.community_user_id!,
        identity_provider: me.identity_provider ?? "external",
        external_user_id: me.external_user_id ?? "",
        display_name: me.display_name,
        avatar_url: me.avatar_url,
        avatar_frame_url: me.avatar_frame_url,
      }
    : null;

  // The host's latest getAuthToken, without a new copy of it reloading the comments (lib/useLatest.ts)
  const getAuthTokenRef = useLatest(getAuthToken);
  const resolveAuthToken = useCallback(async (): Promise<string | null> => {
    const token = (await getAuthTokenRef.current?.()) ?? null;
    setResolvedAuthToken(token);
    return token;
  }, [getAuthTokenRef]);

  const requestContext = useMemo(
    () => ({
      apiBaseUrl,
      communityKey,
      authToken: resolvedAuthToken,
    }),
    [apiBaseUrl, communityKey, resolvedAuthToken],
  );

  const isAuthenticated = Boolean(me?.authenticated && me.community_user_id);
  const isLocked = Boolean(thread?.is_locked);

  useEffect(() => {
    let isMounted = true;

    async function bootstrap() {
      setIsLoading(true);
      setError(null);
      setComments([]);
      setThreadRootId(null);
      setThread(null);
      setMe(null);

      try {
        const config = await getEmbedConfig({
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

        // A linked comment that's gone (deleted for good, another thread) falls back to the whole list
        let context = null;
        let missing = false;
        if (focusCommentId) {
          try {
            context = await getCommentContext(authedRequestContext, {
              threadId,
              commentId: focusCommentId,
              pageSize,
            });
          } catch (err) {
            if (!(err instanceof ThreadFSApiError) || err.status !== 404)
              throw err;
            missing = true;
          }
        }

        const page = await listThreadComments(authedRequestContext, {
          threadId,
          pageSize,
          replyPreview,
          sort: topLevelSort,
        });

        if (!isMounted) return;

        setMe(resolvedMe);
        setReportReasons(config.report_reasons ?? []);
        setCommunityRulesUrl(config.rules_url ?? null);
        setGifConfig(config.gifs ?? null);
        setImageHosts(config.image_hosts ?? []);
        setThread(resolved.thread);
        setFocusedId(context ? String(context.focused_comment_id) : null);
        setIsFocusMissing(missing);
        // A comment deeper than threads nest here opens in its own view, two levels above it shown for context,
        // rather than in a chain that would itself stop at a "more replies" that opens its own view
        const depthHere = continueDepthFor(
          sectionRef.current?.getBoundingClientRect().width ??
            window.innerWidth,
        );
        if (context) {
          const chain: string[] = [];
          for (
            let node: ThreadFSComment | undefined = context.root;
            node;
            node = node.replies?.[0]
          ) {
            chain.push(String(node.id));
            if (String(node.id) === String(context.focused_comment_id)) break;
          }
          if (chain.length - 1 > depthHere) {
            scrollBeforeThread.current = null;
            setThreadRootId(chain[chain.length - 3]);
          }
        }
        // The linked comment's chain first, then the list as usual, without its top-level comment a second time
        setComments(
          context
            ? [context.root, ...withoutIds(page.items, [context.root])]
            : page.items,
        );
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
  }, [
    apiBaseUrl,
    communityKey,
    threadId,
    pageSize,
    replyPreview,
    resolveAuthToken,
    focusCommentId,
  ]);

  async function withAuthRetry<T>(
    action: (ctx: ThreadFSRequestContext) => Promise<T>,
  ): Promise<T> {
    try {
      return await action(requestContext);
    } catch (err) {
      if (!(err instanceof ThreadFSApiError) || err.status !== 401) {
        throw err;
      }

      const freshToken = await resolveAuthToken();

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
      setThreadRootId(null);

      const page = await withAuthRetry((ctx) =>
        listThreadComments(ctx, {
          threadId,
          pageSize,
          replyPreview,
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
        replyPreview,
        offset: topLevelNextOffset,
        sort: topLevelSort,
      });

      // Skipping any already shown (a linked comment's chain is pinned at the top)
      setComments((current) => [
        ...current,
        ...withoutIds(page.items, current),
      ]);
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

  async function handleCreateComment(
    body: string,
    media: CommentMedia,
    parentId?: string | null,
  ) {
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
          media,
          parentId,
          source,
          client,
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

  async function handleEditComment(
    commentId: string,
    body: string,
    media: CommentMedia,
  ) {
    if (!isAuthenticated) {
      onAuthRequired?.();
      return;
    }

    try {
      setError(null);

      const updatedComment = await withAuthRetry((ctx) =>
        updateComment(ctx, commentId, body, media),
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

      // A top-level comment that left the list moves the rest of the server's pages up one
      const droppedTopLevel = applyDeletion(comments, deletedComment).dropped;
      setComments((current) => applyDeletion(current, deletedComment).nodes);
      if (droppedTopLevel > 0) {
        setTopLevelNextOffset((offset) =>
          offset == null ? offset : Math.max(0, offset - droppedTopLevel),
        );
      }
      setThread((current) =>
        current
          ? {
              ...current,
              comment_count: Math.max(0, current.comment_count - 1),
            }
          : current,
      );
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

  async function handleReport(
    commentId: string,
    reason: string,
    details?: string,
  ) {
    try {
      setError(null);
      await withAuthRetry((ctx) =>
        reportComment(ctx, commentId, reason, details),
      );
      return true;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to report comment");
      return false;
    }
  }

  async function handleRemove(commentId: string, removal: CommentRemoval) {
    const removed = await withAuthRetry((ctx) =>
      hideComment(ctx, commentId, removal),
    );

    setComments((current) => replaceCommentInTree(current, removed));
  }

  async function handleRestore(commentId: string) {
    try {
      setError(null);
      const restored = await withAuthRetry((ctx) =>
        restoreComment(ctx, commentId),
      );
      setComments((current) => replaceCommentInTree(current, restored));
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to restore comment",
      );
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
          replies_total: page.total,
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

  // Opens a comment as the root of its own view, its replies loaded and open
  async function handleContinueThread(commentId: string) {
    const comment = findCommentInTree(comments, commentId);
    if (!comment) return;
    if (comment.reply_count > 0 && !comment.replies?.length)
      await handleLoadReplies(commentId);
    scrollBeforeThread.current = window.scrollY;
    setThreadRootId(commentId);
    requestAnimationFrame(() =>
      sectionRef.current?.scrollIntoView({ block: "start" }),
    );
  }

  function handleBackToDiscussion() {
    const scrollY = scrollBeforeThread.current;
    setThreadRootId(null);
    requestAnimationFrame(() =>
      scrollY != null
        ? window.scrollTo({ top: scrollY })
        : sectionRef.current?.scrollIntoView({ block: "start" }),
    );
  }

  const threadRoot = threadRootId
    ? findCommentInTree(comments, threadRootId)
    : null;

  const renderCard = (comment: ThreadFSComment, key: string) => (
    <CommentCard
      key={key}
      comment={comment}
      currentCommunityUserId={me?.community_user_id}
      currentUser={currentUserForEditor}
      canReply={isAuthenticated}
      isLocked={isLocked}
      onReply={(parentId, body, media) =>
        handleCreateComment(body, media, parentId)
      }
      onVote={handleVote}
      onEdit={handleEditComment}
      onDelete={handleDeleteComment}
      onReport={handleReport}
      reportReasons={reportReasons}
      onRemove={me?.staff_role ? handleRemove : undefined}
      onRestore={me?.staff_role ? handleRestore : undefined}
      onLoadReplies={handleLoadReplies}
      onLoadMoreReplies={handleLoadMoreReplies}
      onAuthRequired={onAuthRequired}
      authorProfileUrl={authorProfileUrl}
      highlightedCommentId={focusedId}
      commentUrl={commentUrl}
      onContinueThread={(id) => void handleContinueThread(id)}
      continueDepth={continueDepth}
    />
  );

  const view = (
    <TooltipProvider>
      <section
        ref={sectionRef}
        className={cn("threadfs-root mx-auto w-full space-y-2", className)}
        data-threadfs-thread-id={threadId}
        data-threadfs-community-key={communityKey}
      >
        <h2 className="border-tfs-brand-strong dark:border-tfs-brand border-l-4 pl-4 text-lg font-bold sm:text-xl">
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
              <SelectTrigger className="w-24" aria-label="Sort comments">
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

        {isLocked ? (
          <p className="text-muted-foreground rounded-md border border-dashed px-4 py-3 text-center text-sm">
            This discussion is locked
          </p>
        ) : (
          <CommentEditor
            isLoading={isLoading}
            currentUser={currentUserForEditor}
            authorProfileUrl={authorProfileUrl}
            disabled={!isAuthenticated || isLoading}
            onSubmit={(body, media) => handleCreateComment(body, media)}
            onAuthRequired={onAuthRequired}
          />
        )}

        {isFocusMissing && !isLoading && (
          <p className="text-muted-foreground rounded-md border border-dashed px-4 py-3 text-sm">
            The linked comment isn&apos;t here any more. It may have been
            deleted.
          </p>
        )}

        {error && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mt-2">
          {isLoading ? (
            <CommentSkeleton />
          ) : threadRoot ? (
            <>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                <span className="text-muted-foreground">
                  Continuing a thread
                </span>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={handleBackToDiscussion}
                  className="hover:cursor-pointer"
                >
                  <ArrowLeft className="size-4" /> Back to the discussion
                </Button>
              </div>
              {/* Remounted per root, so its replies open as it appears */}
              {renderCard(threadRoot, `thread-${threadRoot.id}`)}
            </>
          ) : (
            <>
              {comments.length > 0 ? (
                comments.map((comment) =>
                  renderCard(comment, String(comment.id)),
                )
              ) : (
                <div className="px-6 py-16 text-center">
                  <MessageSquareOff
                    aria-hidden
                    className="text-muted-foreground mx-auto mb-3 size-8"
                  />
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

  // Every comment box inside (the top one, and replies and edits) links to the same rules
  return (
    <RulesUrlContext.Provider value={communityRulesUrl}>
      <GifConfigContext.Provider value={gifConfig}>
        <ImageHostsContext.Provider value={imageHosts}>
          {view}
        </ImageHostsContext.Provider>
      </GifConfigContext.Provider>
    </RulesUrlContext.Provider>
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

// Whether a thread still lists a comment that isn't visible, as the server decides: only while something visible is
// below it (reply_count counts visible comments only), or for its author when moderators removed it (others get it
// without its author)
function isListed(comment: ThreadFSComment): boolean {
  if (comment.status === "visible" || comment.reply_count > 0) return true;
  return comment.status === "hidden" && comment.community_user_id != null;
}

// After the viewer deletes a comment: every comment above it has one visible comment fewer below, and it, then any
// of them, leaves the list once nothing visible is left below it. `dropped` is how many top-level comments left.
function applyDeletion(
  comments: ThreadFSComment[],
  deleted: ThreadFSComment,
): { nodes: ThreadFSComment[]; dropped: number } {
  function visit(nodes: ThreadFSComment[]): {
    nodes: ThreadFSComment[];
    found: boolean;
    dropped: number;
  } {
    let found = false;
    let dropped = 0;
    const next: ThreadFSComment[] = [];

    for (const comment of nodes) {
      let updated = comment;

      if (comment.id === deleted.id) {
        found = true;
        updated = { ...comment, ...deleted, replies: comment.replies };
      } else if (comment.replies?.length) {
        const below = visit(comment.replies);
        if (below.found) {
          found = true;
          updated = {
            ...comment,
            reply_count: Math.max(0, comment.reply_count - 1),
            replies: below.nodes,
            replies_total:
              comment.replies_total != null
                ? comment.replies_total - below.dropped
                : comment.replies_total,
            // Replies that left move the rest of the server's pages up
            replies_next_offset:
              comment.replies_next_offset != null
                ? Math.max(0, comment.replies_next_offset - below.dropped)
                : comment.replies_next_offset,
          };
        }
      }

      if (updated !== comment && !isListed(updated)) {
        dropped += 1;
        continue;
      }
      next.push(updated);
    }

    return { nodes: found ? next : nodes, found, dropped };
  }

  const result = visit(comments);
  return { nodes: result.nodes, dropped: result.dropped };
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

// `items` without the ones already in `existing`, by id
function withoutIds(
  items: ThreadFSComment[],
  existing: ThreadFSComment[],
): ThreadFSComment[] {
  const ids = new Set(existing.map((comment) => String(comment.id)));
  return items.filter((comment) => !ids.has(String(comment.id)));
}

function appendRepliesToComment(
  comments: ThreadFSComment[],
  parentId: string,
  page: PageResponse<ThreadFSComment>,
): ThreadFSComment[] {
  return updateCommentInTree(comments, parentId, (comment) => ({
    ...comment,
    // A linked comment's ancestors load the rest of their replies from the start, so skip the one already shown
    replies: [
      ...(comment.replies ?? []),
      ...withoutIds(page.items, comment.replies ?? []),
    ],
    replies_next_offset: page.next_offset,
    replies_has_more: page.has_more,
    replies_total: page.total,
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
    // As strings: ids arrive as numbers, though typed as strings, and a link's id is a string
    if (String(comment.id) === String(commentId)) {
      return comment;
    }

    if (comment.replies?.length) {
      const found = findCommentInTree(comment.replies, commentId);
      if (found) return found;
    }
  }

  return null;
}
