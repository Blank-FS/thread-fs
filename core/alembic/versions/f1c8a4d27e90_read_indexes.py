"""read indexes

Revision ID: f1c8a4d27e90
Revises: b4d8f2a6c391
Create Date: 2026-11-24 15:40:00.000000

Indexes for the lookups every request makes: a signed-in viewer by their identity, and a thread's top-level comments.
The identity one is unique, so two first requests at once can't create the same user twice; any such duplicates are
merged into the earliest first.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1c8a4d27e90'
down_revision: Union[str, Sequence[str], None] = 'b4d8f2a6c391'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every column that points at community_users
REFERENCES = [
    ("comments", "community_user_id"),
    ("comments", "deleted_by_user_id"),
    ("comment_votes", "community_user_id"),
    ("comment_reports", "reporter_community_user_id"),
    ("comment_reports", "resolved_by_community_user_id"),
    ("community_bans", "community_user_id"),
    ("community_bans", "banned_by_community_user_id"),
    ("community_bans", "lifted_by_community_user_id"),
    ("community_user_notes", "community_user_id"),
    ("community_user_notes", "author_community_user_id"),
    ("moderation_actions", "moderator_community_user_id"),
    ("moderation_actions", "target_community_user_id"),
    ("moderation_batches", "moderator_community_user_id"),
    ("moderation_batches", "undone_by_community_user_id"),
]
# One vote and one report a person on each comment: of two, the first stays
ONE_EACH = [("comment_votes", "community_user_id"), ("comment_reports", "reporter_community_user_id")]


def _merge_duplicate_users() -> None:
    op.execute("""
        CREATE TEMPORARY TABLE duplicate_users ON COMMIT DROP AS
        SELECT id, keep FROM (
            SELECT id, first_value(id) OVER (
                PARTITION BY community_id, identity_provider, external_user_id ORDER BY created_at, id
            ) AS keep
            FROM community_users
        ) ranked WHERE id <> keep
    """)
    if not op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM duplicate_users)")).scalar():
        return
    for table, column in ONE_EACH:
        op.execute(f"""
            DELETE FROM {table} WHERE id IN (
                SELECT id FROM (
                    SELECT t.id, row_number() OVER (
                        PARTITION BY t.comment_id, coalesce(d.keep, t.{column}) ORDER BY t.id
                    ) AS n
                    FROM {table} t LEFT JOIN duplicate_users d ON d.id = t.{column}
                    WHERE t.{column} IS NOT NULL
                ) ranked WHERE n > 1
            )
        """)
    for table, column in REFERENCES:
        op.execute(f"UPDATE {table} SET {column} = d.keep FROM duplicate_users d WHERE {table}.{column} = d.id")
    op.execute("DELETE FROM community_users WHERE id IN (SELECT id FROM duplicate_users)")
    # The counts of the comments whose second vote went
    op.execute("""
        UPDATE comments SET
            upvote_count = (SELECT count(*) FROM comment_votes v WHERE v.comment_id = comments.id AND v.value = 1),
            downvote_count = (SELECT count(*) FROM comment_votes v WHERE v.comment_id = comments.id AND v.value = -1)
        WHERE status <> 'deleted' AND id IN (
            SELECT v.comment_id FROM comment_votes v JOIN duplicate_users d ON d.keep = v.community_user_id
        )
    """)


def upgrade() -> None:
    """Upgrade schema."""
    _merge_duplicate_users()
    op.create_index(
        'uq_community_users_identity',
        'community_users',
        ['community_id', 'identity_provider', 'external_user_id'],
        unique=True,
    )
    op.create_index(
        'ix_comments_thread_top_level',
        'comments',
        ['thread_id', sa.text('created_at DESC'), sa.text('id DESC')],
        postgresql_where=sa.text('parent_comment_id IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_comments_thread_top_level', table_name='comments')
    op.drop_index('uq_community_users_identity', table_name='community_users')
