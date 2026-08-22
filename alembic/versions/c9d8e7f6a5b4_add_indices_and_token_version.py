"""add FK indices, user.is_active index, and token_version for refresh rotation

Revision ID: c9d8e7f6a5b4
Revises: b1c2d3e4f5g6
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c9d8e7f6a5b4'
down_revision: Union[str, None] = 'b1c2d3e4f5g6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Refresh token rotation support
    op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))

    # FK indices on matches
    op.create_index('ix_matches_user_a_id', 'matches', ['user_a_id'])
    op.create_index('ix_matches_user_b_id', 'matches', ['user_b_id'])

    # FK indices on swipes
    op.create_index('ix_swipes_target_id', 'swipes', ['target_id'])
    op.create_index('ix_swipes_event_id', 'swipes', ['event_id'])

    # FK index on messages
    op.create_index('ix_messages_sender_id', 'messages', ['sender_id'])

    # FK index on blocks
    op.create_index('ix_blocks_blocked_id', 'blocks', ['blocked_id'])

    # User filter indices
    op.create_index('ix_users_is_active', 'users', ['is_active'])
    op.create_index('ix_users_referred_by_id', 'users', ['referred_by_id'])


def downgrade() -> None:
    op.drop_index('ix_users_referred_by_id', table_name='users')
    op.drop_index('ix_users_is_active', table_name='users')
    op.drop_index('ix_blocks_blocked_id', table_name='blocks')
    op.drop_index('ix_messages_sender_id', table_name='messages')
    op.drop_index('ix_swipes_event_id', table_name='swipes')
    op.drop_index('ix_swipes_target_id', table_name='swipes')
    op.drop_index('ix_matches_user_b_id', table_name='matches')
    op.drop_index('ix_matches_user_a_id', table_name='matches')
    op.drop_column('users', 'token_version')
