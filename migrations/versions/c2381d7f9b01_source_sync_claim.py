"""Fence overlapping source sync operations.

Revision ID: c2381d7f9b01
Revises: b74c193ae120
"""
from alembic import op
import sqlalchemy as sa
revision='c2381d7f9b01'
down_revision='b74c193ae120'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('source_links',sa.Column('sync_token',sa.String(32),nullable=True))
    op.add_column('source_links',sa.Column('sync_expires_at',sa.String(40),nullable=True))


def downgrade():
    with op.batch_alter_table('source_links') as batch:
        batch.drop_column('sync_expires_at')
        batch.drop_column('sync_token')
