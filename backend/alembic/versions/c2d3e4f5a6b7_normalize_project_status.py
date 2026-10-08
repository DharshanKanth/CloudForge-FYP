"""normalize project status to the deployment state machine

Revision ID: c2d3e4f5a6b7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-08

Maps legacy status values onto the new lifecycle states:
saved -> draft, planned -> ready, destroy_planned/plan-destroy -> deployed.
No schema change.
"""

from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE projects SET status = 'draft' WHERE status = 'saved'")
    op.execute("UPDATE projects SET status = 'ready' WHERE status = 'planned'")
    op.execute(
        "UPDATE projects SET status = 'deployed' "
        "WHERE status IN ('destroy_planned', 'plan-destroy')"
    )


def downgrade():
    op.execute("UPDATE projects SET status = 'saved' WHERE status = 'draft'")
    op.execute("UPDATE projects SET status = 'planned' WHERE status = 'ready'")
