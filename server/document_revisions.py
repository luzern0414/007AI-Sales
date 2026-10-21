from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select,func

from .auth import Auth
from .common import DB,owned,data,record
from .db import GeneratedDocument,Project

router=APIRouter(prefix='/api')


class Revision(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title:str=Field(min_length=1,max_length=240)
    markdown:str=Field(min_length=1,max_length=200000)
    reason:str=Field(min_length=1,max_length=2000)


@router.post('/documents/{document_id}/revisions',status_code=201)
def revise(document_id:str,body:Revision,db:DB,user:Auth):
    previous=db.get(GeneratedDocument,document_id)
    if previous is None:raise HTTPException(404,'文档不存在')
    owned(db,Project,previous.project_id,user)
    latest=db.scalar(select(func.max(GeneratedDocument.document_version)).where(GeneratedDocument.root_id==previous.root_id))
    if latest!=previous.document_version:raise HTTPException(409,'已有新版本，请刷新后修订')
    if body.title==previous.title and body.markdown==previous.markdown:raise HTTPException(422,'内容未修改')
    row=GeneratedDocument(project_id=previous.project_id,meeting_id=previous.meeting_id,kind=previous.kind,title=body.title,markdown=body.markdown,source_snapshot=previous.source_snapshot,source_revision=previous.source_revision,root_id=previous.root_id,document_version=previous.document_version+1,previous_version_id=previous.id,revision_reason=body.reason)
    db.add(row);db.flush()
    record(db,row.project_id,user,'document','修订文档：'+row.title,detail=f'V{previous.document_version} → V{row.document_version}\n依据：'+body.reason,source_id=row.meeting_id)
    return data(row,('source_snapshot',))
