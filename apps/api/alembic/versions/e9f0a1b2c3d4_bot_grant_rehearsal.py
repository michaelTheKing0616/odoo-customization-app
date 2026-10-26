"""NF BOT-CLONE-REHEARSAL: approval grants bind the rehearsal id

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-10-25 21:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e9f0a1b2c3d4"
down_revision: str | Sequence[str] | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bot_grant", sa.Column("rehearsal_id", sa.String(64), nullable=True))
    # NOT VALID: rows issued before this revision stay readable; every new grant must bind one.
    op.execute(
        "ALTER TABLE bot_grant ADD CONSTRAINT ck_bot_grant_rehearsal"
        " CHECK (rehearsal_id IS NOT NULL AND length(rehearsal_id) > 0) NOT VALID"
    )


def downgrade() -> None:
    op.drop_constraint("ck_bot_grant_rehearsal", "bot_grant", type_="check")
    op.drop_column("bot_grant", "rehearsal_id")
