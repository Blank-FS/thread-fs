"""gifs

Revision ID: b6e2d9f41c83
Revises: a8d41c6e2f57
Create Date: 2026-11-12 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b6e2d9f41c83'
down_revision: Union[str, Sequence[str], None] = 'a8d41c6e2f57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('communities', sa.Column('klipy_app_key', sa.String(length=255), nullable=True))
    op.add_column('comments', sa.Column('gif', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('comments', 'gif')
    op.drop_column('communities', 'klipy_app_key')
