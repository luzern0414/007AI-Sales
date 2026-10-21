"""One-time transition for local databases created before Alembic existed."""
from pathlib import Path
import sys
import sqlite3

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from server.db import Base,connect
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect,text

for name in sys.argv[1:]:
    target=Path(name).resolve()
    if target.suffix!='.db' or not target.is_file() or root not in target.parents:
        raise SystemExit('Only existing local project .db files are accepted')
    backup=target.with_suffix('.pre-alembic.db')
    if backup.exists():raise SystemExit('Backup already exists; inspect before retrying')
    with sqlite3.connect(target) as source,sqlite3.connect(backup) as destination:source.backup(destination)
    engine,_=connect('sqlite:///'+target.as_posix())
    existing=inspect(engine)
    if 'alembic_version' in existing.get_table_names():raise SystemExit('Database already uses migrations')
    if 'files' in existing.get_table_names():
        columns={c['name'] for c in existing.get_columns('files')}
        with engine.begin() as connection:
            if 'previous_version_id' not in columns:connection.execute(text('ALTER TABLE files ADD COLUMN previous_version_id VARCHAR(32) REFERENCES files(id)'))
            if 'file_version' not in columns:connection.execute(text('ALTER TABLE files ADD COLUMN file_version INTEGER NOT NULL DEFAULT 1'))
    Base.metadata.create_all(engine)
    engine.dispose()
    config=Config(str(root/'alembic.ini'));config.attributes['database_url']='sqlite:///'+target.as_posix()
    command.stamp(config,'head')
    print('Migrated',target,'Backup',backup)
