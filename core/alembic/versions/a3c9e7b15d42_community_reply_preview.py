"""community reply preview

Revision ID: a3c9e7b15d42
Revises: d8b2e5c4f617
Create Date: 2026-11-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c9e7b15d42'
down_revision: Union[str, Sequence[str], None] = 'd8b2e5c4f617'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('communities', sa.Column('reply_preview', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('communities', 'reply_preview')
