"""File provenance and daily development evidence."""
from alembic import op
import sqlalchemy as sa
revision='fb285c830d22'
down_revision='fa184b729c11'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('files',sa.Column('origin',sa.String(20),nullable=False,server_default='unknown'))
    op.execute("UPDATE files SET origin='client' WHERE name LIKE '%客户提供%' OR name LIKE '%甲方提供%'")
    op.execute("UPDATE files SET origin='ours' WHERE name LIKE '%我方提供%' OR name LIKE '%乙方提供%' OR name LIKE '%我方方案%' OR name LIKE '%我方报价%'")
    from server.db import DevelopmentDay
    DevelopmentDay.__table__.create(bind=op.get_bind(),checkfirst=True)

def downgrade():
    raise RuntimeError('来源及开发进度记录请从备份恢复')
