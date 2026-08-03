"""REM-9: FK/index parity for create_all bootstrap DBs

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-03 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_fk(insp: sa.Inspector, table: str, column: str) -> bool:
    for fk in insp.get_foreign_keys(table):
        if column in (fk.get("constrained_columns") or []):
            return True
    return False


def _has_index(insp: sa.Inspector, table: str, name: str) -> bool:
    return any(ix.get("name") == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "approval_entries" in tables and not _has_fk(insp, "approval_entries", "rule_id"):
        op.create_foreign_key(
            "fk_approval_entries_rule_id",
            "approval_entries",
            "approval_rules",
            ["rule_id"],
            ["id"],
            ondelete="CASCADE",
        )

    if "odoo_connections" in tables:
        cols = {c["name"] for c in insp.get_columns("odoo_connections")}
        if "workspace_id" in cols:
            if not _has_fk(insp, "odoo_connections", "workspace_id"):
                op.create_foreign_key(
                    "fk_odoo_connections_workspace_id",
                    "odoo_connections",
                    "workspaces",
                    ["workspace_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
            if not _has_index(insp, "odoo_connections", "ix_odoo_connections_workspace_id"):
                op.create_index(
                    "ix_odoo_connections_workspace_id",
                    "odoo_connections",
                    ["workspace_id"],
                )

    if "customization_projects" in tables:
        cols = {c["name"] for c in insp.get_columns("customization_projects")}
        if "workspace_id" in cols:
            if not _has_fk(insp, "customization_projects", "workspace_id"):
                op.create_foreign_key(
                    "fk_customization_projects_workspace_id",
                    "customization_projects",
                    "workspaces",
                    ["workspace_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
            if not _has_index(insp, "customization_projects", "ix_customization_projects_workspace_id"):
                op.create_index(
                    "ix_customization_projects_workspace_id",
                    "customization_projects",
                    ["workspace_id"],
                )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "customization_projects" in tables:
        if _has_index(insp, "customization_projects", "ix_customization_projects_workspace_id"):
            op.drop_index("ix_customization_projects_workspace_id", "customization_projects")
        if _has_fk(insp, "customization_projects", "workspace_id"):
            op.drop_constraint("fk_customization_projects_workspace_id", "customization_projects", type_="foreignkey")

    if "odoo_connections" in tables:
        if _has_index(insp, "odoo_connections", "ix_odoo_connections_workspace_id"):
            op.drop_index("ix_odoo_connections_workspace_id", "odoo_connections")
        if _has_fk(insp, "odoo_connections", "workspace_id"):
            op.drop_constraint("fk_odoo_connections_workspace_id", "odoo_connections", type_="foreignkey")

    if "approval_entries" in tables and _has_fk(insp, "approval_entries", "rule_id"):
        op.drop_constraint("fk_approval_entries_rule_id", "approval_entries", type_="foreignkey")
