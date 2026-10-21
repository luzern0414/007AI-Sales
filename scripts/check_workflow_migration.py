"""Validate current migrations on a SQLite snapshot, never the live database."""
import json
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'output/workflow-recording-migration.db'
if target.exists():target.unlink()
with sqlite3.connect(ROOT/'data/platform.db') as source,sqlite3.connect(target) as dest:source.backup(dest)
config=Config(str(ROOT/'alembic.ini'))
config.attributes['database_url']='sqlite:///'+target.as_posix()
command.upgrade(config,'head')
command.check(config)
with sqlite3.connect(target) as db:
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    print(json.dumps({'revision':db.execute('select version_num from alembic_version').fetchone()[0],'foreign_keys':'ok','tables_match_models':True}))
