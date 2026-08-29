"""drop orphan phone_verification_codes table

Created by a35bf0b0b4ec for a backend-issued SMS OTP flow that was never built.
Phone verification is handled by Firebase now (/auth/firebase-login), and no
model, service or router references this table. The users.phone_number /
users.phone_verified columns from that same migration stay -- they are in use.

Revision ID: e6b0c4a3f2d1
Revises: d5a9b3f2e1c0
Create Date: 2026-08-28 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6b0c4a3f2d1'
down_revision: Union[str, None] = 'd5a9b3f2e1c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF EXISTS: a DB bootstrapped from Base.metadata.create_all never had this
    # table (there is no model for it), only alembic-migrated DBs do.
    op.execute("DROP TABLE IF EXISTS phone_verification_codes")


def downgrade() -> None:
    op.create_table(
        'phone_verification_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=6), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_phone_verification_codes_user_id'),
        'phone_verification_codes',
        ['user_id'],
        unique=False,
    )
