import { buildHeaders, normalizeApiBaseUrl, parseResponseOrThrow } from "./api";
import type {
  CommentFilters,
  CommunityBan,
  ModerationAction,
  ModerationComment,
  ModerationUser,
  ModerationUserDetail,
  PageResponse,
  ReportedComment,
  ThreadFSReason,
  ThreadFSRequestContext,
  ThreadFSThread,
  UserNote,
} from "./types";

export type BanStatus = "active" | "expired" | "lifted" | "all";
export type BanSort = "newest" | "oldest" | "ending_soon";
export type UserSort =
  "name" | "newest" | "most_comments" | "most_removed" | "most_reported";
export type ReportSort = "newest" | "oldest" | "most_reported";
export type CommentSort = "newest" | "oldest" | "changed" | "most_downvoted";

type Page = { limit: number; offset: number };

async function get<T>(
  ctx: ThreadFSRequestContext,
  path: string,
  params: Record<string, string | number | boolean | null | undefined>,
): Promise<T> {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  }

  const res = await fetch(
    `${normalizeApiBaseUrl(ctx.apiBaseUrl)}/api/v1/moderation${path}?${searchParams.toString()}`,
    { method: "GET", headers: buildHeaders(ctx) },
  );

  return parseResponseOrThrow<T>(res);
}

async function send<T>(
  method: string,
  ctx: ThreadFSRequestContext,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(
    `${normalizeApiBaseUrl(ctx.apiBaseUrl)}/api/v1/moderation${path}`,
    {
      method,
      headers: {
        ...buildHeaders(ctx),
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    },
  );

  return parseResponseOrThrow<T>(res);
}

const post = <T>(ctx: ThreadFSRequestContext, path: string, body: unknown) =>
  send<T>("POST", ctx, path, body);

function filterFields(filters: CommentFilters) {
  return {
    source: filters.source || null,
    client: filters.client || null,
    community_user_id: filters.communityUserId || null,
    thread_id: filters.threadId || null,
    removal_reason: filters.removalReason || null,
    without_removal_reason: filters.withoutRemovalReason || null,
    removed_by: filters.removedBy || null,
    since: filters.since || null,
    until: filters.until || null,
  };
}

export const listReports = (
  ctx: ThreadFSRequestContext,
  params: Page & {
    status?: "open" | "closed";
    reason?: string;
    sort?: ReportSort;
  },
) => get<PageResponse<ReportedComment>>(ctx, "/reports", params);

export const resolveReports = (
  ctx: ThreadFSRequestContext,
  commentId: string | number,
  status: "resolved" | "dismissed",
) => post<void>(ctx, `/comments/${commentId}/reports/resolve`, { status });

export const reopenReports = (
  ctx: ThreadFSRequestContext,
  commentId: string | number,
) => post<void>(ctx, `/comments/${commentId}/reports/reopen`, {});

export const searchComments = (
  ctx: ThreadFSRequestContext,
  params: Page &
    CommentFilters & { status?: string; q?: string; sort?: CommentSort },
) => {
  const { limit, offset, status, q, sort, ...filters } = params;

  return get<PageResponse<ModerationComment>>(ctx, "/comments", {
    ...filterFields(filters),
    status,
    q,
    sort,
    limit,
    offset,
  });
};

export type CommentRemoval = {
  reasonKey: string | null;
  reasonDetail: string | null;
  note: string | null;
  ban: boolean;
  banExpiresAt: string | null;
};

export const hideComment = (
  ctx: ThreadFSRequestContext,
  commentId: string | number,
  payload: CommentRemoval,
) =>
  post<ModerationComment>(ctx, `/comments/${commentId}/hide`, {
    reason_key: payload.reasonKey,
    reason_detail: payload.reasonDetail,
    note: payload.note,
    ban: payload.ban,
    ban_expires_at: payload.banExpiresAt,
  });

export const restoreComment = (
  ctx: ThreadFSRequestContext,
  commentId: string | number,
) => post<ModerationComment>(ctx, `/comments/${commentId}/restore`, {});

export const batchComments = (
  ctx: ThreadFSRequestContext,
  params: {
    action: "hide" | "restore";
    filters?: CommentFilters;
    commentIds?: number[];
    reasonKey?: string | null;
    reasonDetail?: string | null;
    note?: string | null;
    dryRun?: boolean;
  },
) =>
  post<{ matched: number; changed: number; refused?: string }>(
    ctx,
    "/comments/batch",
    {
      ...filterFields(params.filters ?? {}),
      comment_ids: params.commentIds ?? null,
      action: params.action,
      reason_key: params.reasonKey ?? null,
      reason_detail: params.reasonDetail ?? null,
      note: params.note ?? null,
      dry_run: params.dryRun ?? false,
    },
  );

export const listBans = (
  ctx: ThreadFSRequestContext,
  params: Page & {
    status: BanStatus;
    length?: string;
    q?: string;
    bannedBy?: string;
    sort?: BanSort;
  },
) => {
  const { bannedBy, ...rest } = params;
  return get<PageResponse<CommunityBan>>(ctx, "/bans", {
    ...rest,
    banned_by: bannedBy,
  });
};

export const banUser = (
  ctx: ThreadFSRequestContext,
  payload: {
    communityUserId: string;
    reason: string | null;
    expiresAt: string | null;
  },
) =>
  post<CommunityBan>(ctx, "/bans", {
    community_user_id: payload.communityUserId,
    reason: payload.reason,
    expires_at: payload.expiresAt,
  });

export const liftBan = (ctx: ThreadFSRequestContext, banId: number) =>
  post<CommunityBan>(ctx, `/bans/${banId}/lift`, {});

export const setThreadLocked = (
  ctx: ThreadFSRequestContext,
  threadId: string,
  locked: boolean,
) =>
  post<ThreadFSThread>(ctx, "/threads/lock", { thread_id: threadId, locked });

export const searchUsers = (
  ctx: ThreadFSRequestContext,
  params: Page & { q?: string; only?: string; sort?: UserSort },
) => get<PageResponse<ModerationUser>>(ctx, "/users", params);

export const getUser = (ctx: ThreadFSRequestContext, userId: string) =>
  get<ModerationUserDetail>(ctx, `/users/${userId}`, {});

export const addNote = (
  ctx: ThreadFSRequestContext,
  userId: string,
  body: string,
) => post<UserNote>(ctx, `/users/${userId}/notes`, { body });

export const deleteNote = (ctx: ThreadFSRequestContext, noteId: number) =>
  send<void>("DELETE", ctx, `/notes/${noteId}`);

export const listReasons = (ctx: ThreadFSRequestContext) =>
  get<ThreadFSReason[]>(ctx, "/reasons", {});

export const replaceReasons = (
  ctx: ThreadFSRequestContext,
  reasons: ThreadFSReason[],
) => send<ThreadFSReason[]>("PUT", ctx, "/reasons", { reasons });

export const undoBatch = (ctx: ThreadFSRequestContext, batchId: string) =>
  post<{ changed: number; skipped: number }>(
    ctx,
    `/batches/${batchId}/undo`,
    {},
  );

export const listActions = (
  ctx: ThreadFSRequestContext,
  params: Page & {
    action?: string;
    moderator?: string;
    target?: string;
    since?: string;
    until?: string;
  },
) => get<PageResponse<ModerationAction>>(ctx, "/actions", params);
