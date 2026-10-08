"""add cloud_accounts

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-10-08

Per-user connected cloud accounts. Credentials are stored encrypted (Fernet)
in ``encrypted_credentials`` and are never returned by the API.
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "cloud_accounts" in set(inspector.get_table_names()):
        return

    op.create_table(
        "cloud_accounts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="aws"),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("region", sa.String(), nullable=False, server_default="us-east-1"),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_cloud_accounts_user_id", "cloud_accounts", ["user_id"])
    op.create_unique_constraint(
        "uq_cloud_accounts_user_name", "cloud_accounts", ["user_id", "name"]
    )


def downgrade():
    op.drop_index("ix_cloud_accounts_user_id", table_name="cloud_accounts")
    op.drop_table("cloud_accounts")
