"""autogenerate initial (fresh)

Revision ID: ee0805e562a5
Revises: 
Create Date: 2026-09-01 21:57:50.979541
"""

from alembic import op
import sqlalchemy as sa

revision = 'ee0805e562a5'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
    )
    # Model uses Column(unique=True, index=True): SQLAlchemy emits a unique
    # INDEX (ix_users_email), not a unique constraint.
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'projects',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('provider', sa.String(), nullable=False, server_default='aws'),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    op.create_table(
        'architectures',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id'), nullable=False, unique=True),
        sa.Column('nodes', sa.JSON(), nullable=False),
        sa.Column('edges', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

def downgrade():
    op.drop_table('architectures')
    op.drop_table('projects')
    op.drop_table('users')
