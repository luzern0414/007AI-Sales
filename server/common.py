from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from . import db as models


def database(request: Request):
    yield from models.session(request)


DB = Annotated[Session, Depends(database, scope='function')]


def data(obj, exclude=()):
    return {col.name: getattr(obj, col.name) for col in obj.__table__.columns if col.name not in exclude}


def owned(db, model, item_id, user):
    item = db.get(model, item_id)
    if item is None or item.owner_id != user.id:
        raise HTTPException(404, '记录不存在')
    return item


def check_version(item, version):
    if item.version != version:
        raise HTTPException(409, '内容已更新，请刷新后重试')


def record(db, project_id, user, kind, title, **kwargs):
    event = models.ProjectEvent(project_id=project_id, actor_id=user.id, kind=kind, title=title, **kwargs)
    db.add(event)
    db.flush()
    return event


def describe_changes(before,after,reason=''):
    fields={'name':'项目名称','customer':'客户','stage':'环节','status':'状态','due_date':'截止日期','title':'任务名称','assignee':'负责人','evidence':'完成依据'}
    values={'negotiation':'洽谈','requirements':'需求确认','proposal':'方案与商务','preparation':'实施准备','implementation':'实施','testing':'联调与试用','acceptance':'上线与验收','maintenance':'维护','active':'进行中','paused':'已暂停','delivered':'已交付','archived':'已归档','cancelled':'已取消','todo':'待办','doing':'进行中','blocked':'受阻','review':'待验收','done':'已完成','open':'待处理','working':'处理中','resolved':'待复核','closed':'已关闭','pending':'待完成','completed':'已完成'}
    def display(value):return values.get(value,value) if value else '未设置'
    result=[f'{fields.get(key,key)}：{display(before[key])} → {display(value)}' for key,value in after.items() if before[key]!=value]
    if reason:result.append('依据：'+reason)
    return '\n'.join(result)
