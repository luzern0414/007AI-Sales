"""Read-only deployed smoke; never displays the temporary verification cookie."""
import json,sqlite3
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
state=json.loads((ROOT/'output/playwright/workflow/normal-state.json').read_text(encoding='utf-8-sig'))
with httpx.Client(base_url='http://127.0.0.1:8765',cookies={c['name']:c['value'] for c in state['cookies']},timeout=30) as client:
    response=client.get('/api/projects');response.raise_for_status();report=[]
    for p in response.json():
        base='/api/projects/'+p['id']
        detail=client.get(base);overview=client.get(base+'/overview');workflow=client.get(base+'/workflow');activity=client.get(base+'/activity')
        for r in (detail,overview,workflow,activity):r.raise_for_status()
        assert not any(f['mime'].startswith('audio/') for f in detail.json()['files'])
        assert len(workflow.json()['nodes'])==8
        assert all(len(e['summary'])<=100 for e in overview.json()['entries'])
        assert all(len(e['summary'])<=100 for e in activity.json()['items'] if e['kind']!='node')
        assert all(f['origin'] in ('client','ours','unknown') for e in activity.json()['items'] for f in e['attachments'])
        if detail.json()['files']:
            preview=client.get('/api/files/'+detail.json()['files'][0]['id']+'/preview');preview.raise_for_status();assert 'markdown' in preview.json()
        report.append({'name':p['name'],'files':len(detail.json()['files']),'meetings':len(detail.json()['meetings']),'analysis_status':workflow.json()['analysis']['status']})
    (ROOT/'output/playwright/workflow/deployed-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'projects_checked':len(report),'http':'all200','audio_in_files':False,'summary_max_chars':100}))
with sqlite3.connect(ROOT/'data/platform.db') as db:
    print(json.dumps({'revision':db.execute('select version_num from alembic_version').fetchone()[0],'foreign_key_errors':len(db.execute('PRAGMA foreign_key_check').fetchall())}))
