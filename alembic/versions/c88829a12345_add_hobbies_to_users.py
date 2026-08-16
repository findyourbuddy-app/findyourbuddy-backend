"""add_hobbies_to_users

Revision ID: c88829a12345
Revises: b7b3405aa14e
Create Date: 2026-08-16 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c88829a12345'
down_revision: Union[str, None] = 'e2a0ed9ae01e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('hobbies', sa.JSON(), nullable=True, server_default='[]'))


def downgrade() -> None:
    op.drop_column('users', 'hobbies')
