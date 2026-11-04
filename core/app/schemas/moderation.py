# app/schemas/moderation.py

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.schemas.embed import CommentRead, CommunityUserRead, ThreadRead


class ModerationCommentRead(CommentRead):
    """A comment as moderators see it: nothing withheld, plus where it came from."""

    source: str | None = None
    client: str | None = None
    thread: ThreadRead | None = None


class ReportRead(BaseModel):
    id: int
    created_at: datetime
    reason: str
    details: str | None
    status: str
    reporter: CommunityUserRead | None = None

    model_config = {"from_attributes": True}


class ReportedCommentRead(BaseModel):
    comment: ModerationCommentRead
    reports: list[ReportRead]


class ReasonRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ResolveReportsRequest(BaseModel):
    status: Literal["resolved", "dismissed"]


class CommentFilters(BaseModel):
    source: str | None = Field(default=None, max_length=255)
    client: str | None = Field(default=None, max_length=32)
    community_user_id: UUID | None = None
    thread_id: str | None = Field(default=None, max_length=512)
    since: AwareDatetime | None = None
    until: AwareDatetime | None = None


class BatchRequest(CommentFilters):
    """Hide or restore every comment matching the filters. dry_run only counts them."""

    action: Literal["hide", "restore"]
    reason: str | None = Field(default=None, max_length=1000)
    dry_run: bool = False

    @model_validator(mode="after")
    def needs_a_filter(self):
        filters = (self.source, self.client, self.community_user_id, self.thread_id, self.since, self.until)
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
    reason: str | None
    expires_at: datetime | None
    lifted_at: datetime | None

    model_config = {"from_attributes": True}


class LockThreadRequest(ReasonRequest):
    thread_id: str = Field(min_length=1, max_length=512)
    locked: bool


class ModerationActionRead(BaseModel):
    id: int
    created_at: datetime
    action: str
    reason: str | None
    comment_id: int | None
    thread_id: int | None
    moderator: CommunityUserRead | None = None
    target: CommunityUserRead | None = None

    model_config = {"from_attributes": True}
