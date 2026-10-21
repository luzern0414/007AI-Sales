"""Create a short-lived local smoke session; never output credentials or tokens."""
import hashlib,json,secrets,sqlite3
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'output/playwright/workflow/normal-state.json'
if target.exists():raise SystemExit('Revoke the previous smoke session first')
token=secrets.token_urlsafe(32)
expires=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(timespec='microseconds')
with sqlite3.connect(ROOT/'data/platform.db') as db:
    owner=db.execute('SELECT id FROM users WHERE is_admin=1 LIMIT 1').fetchone()
    if not owner:raise SystemExit('No local administrator found')
    db.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),owner[0],expires))
target.parent.mkdir(parents=True,exist_ok=True)
target.write_text(json.dumps({'cookies':[{'name':'sales_session','value':token,'domain':'127.0.0.1','path':'/','expires':-1,'httpOnly':True,'secure':False,'sameSite':'Strict'}],'origins':[]}),encoding='utf-8')
print('Local smoke session created; expires in 15 minutes')
