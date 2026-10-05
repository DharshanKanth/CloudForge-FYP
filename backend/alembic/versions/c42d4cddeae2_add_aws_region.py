"""add_aws_region

Revision ID: c42d4cddeae2
Revises: ee0805e562a5
Create Date: 2026-09-05 11:20:35.215495
"""

from alembic import op
import sqlalchemy as sa

revision = 'c42d4cddeae2'
down_revision = 'ee0805e562a5'


def upgrade():
    op.add_column('architectures', sa.Column('aws_region', sa.String(), server_default='us-east-1', nullable=False))


def downgrade():
    op.drop_column('architectures', 'aws_region')
