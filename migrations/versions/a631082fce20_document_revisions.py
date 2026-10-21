"""Keep document revisions and their frozen source evidence immutable."""
from alembic import op
import sqlalchemy as sa

revision='a631082fce20'
down_revision='f1403b9612a5'
branch_labels=None
depends_on=None


def upgrade():
    with op.batch_alter_table('generated_documents') as batch:
        batch.add_column(sa.Column('root_id',sa.String(32),nullable=True))
        batch.add_column(sa.Column('document_version',sa.Integer(),nullable=False,server_default='1'))
        batch.add_column(sa.Column('previous_version_id',sa.String(32),nullable=True))
        batch.add_column(sa.Column('revision_reason',sa.Text(),nullable=False,server_default=''))
    op.execute('UPDATE generated_documents SET root_id = id')
    with op.batch_alter_table('generated_documents') as batch:
        batch.alter_column('root_id',existing_type=sa.String(32),nullable=False)
        batch.alter_column('document_version',existing_type=sa.Integer(),server_default=None)
        batch.alter_column('revision_reason',existing_type=sa.Text(),server_default=None)
        batch.create_foreign_key('fk_document_previous_version','generated_documents',['previous_version_id'],['id'])
        batch.create_unique_constraint('uq_document_root_version',['root_id','document_version'])


def downgrade():
    with op.batch_alter_table('generated_documents') as batch:
        batch.drop_constraint('uq_document_root_version',type_='unique')
        batch.drop_constraint('fk_document_previous_version',type_='foreignkey')
        for name in ('revision_reason','previous_version_id','document_version','root_id'):batch.drop_column(name)
