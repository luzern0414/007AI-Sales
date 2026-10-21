"""Allow real final text without fabricated audio timestamps.

Revision ID: b74c193ae120
Revises: a631082fce20
"""
from alembic import op
import sqlalchemy as sa

revision='b74c193ae120'
down_revision='a631082fce20'
branch_labels=None
depends_on=None


def upgrade():
    with op.batch_alter_table('transcript_segments') as batch:
        batch.alter_column('begin_ms',existing_type=sa.Integer(),nullable=True)
        batch.alter_column('end_ms',existing_type=sa.Integer(),nullable=True)


def downgrade():
    connection=op.get_bind()
    if connection.scalar(sa.text('SELECT count(*) FROM transcript_segments WHERE begin_ms IS NULL OR end_ms IS NULL')):
        raise RuntimeError('Untimed transcripts exist; restore a backup rather than inventing timestamps')
    with op.batch_alter_table('transcript_segments') as batch:
        batch.alter_column('begin_ms',existing_type=sa.Integer(),nullable=False)
        batch.alter_column('end_ms',existing_type=sa.Integer(),nullable=False)
