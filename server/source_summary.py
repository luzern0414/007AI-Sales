import json
from sqlalchemy import select
from .db import SourceLink,Project


def document_progress(db,user):
    result=[]
    rows=db.execute(select(SourceLink,Project.name).join(Project,Project.id==SourceLink.project_id).where(Project.owner_id==user.id,SourceLink.enabled.is_(True)).order_by(SourceLink.last_synced_at.desc(),SourceLink.id)).all()
    for link,name in rows:
        try:
            summary=json.loads(link.summary or '{}')
            total=int(summary.get('document_total',0))
            checked=int(summary.get('document_checked',0))
            if not 0<=checked<=total:raise ValueError()
        except (ValueError,TypeError,AttributeError):
            total=checked=0
        result.append({'id':link.id,'project_id':link.project_id,'project_name':name,'source_key':link.source_key,'subdirectory':link.subdirectory,'status':link.status,'last_synced_at':link.last_synced_at,'checked':checked,'total':total,'progress':round(100*checked/total) if total else None})
    return result
