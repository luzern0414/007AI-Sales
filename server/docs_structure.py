"""Non-destructive project docs scaffold and machine-owned navigation/state exports."""
import os
from pathlib import Path
from sqlalchemy import select
from .db import Project, ProjectEvent, Meeting, MeetingProject, uid

PLACEHOLDER = '<!-- sales-agent:placeholder -->'
MANAGED = '<!-- sales-agent:generated -->'
DIRECTORIES = ('01-商务与需求', '02-产品与开发', '03-测试与交付')
GROUPS = {
    '01-商务与需求': ('客户资料', '方案文件', '报价与合同'),
    '02-产品与开发': ('设计文档', '开发记录'),
    '03-测试与交付': ('测试验收', '交付资料', '产品宣传'),
}
# Each group's writing standard in the shared SOP library (D:/Codes/SOP); navigation links to it when present.
STANDARDS = {
    '客户资料': ('01-需求',), '方案文件': ('01-需求', '02-方案'), '报价与合同': ('03-报价合同',),
    '设计文档': ('04-设计',), '测试验收': ('05-交付',), '交付资料': ('05-交付',), '产品宣传': ('06-宣传',),
}


def sop_root():
    root = os.getenv('SOP_ROOT') or str(Path(os.getenv('PROJECTS_ROOT', 'D:/Codes')) / 'SOP')
    path = Path(root)
    return path if (path / 'README.md').is_file() else None


def sop_link(docs, folder=None):
    """Relative link from docs/README.md to an SOP README; absolute file URI across drives."""
    from urllib.parse import quote
    root = sop_root()
    if root is None: return None
    target = root / folder / 'README.md' if folder else root / 'README.md'
    if not target.is_file(): return None
    try: return quote(Path(os.path.relpath(target, Path(docs).resolve())).as_posix())
    except ValueError: return target.resolve().as_uri()



def safe_path(docs, relative):
    docs = Path(docs).resolve()
    target = docs / relative
    for part in [target, *target.parents]:
        if part == docs: break
        if part.is_symlink() or part.is_junction(): raise ValueError('文档路径包含链接')
    if not target.resolve().is_relative_to(docs): raise ValueError('文档路径越界')
    return target


def managed_file(path):
    if not path.is_file() or path.stat().st_size > 1024 * 1024: return False
    try: text = path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError): return False
    if text.startswith(MANAGED): return True
    return text == PLACEHOLDER + '\n# ' + path.stem + '\n'


def atomic(path, text):
    temporary = path.with_name('.' + path.name + '-' + uid() + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally: temporary.unlink(missing_ok=True)


def generated(docs, relative, text):
    path = safe_path(docs, relative)
    if path.exists() and not managed_file(path):
        path = safe_path(docs, str(Path(relative).with_name(Path(relative).stem + '-Agent.md')))
        if path.exists() and not managed_file(path): return
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic(path, MANAGED + '\n' + text)
    return path.relative_to(Path(docs).resolve()).as_posix()


def scaffold(docs, name):
    docs = Path(docs)
    if docs.is_symlink() or docs.is_junction(): raise ValueError('文档目录包含链接')
    docs.mkdir(parents=True, exist_ok=True)
    for relative in DIRECTORIES:
        safe_path(docs, relative).mkdir(parents=True, exist_ok=True)
    generated(docs, 'README.md', navigation(docs, name))


def navigation(docs, name):
    from urllib.parse import quote
    docs = Path(docs)
    if docs.is_symlink() or docs.is_junction(): raise ValueError('文档目录包含链接')
    docs = docs.resolve()
    lines = ['# ' + name + ' · 文档导航', '',
             '商务与需求分为“客户资料、方案文件、报价与合同”；产品与开发分为“设计文档、开发记录”；测试与交付分为“测试验收、交付资料、产品宣传”。图片统一放在“素材”。',
             '每个主目录最多三个分组，分组内直接存文件；不属于分组的文件留在对应主目录。分组按需建立，不预建空模板。历史版本在文件名标注日期或版本，归类不代表项目节点已经完成。', '']
    if sop_link(docs):
        lines += ['文档按 [SOP](' + sop_link(docs) + ') 生成：需求 → 方案 → 报价合同 → 设计 → 交付 → 宣传。各分组对应的规范：', '',
                  '| 分组 | 放什么 | 规范 |', '|---|---|---|']
        what = {'客户资料': '客户原件、会议纪要、项目信息卡', '方案文件': '需求清单、资料清单、实施方案',
                '报价与合同': '报价单、合同、变更确认单', '设计文档': '系统设计说明书', '测试验收': '问题清单、验收报告',
                '交付资料': '操作手册、部署手册、培训材料', '产品宣传': '白皮书、单页、介绍 PPT、案例'}
        for category in DIRECTORIES:
            for group in GROUPS[category]:
                links = '、'.join('[' + f + '](' + sop_link(docs, f) + ')' for f in STANDARDS.get(group, ()) if sop_link(docs, f))
                if links: lines.append('| ' + category + '/' + group + ' | ' + what[group] + ' | ' + links + ' |')
        lines.append('')
    if (Path(docs) / '项目进展.md').is_file():
        lines += ['[项目进展](项目进展.md)', '']
    loose = [p for p in Path(docs).glob('*') if not p.is_symlink() and p.is_file() and p.name not in ('README.md', '项目进展.md', 'AGENTS.md') and not p.name.startswith(('.', '~$'))]
    if loose:
        lines += ['## 暂留根目录', '', '尚未归类或正在编辑的文件保留原位，待适合移动时再归类。', '']
        lines += ['- [' + p.name + '](' + quote(p.name) + ')' for p in sorted(loose)]
        lines.append('')
    for category in DIRECTORIES:
        lines += ['## ' + category, '']
        folder = safe_path(docs, category)
        paths = sorted(folder.glob('*'), key=lambda p: p.name.casefold())
        for path in paths:
            if not path.is_symlink() and path.is_file() and not path.name.startswith(('.', '~$')):
                relative = path.relative_to(docs).as_posix()
                lines.append('- [' + path.name.replace('[', '').replace(']', '') + '](' + quote(relative) + ')')
        for group in GROUPS[category]:
            grouped = safe_path(docs, category + '/' + group)
            if not grouped.is_dir(): continue
            standard = [sop_link(docs, f) for f in STANDARDS.get(group, ())]
            lines += ['', '### ' + group + (' · [规范](' + standard[-1] + ')' if standard and standard[-1] else ''), '']
            for path in sorted(grouped.iterdir(), key=lambda p: p.name.casefold()):
                if not path.is_symlink() and path.is_file() and not path.name.startswith(('.', '~$')):
                    relative = path.relative_to(docs).as_posix()
                    lines.append('- [' + path.name.replace('[', '').replace(']', '') + '](' + quote(relative) + ')')
        lines.append('')
    assets = safe_path(docs, '素材')
    if assets.is_dir():
        count = sum(not p.is_symlink() and p.is_file() for p in assets.iterdir())
        lines += ['## 素材', '', '- [配图与视觉素材](' + quote('素材') + '/)：共 ' + str(count) + ' 个文件。', '']
    legacy = Path(docs) / '01-签约前'
    if legacy.is_dir() and not legacy.is_symlink() and not legacy.is_junction():
        locked = [p for p in legacy.iterdir() if p.is_file() and not p.name.startswith('~$')]
        if locked:
            lines += ['## 待归类文件', '', '以下文件被 Office 占用，暂留原位；关闭后归入“01-商务与需求/方案文件”。', '']
            lines += ['- [' + p.name + '](' + quote(p.relative_to(docs).as_posix()) + ')' for p in locked]
            lines.append('')
    return '\n'.join(lines) + '\n'


def meeting_stage(workflow, when):
    """Use confirmed business milestones; unknown meeting dates follow current stage."""
    from datetime import datetime
    for key, stage in (('delivery', '03-测试与交付'), ('contract', '02-产品与开发')):
        node = next((n for n in workflow['nodes'] if n['key'] == key), None)
        if not node or not node['confirmed']:
            continue
        if not when:
            return stage
        try:
            if datetime.fromisoformat(when) >= datetime.fromisoformat(node['occurred_at']):
                return stage
        except (ValueError, TypeError):
            continue
    return '01-商务与需求'


def export_meeting(docs, meeting, when, raw, stage):
    if stage not in DIRECTORIES:
        raise ValueError('未知文档阶段')
    topic = ''.join(c for c in meeting.title[:40] if c not in '<>:"/\\|?*\n\r').strip('. ') or '会议'
    stem = (when[:10] if when else '日期待确认') + '-' + topic + '-' + meeting.id[:8] + '-会议记录'
    group = {'01-商务与需求': '客户资料', '02-产品与开发': '开发记录', '03-测试与交付': '交付资料'}[stage]
    relative = stage + '/' + group + '/' + stem + '.md'
    base = os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:8765').rstrip('/')
    content = '# ' + meeting.title + '\n\n会议时间：' + (when or '待确认')
    content += '\n\n## 会议纪要\n\n' + (meeting.ai_summary or meeting.notes or '待整理')
    content += '\n\n## 录音原文\n\n' + raw['transcript']
    content += '\n' + '\n'.join('[' + str(s['begin_ms']) + 'ms] ' + s['text'] for s in raw['segments'])
    content += '\n\n## 附件\n\n[会议录音](' + base + '/api/meetings/' + meeting.id + '/audio)'
    content += '\n\n[会议纪要PDF](' + base + '/api/meetings/' + meeting.id + '/minutes.pdf)\n'
    return generated(docs, relative, content)



def export_state(app, pid):
    from .workflow import flow, analysis_data
    from .automation import visible_progress
    from .project_catalog import root
    with app.state.sessions() as db:
        # Serialize exports with confirmation/analysis writers, including on SQLite.
        if db.bind.dialect.name == 'sqlite': db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        else: db.execute(select(Project).where(Project.id == pid).with_for_update())
        p = db.get(Project, pid)
        if not p or not p.directory_path: return
        directory = Path(p.directory_path)
        if not directory.is_dir() or directory.is_symlink() or directory.is_junction() or directory.resolve().parent != root(): return
        docs = directory / 'docs'; scaffold(docs, p.name)
        workflow, review = flow(db, p), analysis_data(db, pid)
        text = '# 项目进度\n\n' + (review['summary'] or '待分析') + '\n\n## 流程节点\n\n'
        for node in workflow['nodes']:
            text += '- [' + ('x' if node['confirmed'] else ' ') + '] ' + node['title'] + ' · ' + (node['occurred_at'] or '时间待确认') + (' · ' + node['evidence'] if node['evidence'] else '') + '\n'
        if workflow['due_date']: text += '\n计划交付：' + workflow['due_date'] + '\n'
        text += '\n## 资料进展\n\n'
        for r in visible_progress(db, pid): text += '- ' + r.occurred_at + ' · ' + r.source_name + '：' + r.summary.replace('\n', ' ') + '\n'
        text += '\n## 下一步\n\n' + (review['next_step'] or '待分析') + '\n'
        generated(docs, '02-产品与开发/开发记录/流程进度.md', text)
        generated(docs, '02-产品与开发/开发记录/风险与问题.md', '# 风险与问题\n\n' + '\n'.join('- ' + r['title'] + '：' + r['detail'] + '；依据：' + r['source_name'] + '「' + r['quote'] + '」' for r in review['risks']) + '\n')
        generated(docs, '01-商务与需求/客户资料/客户与业务背景.md', '# 客户与业务背景\n\n' + review['background'] + '\n')
        events = db.scalars(select(ProjectEvent).where(ProjectEvent.project_id == pid, ProjectEvent.kind.in_(['workflow', 'analysis', 'change'])).order_by(ProjectEvent.recorded_at)).all()
        generated(docs, '02-产品与开发/开发记录/变更记录.md', '# 变更记录\n\n' + '\n'.join('- ' + e.recorded_at + ' · ' + e.title + ' · ' + e.detail.replace('\n', ' ') for e in events) + '\n')
        from .recording_imports import active_recording
        meetings = db.scalars(select(Meeting).where((Meeting.project_id == pid) | Meeting.id.in_(select(MeetingProject.meeting_id).where(MeetingProject.project_id == pid))).order_by(Meeting.created_at)).all()
        from urllib.parse import quote
        index = '# 会议索引\n\n'
        for m in meetings:
            imported = active_recording(db,m.id)
            when = imported.occurred_at if imported else m.created_at
            from .automation import original
            raw = original(db, m)
            relative = export_meeting(docs, m, when, raw, meeting_stage(workflow, when))
            if relative:
                link = Path(os.path.relpath(docs / relative, docs / '02-产品与开发/开发记录')).as_posix()
                index += '- ' + (when or '时间待确认') + ' · [' + m.title.replace('[', '').replace(']', '') + '](' + quote(link) + ')\n'
        generated(docs, '02-产品与开发/开发记录/会议索引.md', index)
        generated(docs, 'README.md', navigation(docs, p.name))
