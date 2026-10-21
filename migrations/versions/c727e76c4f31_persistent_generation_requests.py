"""Persist bounded model requests and prevent duplicate generation."""
from alembic import op
import sqlalchemy as sa

revision='c727e76c4f31'
down_revision='76a6a3b5ba10'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('generation_jobs',sa.Column('id',sa.String(32),primary_key=True),sa.Column('meeting_id',sa.String(32),sa.ForeignKey('meetings.id'),nullable=False),sa.Column('request_id',sa.String(100),nullable=False),sa.Column('input_hash',sa.String(64),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('document_ids',sa.Text(),nullable=False),sa.Column('error',sa.String(500),nullable=False),sa.Column('error_status',sa.Integer(),nullable=False),sa.Column('created_at',sa.String(40),nullable=False),sa.Column('finished_at',sa.String(40),nullable=True),sa.UniqueConstraint('meeting_id','request_id'))
    op.create_index('ix_generation_jobs_meeting_id','generation_jobs',['meeting_id'])
    op.create_index('uq_running_generation','generation_jobs',['meeting_id'],unique=True,sqlite_where=sa.text("status = 'running'"),postgresql_where=sa.text("status = 'running'"))


def downgrade():
    op.drop_index('uq_running_generation',table_name='generation_jobs')
    op.drop_index('ix_generation_jobs_meeting_id',table_name='generation_jobs')
    op.drop_table('generation_jobs')
