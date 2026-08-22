"""add index on events.creator_id

Revision ID: d1e2f3a4b5c6
Revises: c9d8e7f6a5b4
Create Date: 2026-08-22 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c9d8e7f6a5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_events_creator_id', 'events', ['creator_id'])


def downgrade() -> None:
    op.drop_index('ix_events_creator_id', table_name='events')
