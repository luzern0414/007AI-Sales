import hashlib
import sqlite3
from pathlib import Path
import pytest


def test_backup_uses_snapshot_and_verifies_original_files(tmp_path):
    from server.backups import backup_local,verify_backup,restore_local
    source=tmp_path/'source.db';storage=tmp_path/'private';storage.mkdir()
    content='审批权限证据'.encode();(storage/'proof').write_bytes(content)
    digest=hashlib.sha256(content).hexdigest()
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE files(storage_key TEXT,sha256 TEXT)')
        db.execute('CREATE TABLE audio_blocks(storage_key TEXT,sha256 TEXT)')
        db.execute('INSERT INTO files VALUES(?,?)',('proof',digest))
    target=tmp_path/'backup'
    backup_local(source,storage,target)
    assert verify_backup(target)['files']==1
    restore_local(target,tmp_path/'restore.db',tmp_path/'restore-files')
    assert (tmp_path/'restore-files/proof').read_bytes()==content
    with sqlite3.connect(tmp_path/'restore.db') as db:
        assert db.execute('SELECT sha256 FROM files').fetchone()[0]==digest
    with pytest.raises(ValueError,match='已存在'):restore_local(target,tmp_path/'restore.db',tmp_path/'other')
    (target/'files/proof').write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='校验'):verify_backup(target)


def test_backup_rejects_escape_and_missing_sources(tmp_path):
    from server.backups import backup_local
    source=tmp_path/'source.db';storage=tmp_path/'files';storage.mkdir()
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE files(storage_key TEXT,sha256 TEXT)')
        db.execute('CREATE TABLE audio_blocks(storage_key TEXT,sha256 TEXT)')
        db.execute('INSERT INTO files VALUES(?,?)',('../outside','0'*64))
    with pytest.raises(ValueError,match='路径'):backup_local(source,storage,tmp_path/'backup')
    assert not (tmp_path/'backup/manifest.json').exists()
