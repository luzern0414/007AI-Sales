"""Verified SQLite snapshots and their immutable private-file references."""
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def references(database):
    with sqlite3.connect(f'{database.resolve().as_uri()}?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('数据库校验失败')
        return {key:value for table in ('files','audio_blocks') for key,value in db.execute(f'SELECT storage_key,sha256 FROM {table}')}


def private_file(directory,key):
    if not key or Path(key).name!=key or key in ('.','..') or '/' in key or '\\' in key or ':' in key:
        raise ValueError('备份文件路径无效')
    path=directory/key
    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):raise ValueError('备份文件路径无效')
    return path


def backup_local(database,storage,target):
    database,storage,target=map(Path,(database,storage,target))
    if not database.is_file():raise ValueError('数据库不存在')
    if target.exists():raise ValueError('备份目录已存在')
    target.mkdir(parents=True);(target/'files').mkdir()
    with sqlite3.connect(f'{database.resolve().as_uri()}?mode=ro',uri=True) as source,sqlite3.connect(target/'platform.db') as snapshot:
        source.backup(snapshot)
    refs=references(target/'platform.db')
    for key,value in refs.items():
        source=private_file(storage,key)
        if not source.is_file() or digest(source)!=value:raise ValueError('原文件校验失败：'+key)
        shutil.copy2(source,target/'files'/key)
        if digest(target/'files'/key)!=value:raise ValueError('备份文件校验失败：'+key)
    manifest={'version':1,'database_sha256':digest(target/'platform.db'),'files':refs}
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return verify_backup(target)


def verify_backup(target):
    target=Path(target)
    try:
        manifest=json.loads((target/'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('version')!=1 or digest(target/'platform.db')!=manifest['database_sha256']:raise ValueError('数据库备份校验失败')
        refs=references(target/'platform.db')
        if refs!=manifest['files']:raise ValueError('备份清单校验失败')
        for key,value in refs.items():
            path=private_file(target/'files',key)
            if not path.is_file() or digest(path)!=value:raise ValueError('备份文件校验失败：'+key)
        return {'files':len(refs),'verified':True}
    except (OSError,KeyError,json.JSONDecodeError,sqlite3.Error) as exc:raise ValueError('备份校验失败') from exc


def restore_local(target,database,storage):
    target,database,storage=map(Path,(target,database,storage))
    result=verify_backup(target)
    if database.exists() or storage.exists() or Path(str(database)+'-wal').exists() or Path(str(database)+'-shm').exists():
        raise ValueError('恢复目标已存在')
    if database.resolve().is_relative_to(storage.resolve()):raise ValueError('数据库不能放在恢复文件目录中')
    database.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(target/'files',storage)
    shutil.copy2(target/'platform.db',database)
    if references(database)!=references(target/'platform.db'):raise ValueError('恢复校验失败')
    return result
