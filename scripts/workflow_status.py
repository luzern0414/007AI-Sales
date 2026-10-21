"""Inspect non-secret verification state for local and isolated services."""
import json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name,path in [('normal',ROOT/'data/platform.db'),('ui',ROOT/'output/playwright/workflow/acceptance.db')]:
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row
        result={'environment':name,'revision':[dict(r) for r in db.execute('select * from alembic_version')],
                'queue':[dict(r) for r in db.execute('select kind,status,count(*) total from analysis_jobs group by kind,status')],
                'sources':[dict(r) for r in db.execute("select subdirectory,status,last_error from source_links where status='failed'")],
                'recent_jobs':[dict(r) for r in db.execute('select kind,status,error,priority,updated_at from analysis_jobs order by updated_at desc limit 5')]}
        if name=='ui':
            result['recordings']=[dict(r) for r in db.execute('select meeting_id,active,occurred_at from imported_recordings')]
            result['progress']=[dict(r) for r in db.execute("select source_type,source_name,occurred_at,time_basis,recorded_at from project_progress order by recorded_at desc limit 5")]
        else:
            result['active_coverage']=[{'status':r['status'],'covered':len(json.loads(r['result_json']).get('coverage',[]))} for r in db.execute("select status,result_json from analysis_jobs where kind='project' and priority=10 and status in ('pending','running','failed') order by updated_at desc limit 2")]
        print(json.dumps(result,ensure_ascii=False))
