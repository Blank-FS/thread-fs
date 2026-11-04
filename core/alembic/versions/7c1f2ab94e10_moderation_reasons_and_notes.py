"""moderation reasons and notes

Revision ID: 7c1f2ab94e10
Revises: 43d545d05678
Create Date: 2026-11-04 10:12:41.318204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1f2ab94e10'
down_revision: Union[str, Sequence[str], None] = '43d545d05678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('community_reasons',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('community_id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('label', sa.String(length=128), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('community_id', 'key', name='uq_community_reasons_key')
    )
    op.create_table('community_user_notes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('community_id', sa.UUID(), nullable=False),
    sa.Column('community_user_id', sa.UUID(), nullable=False),
    sa.Column('author_community_user_id', sa.UUID(), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['author_community_user_id'], ['community_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['community_user_id'], ['community_users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_community_user_notes_user', 'community_user_notes', ['community_id', 'community_user_id'], unique=False)
    op.add_column('comment_reports', sa.Column('reason_label', sa.String(length=128), nullable=True))
    op.add_column('comments', sa.Column('removal_reason', sa.String(length=128), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('comments', 'removal_reason')
    op.drop_column('comment_reports', 'reason_label')
    op.drop_index('ix_community_user_notes_user', table_name='community_user_notes')
    op.drop_table('community_user_notes')
    op.drop_table('community_reasons')
