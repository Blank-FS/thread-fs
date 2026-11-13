# app/schemas/moderation.py

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.schemas.embed import CommentRead, CommunityUserRead, GifRead, ImageRead, ReasonRead, ThreadRead


class ParentCommentRead(BaseModel):
    """What a reply answers, so moderators can judge it without leaving the queue."""

    id: int
    content: str
    gif: GifRead | None = None
    image: ImageRead | None = None
    status: str
    community_user: CommunityUserRead | None = None

    model_config = {"from_attributes": True}


class RemovalRead(BaseModel):
    """The log entry for a comment's latest removal."""

    created_at: datetime
    reason: str | None
    moderator: CommunityUserRead | None = None

    model_config = {"from_attributes": True}


class StaffAwareUserRead(CommunityUserRead):
    """A user as moderators see them, so what they may do to them can be shown."""

    last_staff_role: str | None = None


class ModerationCommentRead(CommentRead):
    """A comment as moderators see it: nothing withheld, plus where it came from."""

    community_user: StaffAwareUserRead | None = None
    source: str | None = None
    client: str | None = None
    thread: ThreadRead | None = None
    parent: ParentCommentRead | None = None
    removal: RemovalRead | None = None


class ReportRead(BaseModel):
    id: int
    created_at: datetime
    reason: str
    reason_label: str | None
    details: str | None
    status: str
    reporter: CommunityUserRead | None = None
    resolver: CommunityUserRead | None = None

    model_config = {"from_attributes": True}


class ReportedCommentRead(BaseModel):
    comment: ModerationCommentRead
    reports: list[ReportRead]


class ReasonRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class RemoveRequest(BaseModel):
    """Removes a comment, optionally banning its author in the same step."""

    # A key from the community's reasons; its label is what the author sees
    reason_key: str | None = Field(default=None, max_length=64)
    # What the author sees instead of the label, when the reason is "other"
    reason_detail: str | None = Field(default=None, max_length=200)
    # Stays private, in the moderation log
    note: str | None = Field(default=None, max_length=1000)
    ban: bool = False
    # None is permanent
    ban_expires_at: AwareDatetime | None = None


class ResolveReportsRequest(BaseModel):
    status: Literal["resolved", "dismissed"]


class CommentFilters(BaseModel):
    source: str | None = Field(default=None, max_length=255)
    client: str | None = Field(default=None, max_length=32)
    community_user_id: UUID | None = None
    thread_id: str | None = Field(default=None, max_length=512)
    comment_ids: list[int] | None = Field(default=None, max_length=200)
    removal_reason: str | None = Field(default=None, max_length=128)
    without_removal_reason: bool | None = None
    removed_by: UUID | None = None
    since: AwareDatetime | None = None
    until: AwareDatetime | None = None


class BatchRequest(CommentFilters):
    """Hide or restore every comment matching the filters. dry_run only counts them."""

    action: Literal["hide", "restore"]
    reason_key: str | None = Field(default=None, max_length=64)
    reason_detail: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)
    dry_run: bool = False

    @model_validator(mode="after")
    def needs_a_filter(self):
        filters = (
            self.source,
            self.client,
            self.community_user_id,
            self.thread_id,
            self.comment_ids,
            self.removal_reason,
            self.without_removal_reason,
            self.removed_by,
            self.since,
            self.until,
        )
        if all(value is None for value in filters):
            raise ValueError("A batch needs at least one filter")
        return self


class BatchResult(BaseModel):
    matched: int
    changed: int
    # On a dry run: why running it would be refused
    refused: str | None = None


class StaffActivityRead(BaseModel):
    user: StaffAwareUserRead
    removed: int
    restored: int
    bans: int
    batches: int
    last_active_at: datetime | None
    is_suspended: bool


class AdminOverviewRead(BaseModel):
    activity_days: int
    max_batch_size: int
    max_daily_batch_changes: int
    rules_url: str | None = None
    reply_preview: int = 0
    # Public by design (the widget searches with it), so admins may see it
    klipy_app_key: str | None = None
    image_hosts: list[str] = []
    origins: list[str]
    staff: list[StaffActivityRead]


class LimitsRequest(BaseModel):
    max_batch_size: int = Field(ge=1, le=1000)
    max_daily_batch_changes: int = Field(ge=1, le=100000)

    @model_validator(mode="after")
    def a_day_fits_a_batch(self):
        if self.max_daily_batch_changes < self.max_batch_size:
            raise ValueError("The daily limit can't be lower than the batch limit")
        return self


class RulesRequest(BaseModel):
    # A page on the community's site; empty or null clears it
    rules_url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def a_web_page(self):
        url = (self.rules_url or "").strip()
        if url and not url.startswith(("https://", "http://")):
            raise ValueError("The rules link must be a web address (https://...)")
        self.rules_url = url or None
        return self


class ReplyPreviewRequest(BaseModel):
    # How many replies show under each top-level comment; 0 for none
    reply_preview: int = Field(ge=0, le=5)


class GifsRequest(BaseModel):
    # A KLIPY app key turns GIFs on; empty or null turns them off
    klipy_app_key: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def a_key(self):
        key = (self.klipy_app_key or "").strip()
        # It goes in the path of KLIPY's URLs, so nothing that could change the path
        if key and not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            raise ValueError("That doesn't look like a KLIPY app key")
        self.klipy_app_key = key or None
        return self


# A hostname, nothing else: no scheme, path, port or wildcard
_HOSTNAME_RE = re.compile(r"(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
MAX_IMAGE_HOSTS = 20


class ImageHostsRequest(BaseModel):
    # Exact hostnames, so a subdomain or lookalike of an allowed host isn't allowed too
    image_hosts: list[str] = Field(default_factory=list, max_length=MAX_IMAGE_HOSTS)

    @model_validator(mode="after")
    def hostnames(self):
        hosts: list[str] = []
        for raw in self.image_hosts:
            host = raw.strip().lower().rstrip(".")
            if not host:
                continue
            if not _HOSTNAME_RE.fullmatch(host):
                raise ValueError(f"{raw.strip()!r} isn't a hostname (like i.imgur.com)")
            if host not in hosts:
                hosts.append(host)
        self.image_hosts = hosts
        return self


class UndoBatchResult(BaseModel):
    changed: int
    # Comments that changed again after the batch, and so were left alone
    skipped: int


class BatchRead(BaseModel):
    id: UUID
    comment_count: int
    undone_at: datetime | None

    model_config = {"from_attributes": True}


class ClearImagesRequest(BaseModel):
    """Which of a user's images to clear, naming them by the host's own user id (the token's subject)."""

    external_user_id: str = Field(min_length=1, max_length=255)
    avatar: bool = False
    frame: bool = False
    reason: str | None = Field(default=None, max_length=1000)


class BanRequest(BaseModel):
    community_user_id: UUID
    reason: str | None = Field(default=None, max_length=1000)
    # None is permanent
    expires_at: AwareDatetime | None = None


class BanRead(BaseModel):
    id: int
    created_at: datetime
    community_user: CommunityUserRead | None = None
    banned_by: CommunityUserRead | None = None
    lifted_by: CommunityUserRead | None = None
    reason: str | None
    expires_at: datetime | None
    lifted_at: datetime | None

    model_config = {"from_attributes": True}


class ModerationUserRead(StaffAwareUserRead):
    created_at: datetime
    comment_count: int = 0
    removed_count: int = 0
    report_count: int = 0
    is_banned: bool = False


class UserNoteRead(BaseModel):
    id: int
    created_at: datetime
    body: str
    author: CommunityUserRead | None = None

    model_config = {"from_attributes": True}


class ModerationUserDetailRead(ModerationUserRead):
    bans: list[BanRead] = []
    notes: list[UserNoteRead] = []


class UserNoteRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class ReasonWrite(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    label: str = Field(min_length=1, max_length=128)


class ReasonsRequest(BaseModel):
    reasons: list[ReasonWrite] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def keys_are_unique(self):
        if len({reason.key for reason in self.reasons}) != len(self.reasons):
            raise ValueError("Reason keys must be unique")
        return self


class LockThreadRequest(ReasonRequest):
    thread_id: str = Field(min_length=1, max_length=512)
    locked: bool


class ActionCommentRead(BaseModel):
    """The comment a log entry is about, as it stands now."""

    id: int
    content: str
    gif: GifRead | None = None
    image: ImageRead | None = None
    status: str

    model_config = {"from_attributes": True}


class ModerationActionRead(BaseModel):
    id: int
    created_at: datetime
    action: str
    reason: str | None
    comment_id: int | None
    thread_id: int | None
    moderator: CommunityUserRead | None = None
    target: CommunityUserRead | None = None
    comment: ActionCommentRead | None = None
    thread: ThreadRead | None = None
    batch: BatchRead | None = None

    model_config = {"from_attributes": True}
