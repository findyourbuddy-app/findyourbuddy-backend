"""make swipes.event_id and matches.event_id nullable

General-user browsing ("Genel Kullanıcılarda Gezin") records swipes with
event_id=NULL and can produce event-less matches. Both models were changed to
nullable=True but no migration followed, so on real deployments every
general-browse swipe hit a NOT NULL violation (500) and never recorded.

Revision ID: 19114ff9f179
Revises: e6b0c4a3f2d1
Create Date: 2026-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "19114ff9f179"
down_revision: Union[str, None] = "e6b0c4a3f2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE swipes ALTER COLUMN event_id DROP NOT NULL")
    op.execute("ALTER TABLE matches ALTER COLUMN event_id DROP NOT NULL")


def downgrade() -> None:
    op.execute("DELETE FROM swipes WHERE event_id IS NULL")
    op.execute("DELETE FROM matches WHERE event_id IS NULL")
    op.execute("ALTER TABLE swipes ALTER COLUMN event_id SET NOT NULL")
    op.execute("ALTER TABLE matches ALTER COLUMN event_id SET NOT NULL")
