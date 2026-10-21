import argparse
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from server.backups import backup_local,verify_backup,restore_local

load_dotenv(ROOT/'.env')
parser=argparse.ArgumentParser()
parser.add_argument('action',choices=['backup','verify','restore'])
parser.add_argument('directory',type=Path)
parser.add_argument('--database',type=Path)
parser.add_argument('--storage',type=Path)
args=parser.parse_args()
try:
    if args.action=='verify':result=verify_backup(args.directory)
    elif args.action=='restore':
        if not args.database or not args.storage:raise ValueError('恢复必须指定新的数据库和文件目录')
        result=restore_local(args.directory,args.database,args.storage)
    else:
        url=make_url(os.getenv('DATABASE_URL','sqlite:///'+(ROOT/'data/platform.db').as_posix()))
        if url.get_backend_name()!='sqlite':raise ValueError('此工具仅支持SQLite，PostgreSQL请使用数据库原生备份')
        database=args.database or Path(url.database)
        storage=args.storage or Path(os.getenv('STORAGE_DIR',str(ROOT/'data/files')))
        result=backup_local(database,storage,args.directory)
    print('Verified:',result['files'],'files')
except (ValueError,OSError) as exc:
    print(str(exc),file=sys.stderr);raise SystemExit(1)
