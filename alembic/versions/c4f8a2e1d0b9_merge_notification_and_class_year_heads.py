"""merge notification-columns and class-year migration heads

The chain forked at f1a9c3d7b2e4 into two independent branches:
  - a1b2c3d4e5f6 -> ... -> e5f6a7b8c9d0  (user profile: firebase_uid, class_year, ...)
  - a3c1e8f92b05 -> b3d4e5f6a7b8         (swipe index + missing notification columns)
With two heads, `alembic upgrade head` fails. This merge rejoins them so a
single `alembic upgrade head` applies both branches.

Revision ID: c4f8a2e1d0b9
Revises: e5f6a7b8c9d0, b3d4e5f6a7b8
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

revision: str = 'c4f8a2e1d0b9'
down_revision: Union[str, Sequence[str], None] = ('e5f6a7b8c9d0', 'b3d4e5f6a7b8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
