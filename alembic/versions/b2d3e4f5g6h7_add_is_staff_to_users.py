"""add is_staff to users

Revision ID: b2d3e4f5g6h7
Revises: a1c2d3e4f5g6
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d3e4f5g6h7'
down_revision: Union[str, None] = 'a1c2d3e4f5g6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_staff', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('users', 'is_staff', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'is_staff')
