"""community image hosts

Revision ID: c3f7a1e8d520
Revises: b6e2d9f41c83
Create Date: 2026-11-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3f7a1e8d520'
down_revision: Union[str, Sequence[str], None] = 'b6e2d9f41c83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'communities',
        sa.Column('image_hosts', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('communities', 'image_hosts')
