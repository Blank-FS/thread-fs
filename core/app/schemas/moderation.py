# app/schemas/moderation.py

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.schemas.embed import CommentRead, CommunityUserRead, ReasonRead, ThreadRead


class ParentCommentRead(BaseModel):
    """What a reply answers, so moderators can judge it without leaving the queue."""

    id: int
    content: str
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

    model_config = {"from_attributes": True}
