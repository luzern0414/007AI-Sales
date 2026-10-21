"""Independent meetings, context jobs and project chronology."""
from alembic import op
import sqlalchemy as sa

revision='d7413a9c8e20'
down_revision='c2381d7f9b01'
branch_labels=None
depends_on=None


def upgrade():
    with op.batch_alter_table('projects') as b:
        b.add_column(sa.Column('directory_path',sa.Text(),nullable=True))
        b.create_unique_constraint('uq_projects_directory_path',['directory_path'])
    op.add_column('files',sa.Column('source_modified_at',sa.String(40),nullable=True))
    op.add_column('files',sa.Column('source_time_basis',sa.String(30),nullable=False,server_default='uploaded'))
    with op.batch_alter_table('meetings') as b:
        b.alter_column('project_id',existing_type=sa.String(32),nullable=True)
        b.add_column(sa.Column('owner_id',sa.String(32),nullable=True))
        b.create_foreign_key('fk_meetings_owner','users',['owner_id'],['id'])
        b.create_index('ix_meetings_owner_id',['owner_id'])
        b.add_column(sa.Column('analysis_status',sa.String(30),nullable=False,server_default='pending'))
        b.add_column(sa.Column('ai_summary',sa.Text(),nullable=False,server_default=''))
        b.add_column(sa.Column('title_locked',sa.Boolean(),nullable=False,server_default=sa.false()))
        b.add_column(sa.Column('classification_locked',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.execute('UPDATE meetings SET owner_id=(SELECT owner_id FROM projects WHERE projects.id=meetings.project_id)')
    from server.db import MeetingProject,NameEntry,AnalysisJob,ProjectProgress
    for table in (MeetingProject.__table__,NameEntry.__table__,AnalysisJob.__table__,ProjectProgress.__table__):
        table.create(bind=op.get_bind())
    op.execute("INSERT INTO meeting_projects(meeting_id,project_id,evidence,source) SELECT id,project_id,'','original' FROM meetings WHERE project_id IS NOT NULL")


def downgrade():
    raise RuntimeError('自动归档数据不可直接降级，请从备份恢复')
