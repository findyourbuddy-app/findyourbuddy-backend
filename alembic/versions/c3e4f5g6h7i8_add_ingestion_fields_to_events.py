"""add ingestion fields to events

Revision ID: c3e4f5g6h7i8
Revises: b2d3e4f5g6h7
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e4f5g6h7i8'
down_revision: Union[str, None] = 'b2d3e4f5g6h7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('source', sa.String(length=50), nullable=True))
    op.add_column('events', sa.Column('external_id', sa.String(length=255), nullable=True))
    op.add_column('events', sa.Column('source_url', sa.String(length=500), nullable=True))
    op.alter_column('events', 'creator_id', existing_type=sa.Integer(), nullable=True)
    op.create_unique_constraint('uq_events_source_external_id', 'events', ['source', 'external_id'])


def downgrade() -> None:
    op.drop_constraint('uq_events_source_external_id', 'events', type_='unique')
    op.alter_column('events', 'creator_id', existing_type=sa.Integer(), nullable=False)
    op.drop_column('events', 'source_url')
    op.drop_column('events', 'external_id')
    op.drop_column('events', 'source')
