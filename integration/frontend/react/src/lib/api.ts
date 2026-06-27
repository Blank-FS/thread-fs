import { ThreadFSApiError } from "./errors";
import type {
  CommentSort,
  EmbedMe,
  PageResponse,
  ResolveThreadResponse,
  ThreadFSComment,
  ThreadFSEmbedConfig,
  ThreadFSRequestContext,
  ThreadFSThread,
} from "./types";

function normalizeApiBaseUrl(apiBaseUrl: string): string {
  return apiBaseUrl.replace(/\/+$/, "");
}

function buildHeaders(ctx: ThreadFSRequestContext): HeadersInit {
  const headers: HeadersInit = {
    "X-ThreadFS-Community-Key": ctx.communityKey,
  };

  if (ctx.authToken) {
    headers.Authorization = `Bearer ${ctx.authToken}`;
  }

  return headers;
}

export async function parseResponseOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown = null;
    let message = `ThreadFS request failed with status ${res.status}`;

    try {
      body = await res.json();

      if (
        body &&
        typeof body === "object" &&
        "detail" in body &&
        typeof body.detail === "string"
      ) {
        message = body.detail;
      }
    } catch {
      // Response was not JSON.
    }

    throw new ThreadFSApiError(message, res.status, body);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export async function getEmbedConfig(
  ctx: ThreadFSRequestContext,
): Promise<ThreadFSEmbedConfig> {
  const apiBaseUrl = normalizeApiBaseUrl(ctx.apiBaseUrl);

  const res = await fetch(`${apiBaseUrl}/api/v1/embed/config`, {
    method: "GET",
    headers: buildHeaders(ctx),
  });

  return parseResponseOrThrow<ThreadFSEmbedConfig>(res);
}

export async function resolveThread(
  ctx: ThreadFSRequestContext,
  payload: {
    threadId: string;
    title?: string | null;
    sourceUrl?: string | null;
  },
): Promise<ResolveThreadResponse> {
  const apiBaseUrl = normalizeApiBaseUrl(ctx.apiBaseUrl);

  const res = await fetch(`${apiBaseUrl}/api/v1/embed/threads/resolve`, {
    method: "POST",
    headers: {
      ...buildHeaders(ctx),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      thread_id: payload.threadId,
      title: payload.title ?? null,
      source_url: payload.sourceUrl ?? null,
    }),
  });

  return parseResponseOrThrow<ResolveThreadResponse>(res);
}

export async function listThreadComments(
  ctx: ThreadFSRequestContext,
  params: {
    threadId: string;
    parentCommentId?: string | number | null;
    pageSize?: number;
    offset?: number;
    sort?: CommentSort;
  },
): Promise<PageResponse<ThreadFSComment>> {
  const apiBaseUrl = normalizeApiBaseUrl(ctx.apiBaseUrl);

  const searchParams = new URLSearchParams({
    thread_id: params.threadId,
    limit: String(params.pageSize ?? 20),
    offset: String(params.offset ?? 0),
  });

  if (params.parentCommentId != null) {
    searchParams.set("parent_comment_id", String(params.parentCommentId));
  }

  if (params.sort) {
    searchParams.set("sort", params.sort);
  }

  const res = await fetch(
    `${apiBaseUrl}/api/v1/embed/comments?${searchParams.toString()}`,
    {
      method: "GET",
      headers: buildHeaders(ctx),
    },
  );

  return parseResponseOrThrow<PageResponse<ThreadFSComment>>(res);
}
export async function listMyComments(
  ctx: ThreadFSRequestContext,
  params: {
    externalUserId?: string | null;
    pageSize?: number;
    offset?: number;
  } = {},
): Promise<PageResponse<ThreadFSComment>> {
  const apiBaseUrl = normalizeApiBaseUrl(ctx.apiBaseUrl);

  const searchParams = new URLSearchParams({
    limit: String(params.pageSize ?? 20),
    offset: String(params.offset ?? 0),
  });

  if (params.externalUserId) {
    searchParams.set("external_user_id", params.externalUserId);
  }

  const res = await fetch(
    `${apiBaseUrl}/api/v1/embed/comments/mine?${searchParams.toString()}`,
    {
      method: "GET",
      headers: buildHeaders(ctx),
    },
  );

  return parseResponseOrThrow<PageResponse<ThreadFSComment>>(res);
}

export async function createComment(
  ctx: ThreadFSRequestContext,
  payload: {
    threadId: string;
    title?: string | null;
    sourceUrl?: string | null;
    body: string;
    parentId?: string | number | null;
  },
): Promise<ThreadFSComment> {
  const apiBaseUrl = normalizeApiBaseUrl(ctx.apiBaseUrl);

  const res = await fetch(`${apiBaseUrl}/api/v1/embed/comments`, {
    method: "POST",
    headers: {
      ...buildHeaders(ctx),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      thread_id: payload.threadId,
      title: payload.title ?? null,
      source_url: payload.sourceUrl ?? null,
      content: payload.body,
      parent_comment_id:
        payload.parentId === undefined || payload.parentId === null
          ? null
          : Number(payload.parentId),
    }),
  });

  return parseResponseOrThrow<ThreadFSComment>(res);
}

export async function voteComment(
  ctx: ThreadFSRequestContext,
  commentId: string | number,
  value: 1 | -1 | 0,
): Promise<ThreadFSComment> {
  const apiBaseUrl = normalizeApiBaseUrl(ctx.apiBaseUrl);

  const res = await fetch(
    `${apiBaseUrl}/api/v1/embed/comments/${commentId}/votes`,
    {
      method: "POST",
      headers: {
        ...buildHeaders(ctx),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ value }),
    },
  );

  return parseResponseOrThrow<ThreadFSComment>(res);
}

export async function getEmbedMe(
  ctx: ThreadFSRequestContext,
): Promise<EmbedMe> {
  const apiBaseUrl = normalizeApiBaseUrl(ctx.apiBaseUrl);

  const res = await fetch(`${apiBaseUrl}/api/v1/embed/me`, {
    method: "GET",
    headers: buildHeaders(ctx),
  });

  return parseResponseOrThrow<EmbedMe>(res);
}

export async function updateComment(
  ctx: ThreadFSRequestContext,
  commentId: string | number,
  body: string,
): Promise<ThreadFSComment> {
  const apiBaseUrl = normalizeApiBaseUrl(ctx.apiBaseUrl);

  const res = await fetch(`${apiBaseUrl}/api/v1/embed/comments/${commentId}`, {
    method: "PATCH",
    headers: {
      ...buildHeaders(ctx),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      content: body,
    }),
  });

  return parseResponseOrThrow<ThreadFSComment>(res);
}

export async function deleteComment(
  ctx: ThreadFSRequestContext,
  commentId: string | number,
): Promise<ThreadFSComment> {
  const apiBaseUrl = normalizeApiBaseUrl(ctx.apiBaseUrl);

  const res = await fetch(`${apiBaseUrl}/api/v1/embed/comments/${commentId}`, {
    method: "DELETE",
    headers: buildHeaders(ctx),
  });

  return parseResponseOrThrow<ThreadFSComment>(res);
}
