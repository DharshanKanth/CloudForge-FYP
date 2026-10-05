"""add deployment_events and align architectures JSON columns with JSONB

Revision ID: f1a2b3c4d5e6
Revises: c42d4cddeae2
Create Date: 2026-10-05

The ORM declares ``nodes``/``edges`` as JSONB, but the initial migration used
generic ``sa.JSON``. This migration brings a migration-created database in line
with the models and adds the ``deployment_events`` audit table.

It is intentionally idempotent: databases created by the old
``Base.metadata.create_all`` startup already contain these objects, so each step
is guarded by an inspector check. That lets Alembic adopt a pre-existing
database without a manual ``stamp``.
"""

from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "c42d4cddeae2"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "deployment_events" not in set(inspector.get_table_names()):
        op.create_table(
            "deployment_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False, server_default=""),
            sa.Column("resource_count", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index(
            "ix_deployment_events_project_time",
            "deployment_events",
            ["project_id", "created_at"],
        )

    if bind.dialect.name == "postgresql":
        column_types = {
            c["name"]: str(c["type"]).upper()
            for c in inspector.get_columns("architectures")
        }
        if column_types.get("nodes") != "JSONB":
            op.execute(
                "ALTER TABLE architectures ALTER COLUMN nodes TYPE jsonb USING nodes::jsonb"
            )
        if column_types.get("edges") != "JSONB":
            op.execute(
                "ALTER TABLE architectures ALTER COLUMN edges TYPE jsonb USING edges::jsonb"
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "deployment_events" in set(inspector.get_table_names()):
        op.drop_index("ix_deployment_events_project_time", table_name="deployment_events")
        op.drop_table("deployment_events")

    if bind.dialect.name == "postgresql":
        column_types = {
            c["name"]: str(c["type"]).upper()
            for c in inspector.get_columns("architectures")
        }
        if column_types.get("nodes") == "JSONB":
            op.execute("ALTER TABLE architectures ALTER COLUMN nodes TYPE json USING nodes::json")
        if column_types.get("edges") == "JSONB":
            op.execute("ALTER TABLE architectures ALTER COLUMN edges TYPE json USING edges::json")
