"""add trust score tracking columns

Revision ID: f1a9c3d7b2e4
Revises: b2577480ae3a
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a9c3d7b2e4'
down_revision: Union[str, None] = 'b2577480ae3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('event_attendances', sa.Column('no_show_penalized_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('trust_score_low_since', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'trust_score_low_since')
    op.drop_column('event_attendances', 'no_show_penalized_at')
