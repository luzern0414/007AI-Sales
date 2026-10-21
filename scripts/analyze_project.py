"""Resume durable analysis for a named local project without exposing credentials."""
import argparse
from sqlalchemy import select
from server.app import create_app
from server.db import Project,AnalysisJob,StoredFile
from server.automation import drain_jobs


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',required=True)
    parser.add_argument('--limit',type=int,default=100)
    args=parser.parse_args()
    app=create_app()
    with app.state.sessions() as db:
        p=db.scalar(select(Project).where(Project.name==args.project))
        if not p:raise SystemExit('Project does not exist')
        pid=p.id
    for _ in range(args.limit):
        if not drain_jobs(app,limit=1,project_id=pid):break
        with app.state.sessions() as db:
            jobs=list(db.scalars(select(AnalysisJob).where(AnalysisJob.kind=='file',AnalysisJob.target_id.in_(select(StoredFile.id).where(StoredFile.project_id==pid)))))
            counts={s:sum(j.status==s for j in jobs) for s in ('pending','running','succeeded','failed')}
        print(counts,flush=True)


if __name__=='__main__':main()
