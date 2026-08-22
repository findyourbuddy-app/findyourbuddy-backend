"""add hidden_fields and firebase_uid to users

Revision ID: a1b2c3d4e5f6
Revises: f1a9c3d7b2e4
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f1a9c3d7b2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS hidden_fields JSON NOT NULL DEFAULT '[]'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(128)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_firebase_uid ON users (firebase_uid)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_firebase_uid ON users (firebase_uid)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_firebase_uid")
    op.execute("DROP INDEX IF EXISTS uq_users_firebase_uid")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS firebase_uid")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS hidden_fields")
