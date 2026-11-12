"""webhooks

Revision ID: f3a7c2d94b18
Revises: e5b3f8a2c917
Create Date: 2026-11-11 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f3a7c2d94b18'
down_revision: Union[str, Sequence[str], None] = 'e5b3f8a2c917'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'community_webhooks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('community_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('secret', sa.String(length=255), nullable=False),
        sa.Column('events', sa.String(length=512), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_community_webhooks_community_id', 'community_webhooks', ['community_id'])

    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('webhook_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_error', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['webhook_id'], ['community_webhooks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webhook_deliveries_due', 'webhook_deliveries', ['status', 'next_attempt_at'])
    op.create_index('ix_webhook_deliveries_webhook_id', 'webhook_deliveries', ['webhook_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_webhook_deliveries_webhook_id', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_due', table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')
    op.drop_index('ix_community_webhooks_community_id', table_name='community_webhooks')
    op.drop_table('community_webhooks')
