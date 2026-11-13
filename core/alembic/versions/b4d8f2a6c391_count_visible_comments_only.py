"""count visible comments only

Revision ID: b4d8f2a6c391
Revises: a3c9e7b15d42
Create Date: 2026-11-13 14:00:00.000000

A comment's reply_count and a thread's comment_count now count visible comments only, so a deleted or removed comment
with nothing visible below it can leave the thread. Recomputed here from the comments themselves; from now on they're
kept up to date on every delete, removal and restore.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b4d8f2a6c391'
down_revision: Union[str, Sequence[str], None] = 'a3c9e7b15d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _recount(counted: str) -> None:
    # Every (ancestor, descendant) pair, then each ancestor's count of the descendants that count
    op.execute("UPDATE comments SET reply_count = 0")
    op.execute(f"""
        WITH RECURSIVE pairs(ancestor_id, descendant_id) AS (
            SELECT parent_comment_id, id FROM comments WHERE parent_comment_id IS NOT NULL
            UNION ALL
            SELECT c.parent_comment_id, p.descendant_id
            FROM pairs p JOIN comments c ON c.id = p.ancestor_id
            WHERE c.parent_comment_id IS NOT NULL
        )
        UPDATE comments SET reply_count = counts.n
        FROM (
            SELECT p.ancestor_id, count(*) AS n
            FROM pairs p JOIN comments d ON d.id = p.descendant_id
            WHERE {counted}
            GROUP BY p.ancestor_id
        ) counts
        WHERE comments.id = counts.ancestor_id
    """)
    op.execute(f"""
        UPDATE threads SET comment_count = (
            SELECT count(*) FROM comments d WHERE d.thread_id = threads.id AND {counted}
        )
    """)


def upgrade() -> None:
    """Upgrade schema."""
    _recount("d.status = 'visible'")


def downgrade() -> None:
    """Downgrade schema."""
    # Back to counting every comment ever posted
    _recount("TRUE")
