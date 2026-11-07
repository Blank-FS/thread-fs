"""community moderator limits

Revision ID: d1a9c7e35f20
Revises: c4e8a1f6d392
Create Date: 2026-11-07 18:22:13.506744

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1a9c7e35f20'
down_revision: Union[str, Sequence[str], None] = 'c4e8a1f6d392'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('communities', sa.Column('max_batch_size', sa.Integer(), server_default='50', nullable=False))
    op.add_column('communities', sa.Column('max_daily_batch_changes', sa.Integer(), server_default='200', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('communities', 'max_daily_batch_changes')
    op.drop_column('communities', 'max_batch_size')
