"""add missing notification columns (event_id, match_id, notification_type, data)

Revision ID: b3d4e5f6a7b8
Revises: a3c1e8f92b05
Create Date: 2026-08-27 02:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b3d4e5f6a7b8'
down_revision: Union[str, None] = 'a3c1e8f92b05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use IF NOT EXISTS: _auto_migrate_db may have already added
    # notification_type and data on older deployments.
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        conn.execute(sa.text(
            "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS event_id INTEGER REFERENCES events(id)"
        ))
        conn.execute(sa.text(
            "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS match_id INTEGER REFERENCES matches(id)"
        ))
        conn.execute(sa.text(
            "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS notification_type VARCHAR(50)"
        ))
        conn.execute(sa.text(
            "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS data JSON"
        ))
    else:
        # SQLite — only reached in edge-case testing against Alembic directly
        with op.batch_alter_table("notifications") as batch_op:
            for col, col_type in [
                ("event_id", sa.Integer()),
                ("match_id", sa.Integer()),
                ("notification_type", sa.String(50)),
                ("data", sa.JSON()),
            ]:
                try:
                    batch_op.add_column(sa.Column(col, col_type, nullable=True))
                except Exception:
                    pass


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        conn.execute(sa.text("ALTER TABLE notifications DROP COLUMN IF EXISTS data"))
        conn.execute(sa.text("ALTER TABLE notifications DROP COLUMN IF EXISTS notification_type"))
        conn.execute(sa.text("ALTER TABLE notifications DROP COLUMN IF EXISTS match_id"))
        conn.execute(sa.text("ALTER TABLE notifications DROP COLUMN IF EXISTS event_id"))
    else:
        with op.batch_alter_table("notifications") as batch_op:
            for col in ("data", "notification_type", "match_id", "event_id"):
                try:
                    batch_op.drop_column(col)
                except Exception:
                    pass
