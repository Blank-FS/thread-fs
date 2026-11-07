"""community user avatar frame

Revision ID: e5b3f8a2c917
Revises: d1a9c7e35f20
Create Date: 2026-11-07 20:14:38.902611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b3f8a2c917'
down_revision: Union[str, Sequence[str], None] = 'd1a9c7e35f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('community_users', sa.Column('avatar_frame_url', sa.String(length=2048), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('community_users', 'avatar_frame_url')
