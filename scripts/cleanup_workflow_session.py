"""Revoke only the temporary browser verification session, without exposing tokens."""
import hashlib,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
state_file=ROOT/'output/playwright/workflow/normal-state.json'
if state_file.exists():
    state=json.loads(state_file.read_text(encoding='utf-8-sig'));revoked=0
    with sqlite3.connect(ROOT/'data/platform.db') as db:
        for c in state['cookies']:
            if c['httpOnly']:revoked+=db.execute('delete from sessions where token_hash=?',(hashlib.sha256(c['value'].encode()).hexdigest(),)).rowcount
    state_file.unlink();print('Temporary verification sessions revoked:',revoked)
