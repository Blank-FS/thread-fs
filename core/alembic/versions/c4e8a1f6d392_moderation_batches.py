"""moderation batches

Revision ID: c4e8a1f6d392
Revises: b7f2d4e81c05
Create Date: 2026-11-07 15:06:52.740913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a1f6d392'
down_revision: Union[str, Sequence[str], None] = 'b7f2d4e81c05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('moderation_batches',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('community_id', sa.UUID(), nullable=False),
    sa.Column('moderator_community_user_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=16), nullable=False),
    sa.Column('comment_count', sa.Integer(), nullable=False),
    sa.Column('counts_toward_limit', sa.Boolean(), nullable=False),
    sa.Column('undone_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('undone_by_community_user_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['moderator_community_user_id'], ['community_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['undone_by_community_user_id'], ['community_users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_moderation_batches_moderator_created_at', 'moderation_batches', ['moderator_community_user_id', 'created_at'], unique=False)
    op.add_column('moderation_actions', sa.Column('batch_id', sa.UUID(), nullable=True))
    op.add_column('moderation_actions', sa.Column('previous_removal_reason', sa.String(length=128), nullable=True))
    op.add_column('moderation_actions', sa.Column('previous_removal_detail', sa.String(length=200), nullable=True))
    op.create_foreign_key('moderation_actions_batch_id_fkey', 'moderation_actions', 'moderation_batches', ['batch_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_moderation_actions_batch_id', 'moderation_actions', ['batch_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_moderation_actions_batch_id', table_name='moderation_actions')
    op.drop_constraint('moderation_actions_batch_id_fkey', 'moderation_actions', type_='foreignkey')
    op.drop_column('moderation_actions', 'previous_removal_detail')
    op.drop_column('moderation_actions', 'previous_removal_reason')
    op.drop_column('moderation_actions', 'batch_id')
    op.drop_index('ix_moderation_batches_moderator_created_at', table_name='moderation_batches')
    op.drop_table('moderation_batches')
