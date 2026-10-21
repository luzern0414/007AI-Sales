"""Human workflow confirmations, project analysis and imported recording links."""
from alembic import op
revision = 'e825af391c42'
down_revision = 'd7413a9c8e20'
branch_labels = None
depends_on = None


def upgrade():
    from server.db import WorkflowNode, ProjectAnalysis, ImportedRecording
    for table in (WorkflowNode.__table__, ProjectAnalysis.__table__, ImportedRecording.__table__):
        table.create(bind=op.get_bind())


def downgrade():
    raise RuntimeError('节点确认和录音关联请从备份恢复')
