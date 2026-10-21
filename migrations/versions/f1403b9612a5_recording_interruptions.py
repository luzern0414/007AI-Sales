"""Retain observed recording interruptions separately from saved samples."""
from alembic import op
import sqlalchemy as sa

revision='f1403b9612a5'
down_revision='c727e76c4f31'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('capture_epochs',sa.Column('interruption_kind',sa.String(40),nullable=True))
    op.add_column('capture_epochs',sa.Column('interruption_detected_at',sa.String(40),nullable=True))


def downgrade():
    op.drop_column('capture_epochs','interruption_detected_at')
    op.drop_column('capture_epochs','interruption_kind')
