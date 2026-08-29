"""add composite index on swipes(swiper_id, event_id)

Revision ID: a3c1e8f92b05
Revises: f1a9c3d7b2e4
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a3c1e8f92b05'
down_revision: Union[str, None] = 'f1a9c3d7b2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_swipes_swiper_event', 'swipes', ['swiper_id', 'event_id'])


def downgrade() -> None:
    op.drop_index('ix_swipes_swiper_event', table_name='swipes')
