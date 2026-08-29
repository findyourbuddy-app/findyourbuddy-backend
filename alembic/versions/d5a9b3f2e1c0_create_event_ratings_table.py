"""create event_ratings table

The EventRating model (app/models/event_rating.py) and the
POST /events/{id}/rating + GET /events/{id} endpoints were shipped without a
migration, so the table only ever existed in tests (Base.metadata.create_all).
This creates it for real deployments.

Revision ID: d5a9b3f2e1c0
Revises: c4f8a2e1d0b9
Create Date: 2026-08-28 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5a9b3f2e1c0'
down_revision: Union[str, None] = 'c4f8a2e1d0b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'event_ratings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'user_id', name='uq_event_ratings_event_user'),
    )
    op.create_index(op.f('ix_event_ratings_event_id'), 'event_ratings', ['event_id'], unique=False)
    op.create_index(op.f('ix_event_ratings_user_id'), 'event_ratings', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_event_ratings_user_id'), table_name='event_ratings')
    op.drop_index(op.f('ix_event_ratings_event_id'), table_name='event_ratings')
    op.drop_table('event_ratings')
