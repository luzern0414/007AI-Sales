"""Claim first administrator once across concurrent requests."""
from alembic import op
import sqlalchemy as sa

revision='76a6a3b5ba10'
down_revision='3065a635a3f6'
branch_labels=None
depends_on=None


def upgrade():
    table=op.create_table('initialization',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('created_at',sa.String(40),nullable=False))
    from server.db import now
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT id FROM users LIMIT 1')).first():
        bind.execute(table.insert().values(id=1,created_at=now()))


def downgrade():
    op.drop_table('initialization')
