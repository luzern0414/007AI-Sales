"""Retain each imported audio version with its associated transcript."""
from alembic import op
import sqlalchemy as sa

revision='fa184b729c11'
down_revision='f932ab63d510'
branch_labels=None
depends_on=None


def upgrade():
    inspector=sa.inspect(op.get_bind())
    if 'active' in {c['name'] for c in inspector.get_columns('imported_recordings')}:return
    with op.batch_alter_table('imported_recordings',naming_convention={'uq':'uq_%(table_name)s_%(column_0_name)s'}) as batch:
        batch.drop_constraint('uq_imported_recordings_meeting_id',type_='unique')
        batch.add_column(sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()))
        batch.add_column(sa.Column('transcript',sa.Text(),nullable=False,server_default=''))
        batch.add_column(sa.Column('summary',sa.Text(),nullable=False,server_default=''))
    op.create_index('uq_recording_active_meeting','imported_recordings',['meeting_id'],unique=True,sqlite_where=sa.text('active = 1'),postgresql_where=sa.text('active = true'))


def downgrade():
    raise RuntimeError('录音版本与转写历史请从备份恢复')
