"""add deployments and deployment_logs

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-10-08

Async deployment jobs and their streamed log lines, executed by the isolated
Terraform worker.
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "deployments" not in tables:
        op.create_table(
            "deployments",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("operation", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="queued"),
            sa.Column("step", sa.String(), nullable=True),
            sa.Column("output_tail", sa.Text(), nullable=False, server_default=""),
            sa.Column("resource_count", sa.Integer(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_deployments_project_id", "deployments", ["project_id"])

    if "deployment_logs" not in tables:
        op.create_table(
            "deployment_logs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deployment_id", sa.String(), sa.ForeignKey("deployments.id"), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_deployment_logs_deployment_id", "deployment_logs", ["deployment_id"])
        op.create_index(
            "ix_deployment_logs_deployment_seq", "deployment_logs", ["deployment_id", "seq"]
        )


def downgrade():
    op.drop_index("ix_deployment_logs_deployment_seq", table_name="deployment_logs")
    op.drop_index("ix_deployment_logs_deployment_id", table_name="deployment_logs")
    op.drop_table("deployment_logs")
    op.drop_index("ix_deployments_project_id", table_name="deployments")
    op.drop_table("deployments")
