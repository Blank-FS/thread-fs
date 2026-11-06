"""comment removal detail

Revision ID: 9e4d1c7a2b63
Revises: 7c1f2ab94e10
Create Date: 2026-11-06 09:20:11.402817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e4d1c7a2b63'
down_revision: Union[str, Sequence[str], None] = '7c1f2ab94e10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('comments', sa.Column('removal_detail', sa.String(length=200), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('comments', 'removal_detail')
