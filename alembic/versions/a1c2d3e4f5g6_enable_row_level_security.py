"""enable row level security

Revision ID: a1c2d3e4f5g6
Revises: 0b7492e3213e
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1c2d3e4f5g6'
down_revision: Union[str, None] = '0b7492e3213e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ['users', 'swipes', 'matches', 'messages', 'events', 'blocks', 'reports']


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
