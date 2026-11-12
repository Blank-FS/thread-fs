# app/schemas/embed.py

from datetime import datetime
from uuid import UUID
from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    limit: int
    offset: int
    next_offset: int | None
    has_more: bool
    total: int | None = None


class ReasonRead(BaseModel):
    key: str
    label: str

    model_config = {"from_attributes": True}


class EmbedCommunityConfigRead(BaseModel):
    community_id: UUID
    name: str
    slug: str
    allow_anonymous_read: bool = True
    allow_anonymous_comment: bool = False
    report_reasons: list[ReasonRead] = []
    # Where the community's comment rules are; the widget's Rules button links there
    rules_url: str | None = None


class ResolveThreadRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=512)
    title: str | None = Field(default=None, max_length=512)
    source_url: str | None = Field(default=None, max_length=2048)


class ThreadRead(BaseModel):
    id: int
    community_id: UUID
    unique_id: str
    title: str | None
    source_url: str | None
    comment_count: int
    is_locked: bool
    is_deleted: bool
    created_at: datetime
    modified_at: datetime

    model_config = {"from_attributes": True}


class ResolveThreadResponse(BaseModel):
    exists: bool
    thread: ThreadRead | None = None


class EmbedMeRead(BaseModel):
    authenticated: bool
    community_user_id: UUID | None = None
    identity_provider: str | None = None
    external_user_id: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    avatar_frame_url: str | None = None
    threadfs_user_id: UUID | None = None
    staff_role: str | None = None


class ExternalIdentityPayload(BaseModel):
    sub: str
    name: str | None = None
    avatar_url: str | None = None
    iss: str
    aud: str | None = None
    typ: str | None = None


class CommentCreateRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=512)
    title: str | None = Field(default=None, max_length=512)
    source_url: str | None = Field(default=None, max_length=2048)

    content: str = Field(min_length=1, max_length=10_000)
    parent_comment_id: int | None = None

    # Where it's posted from, for moderation: a site or app slug, and the kind of client
    source: str | None = Field(default=None, max_length=255)
    client: str | None = Field(default=None, max_length=32)


class VoteRequest(BaseModel):
    # 1 = upvote, -1 = downvote, 0 = remove current vote
    value: int = Field(ge=-1, le=1)


class CommentUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)


class CommunityUserRead(BaseModel):
    id: UUID
    identity_provider: str
    external_user_id: str
    display_name: str | None
    avatar_url: str | None
    avatar_frame_url: str | None = None

    model_config = {"from_attributes": True}


class CommentRead(BaseModel):
    id: int
    thread_id: int
    parent_comment_id: int | None
    # Both empty on a comment moderators removed, unless the viewer wrote it
    community_user_id: UUID | None

    community_user: CommunityUserRead | None = None

    content: str
    status: str
    # Why moderators removed it: only its author gets this
    removal_reason: str | None = None
    removal_detail: str | None = None

    upvote_count: int
    downvote_count: int
    reply_count: int
    viewer_vote: int | None = None

    edited_at: datetime | None = None
    deleted_at: datetime | None = None

    created_at: datetime
    modified_at: datetime

    model_config = {"from_attributes": True}


class CommentTreeRead(CommentRead):
    """A comment with some of its replies loaded, as the context endpoint returns them."""

    replies: list["CommentTreeRead"] = []
    replies_next_offset: int | None = None
    replies_has_more: bool = False
    # How many direct replies it has, so "N more replies" can be shown (reply_count counts every level below)
    replies_total: int | None = None


class CommentContextRead(BaseModel):
    """One comment in context, for a link to it: its top-level comment, then each reply down to it, one per level, with
    the comment's own first page of replies. Siblings along the way are left out; an ancestor that has them says so
    (replies_has_more, from offset 0), so they can be loaded, skipping the reply already shown."""

    focused_comment_id: int
    root: CommentTreeRead


class ReportRequest(BaseModel):
    # A key from the community's reasons
    reason: str = Field(min_length=1, max_length=64)
    details: str | None = Field(default=None, max_length=100)


class CommentWithThreadRead(CommentRead):
    thread: ThreadRead | None = None
