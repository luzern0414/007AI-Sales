"""Prioritize user-requested project analysis and meeting work."""
from alembic import op
import sqlalchemy as sa
revision='f932ab63d510'
down_revision='e825af391c42'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('analysis_jobs',sa.Column('priority',sa.Integer(),nullable=False,server_default='0'))
    op.execute("UPDATE analysis_jobs SET priority=20 WHERE kind='meeting'")


def downgrade():
    op.drop_column('analysis_jobs','priority')
