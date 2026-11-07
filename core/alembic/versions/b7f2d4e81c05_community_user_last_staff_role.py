"""community user last staff role

Revision ID: b7f2d4e81c05
Revises: 9e4d1c7a2b63
Create Date: 2026-11-07 10:41:27.118306

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f2d4e81c05'
down_revision: Union[str, Sequence[str], None] = '9e4d1c7a2b63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('community_users', sa.Column('last_staff_role', sa.String(length=16), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('community_users', 'last_staff_role')
