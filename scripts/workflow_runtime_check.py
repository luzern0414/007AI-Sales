"""Read-only recording safety and source-integrity check before service restart."""
import hashlib,json,sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
with sqlite3.connect(ROOT/'data/platform.db') as db:
    active=db.execute("select count(*) from meetings where status='recording'").fetchone()[0]
    opened=db.execute('select count(*) from capture_epochs where sealed=0').fetchone()[0]
    print(json.dumps({'active_recordings':active,'open_epochs':opened,'projects':db.execute('select count(*) from projects').fetchone()[0],'analysis_jobs':dict(db.execute('select status,count(*) from analysis_jobs group by status').fetchall())}))
    if active or opened:raise SystemExit('Recording in progress: leave service running')
audio=Path('D:/Codes/011KeChuang/docs/01-商务与需求/客户资料/深圳科创项目内部会.m4a')
digest=hashlib.sha256(audio.read_bytes()).hexdigest()
assert digest=='23281f8159f2b0f359216ed5fdec26b6a049a8804a5184bb8490f87b2b18d1cf'
print('Original recording SHA256 unchanged')
