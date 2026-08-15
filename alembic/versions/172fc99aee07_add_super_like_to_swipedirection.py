"""add super_like to swipedirection enum

Revision ID: 172fc99aee07
Revises: e3efa8daeaae
Create Date: 2026-08-15 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '172fc99aee07'
down_revision: Union[str, None] = 'e3efa8daeaae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE swipedirection ADD VALUE IF NOT EXISTS 'SUPER_LIKE'")


def downgrade() -> None:
    # Postgres does not support removing enum values; downgrade is a no-op.
    pass
