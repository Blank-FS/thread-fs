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
  report_reasons?: ThreadFSReason[];
};

/** One of a community's reasons, used for reporting and removing comments. */
export type ThreadFSReason = {
  key: string;
  label: string;
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
  /** Null on a comment moderators removed, unless the viewer wrote it. */
  community_user_id: string | null;

  community_user?: ThreadFSCommentUser | null;

  content: string;
  status: string;
  /** Why moderators removed it. Only its author gets this. */
  removal_reason?: string | null;
  /** The moderator's own words, when the reason is "other". */
  removal_detail?: string | null;

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
  staff_role: ThreadFSStaffRole | null;
};

export type ThreadFSStaffRole = "moderator" | "admin";

/** A user as moderators see them: the role in their latest token, for protecting and labelling them. */
export type StaffAwareUser = ThreadFSCommentUser & {
  last_staff_role?: ThreadFSStaffRole | null;
};

export type ModerationComment = ThreadFSComment & {
  community_user?: StaffAwareUser | null;
  source?: string | null;
  client?: string | null;
  parent?: {
    id: number;
    content: string;
    status: string;
    community_user?: ThreadFSCommentUser | null;
  } | null;
  /** Who removed it, when and why. Only on removed comments. */
  removal?: {
    created_at: string;
    reason: string | null;
    moderator?: ThreadFSCommentUser | null;
  } | null;
};

export type CommentReport = {
  id: number;
  created_at: string;
  reason: string;
  reason_label: string | null;
  details: string | null;
  status: string;
  reporter?: ThreadFSCommentUser | null;
  resolver?: ThreadFSCommentUser | null;
};

export type ReportedComment = {
  comment: ModerationComment;
  reports: CommentReport[];
};

export type CommentFilters = {
  source?: string;
  client?: string;
  communityUserId?: string;
  threadId?: string;
  removalReason?: string;
  withoutRemovalReason?: boolean;
  removedBy?: string;
  since?: string;
  until?: string;
};

export type CommunityBan = {
  id: number;
  created_at: string;
  community_user?: ThreadFSCommentUser | null;
  banned_by?: ThreadFSCommentUser | null;
  lifted_by?: ThreadFSCommentUser | null;
  reason: string | null;
  expires_at: string | null;
  lifted_at: string | null;
};

export type ModerationUser = StaffAwareUser & {
  created_at: string;
  comment_count: number;
  removed_count: number;
  report_count: number;
  is_banned: boolean;
};

export type UserNote = {
  id: number;
  created_at: string;
  body: string;
  author?: ThreadFSCommentUser | null;
};

export type ModerationUserDetail = ModerationUser & {
  bans: CommunityBan[];
  notes: UserNote[];
};

export type StaffActivity = {
  user: ModerationUser;
  removed: number;
  restored: number;
  bans: number;
  batches: number;
  last_active_at: string | null;
  is_suspended: boolean;
};

export type AdminOverview = {
  activity_days: number;
  max_batch_size: number;
  max_daily_batch_changes: number;
  origins: string[];
  staff: StaffActivity[];
};

export type ModerationAction = {
  id: number;
  created_at: string;
  action: string;
  reason: string | null;
  comment_id: number | null;
  thread_id: number | null;
  moderator?: ThreadFSCommentUser | null;
  target?: ThreadFSCommentUser | null;
  comment?: { id: number; content: string; status: string } | null;
  thread?: ThreadFSThread | null;
  /** On a batch's summary entry. */
  batch?: {
    id: string;
    comment_count: number;
    undone_at: string | null;
  } | null;
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
