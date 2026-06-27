export type PageResponse<T> = {
  items: T[];
  limit: number;
  offset: number;
  next_offset: number | null;
  has_more: boolean;
  total: number | null;
};

export type CommentSort = "latest" | "oldest" | "top";

export type ThreadFSCurrentUser = {
  id: string;
  name: string;
  avatarUrl?: string | null;
};

export type ThreadFSEmbedConfig = {
  community_id: string;
  name: string;
  slug: string;
  allow_anonymous_read: boolean;
  allow_anonymous_comment: boolean;
};

export type ThreadFSThread = {
  id: number;
  community_id: string;
  unique_id: string;
  title: string | null;
  source_url: string | null;
  comment_count: number;
  is_locked: boolean;
  is_deleted: boolean;
  created_at?: string;
  modified_at?: string;
};

export type ResolveThreadResponse = {
  exists: boolean;
  thread: ThreadFSThread | null;
};

export type ThreadFSCommentUser = {
  id: string;
  identity_provider: string;
  external_user_id: string;
  display_name: string | null;
  avatar_url: string | null;
};

export type ThreadFSComment = {
  id: string;
  thread_id: number;
  parent_comment_id: string | null;
  community_user_id: string;

  community_user?: ThreadFSCommentUser | null;

  content: string;
  status: string;

  upvote_count: number;
  downvote_count: number;
  reply_count: number;
  viewer_vote?: 1 | -1 | null;

  edited_at?: string | null;
  deleted_at?: string | null;

  created_at: string;
  modified_at: string;

  replies?: ThreadFSComment[];

  replies_next_offset?: number | null;
  replies_has_more?: boolean;
  replies_is_loading_more?: boolean;

  /** Only populated by endpoints that list comments across threads, e.g. listMyComments. */
  thread?: ThreadFSThread | null;
};

export type ThreadFSRequestContext = {
  apiBaseUrl: string;
  communityKey: string;
  authToken?: string | null;
};

export type EmbedMe = {
  authenticated: boolean;
  community_user_id: string | null;
  identity_provider: string | null;
  external_user_id: string | null;
  display_name: string | null;
  avatar_url: string | null;
  threadfs_user_id: string | null;
};

// Other
export type ConnectorPoint = {
  x: number;
  y: number;
};

export type ConnectorGeometry = {
  width: number;
  height: number;
  railX: number;
  startY: number;
  endY: number;
  buttonPoint: ConnectorPoint | null;
  replyPoints: ConnectorPoint[];
};
