"""Accumulated AI project insight: stage judgement, reasoning and suggested actions."""
from alembic import op
import sqlalchemy as sa
revision='a9c41e7d2b10'
down_revision='fb285c830d22'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('project_analysis',sa.Column('insight_json',sa.Text(),nullable=False,server_default='{}'))

def downgrade():
    op.drop_column('project_analysis','insight_json')
