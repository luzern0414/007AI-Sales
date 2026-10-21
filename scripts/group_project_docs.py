"""Group project docs one level deeper, with verified backups and no overwritten originals.

Dry run: python -m scripts.group_project_docs
Apply: python -m scripts.group_project_docs --apply --run output/docs-grouping-20261019/migration
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from urllib.parse import quote, unquote
import zipfile

from server.docs_structure import DIRECTORIES, GROUPS, generated, navigation
from scripts.simplify_project_docs import key, update_references

ROOT = Path(__file__).resolve().parents[1]
TEXT = {'.md', '.txt', '.html', '.htm', '.py', '.ps1', '.js', '.ts', '.tsx', '.json', '.yaml', '.yml', '.toml', '.vue', '.sh'}
IMAGES = {'.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif', '.drawio'}
LEGACY = {'01-签约前': DIRECTORIES[0], '02-开发过程': DIRECTORIES[1], '03-交付': DIRECTORIES[2]}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def destination(relative):
    """Only classify a recognizable document; keep uncertain material at category level."""
    relative = Path(relative)
    parts, name = relative.parts, relative.name
    if len(parts) == 1:
        if relative.suffix.lower() in IMAGES:
            return Path('素材') / name
        if re.search(r'培训|课程|选课', name):
            return Path(DIRECTORIES[2]) / '交付资料' / name
        return relative
    category = LEGACY.get(parts[0], parts[0])
    if category == '素材' or relative.suffix.lower() in IMAGES:
        return Path('素材') / name
    if category not in DIRECTORIES:
        return relative
    if len(parts) == 3 and parts[1] in GROUPS[category]:
        return Path(category) / parts[1] / name
    lower = name.casefold()
    def has(pattern):
        return re.search(pattern, lower, re.I) is not None
    if name in {'会议索引.md', '原文档索引.md', '流程进度.md', '风险与问题.md', '变更记录.md'}:
        return Path(DIRECTORIES[1]) / '开发记录' / name
    # A lesson about testing is still training material, rather than test evidence.
    if has(r'^系列\d') and relative.suffix.lower() == '.html':
        return Path(DIRECTORIES[2]) / '交付资料' / name
    if category == DIRECTORIES[0] and has(r'架构调研|采集与获客设计'):
        return Path(DIRECTORIES[1]) / '设计文档' / name
    if relative.suffix.lower() in {'.m4a', '.mp3', '.wav', '.aac', '.ogg'} or has(r'会议|转写|录音'):
        group = '客户资料' if category == DIRECTORIES[0] else ('开发记录' if category == DIRECTORIES[1] else '交付资料')
        return Path(category) / group / name
    if has(r'测试|验收|复核|回归|完成审计|acceptance'):
        return Path(DIRECTORIES[2]) / '测试验收' / name
    if has(r'调研|research|opensource|开源|search-crawl|data-sources|sources-integration|上游原始资料说明|upstream-sources'):
        return Path(DIRECTORIES[1]) / '设计文档' / name
    if has(r'部署|运维|隔离演示启动|quickstart|handoff|integration\.html|network-setup|使用手册|操作手册|交付|培训|课程|选课|^系列\d'):
        return Path(DIRECTORIES[2]) / '交付资料' / name
    if has(r'白皮书|产品单页|客户案例|宣传|文案素材') and category != DIRECTORIES[1]:
        return Path(DIRECTORIES[2]) / '产品宣传' / name
    if category == DIRECTORIES[0]:
        if has(r'报价|合同|协议|变更确认|商务确认'):
            return Path(category) / '报价与合同' / name
        if has(r'实施方案|建设方案|录入方案|详细方案|方案源文件|产品介绍|报价|合同|确认清单|确认书|协议|商务确认'):
            return Path(category) / '方案文件' / name
        if has(r'客户|需求|业务理解|业务分析|prd|功能清单|functional-spec|简介|原始参考资料|演示资料原件|甲方.*信息|AI赋能产业升级|传统综合体转型升级'):
            return Path(category) / '客户资料' / name
    elif category == DIRECTORIES[1]:
        if has(r'功能清单|甲方需提供信息'):
            return Path(DIRECTORIES[0]) / '客户资料' / name
        if has(r'^\d{4}-\d\d-\d\d-' ) and not has(r'design|设计'):
            return Path(category) / '开发记录' / name
        if has(r'实现说明|实测|排查|检查|接续执行|开发计划|实施计划|里程碑|路线图|待确认|development|dev-plan|source-download-status|^development|^funasr-gpu|^\d+-实现|^\d+-稳定性'):
            return Path(category) / '开发记录' / name
        if has(r'设计|架构|接口|数据库|数据模型|业务流程|设备登录|开源|技术|提示词|规范|对照|补充.*需求|方案|流程|接线|architecture|technical|design|adr-|^000\d-|data-model|data-and-api|frontend|api\.|security|compliance|agent|ui-spec|functional-spec|audio|phase-plan|realtime|hardware|acquisition|acq-query|demo-generation|meeting-ui|tender|mcp|env-setup|face-enrollment|lock-control'):
            return Path(category) / '设计文档' / name
    elif category == DIRECTORIES[2] and has(r'指南|说明|清单|手册|版本|报告|维护|移交|发布'):
        return Path(category) / '交付资料' / name
    return Path(category) / name


def docs_files(docs):
    for folder, dirs, names in os.walk(docs):
        for name in dirs:
            path = Path(folder) / name
            if path.is_symlink() or path.is_junction():
                raise ValueError('Linked docs directory: ' + str(path))
        for name in names:
            path = Path(folder) / name
            if path.is_symlink():
                raise ValueError('Linked docs file: ' + str(path))
            if name.startswith('~$'):
                continue
            yield path


def build_plan(project):
    docs = project / 'docs'
    rows = []
    paths = list(docs_files(docs))
    # Reserve files already in their target location before allocating moved names.
    paths.sort(key=lambda p: (destination(p.relative_to(docs)) != p.relative_to(docs), p.as_posix().casefold()))
    used = set()
    for old in paths:
        relative = destination(old.relative_to(docs))
        new = docs / relative
        if key(new) in used:
            suffix = hashlib.sha256(old.relative_to(docs).as_posix().encode()).hexdigest()[:8]
            new = new.with_name(new.stem + '-' + suffix + new.suffix)
        assert key(new) not in used, str(new)
        assert old.resolve().is_relative_to(docs.resolve()) and new.resolve().is_relative_to(docs.resolve())
        used.add(key(new))
        rows.append({'old': str(old), 'new': str(new), 'sha256': digest(old), 'size': old.stat().st_size})
    return rows


def external_texts(project):
    # Only project-owned code/docs/config. Never walk installed dependencies or data snapshots.
    for p in project.iterdir():
        if p.is_file() and (p.suffix.lower() in TEXT or p.name == '.gitignore'):
            yield p
    skip = {'node_modules', 'data', 'output', 'dist', 'build', 'runtime', 'vendor', 'vendors', 'third_party', 'secrets', 'backup-keys', 'assets', 'icons', 'snapshots'}
    for name in ('scripts', 'server', 'config', 'tests', 'src', 'backend', 'frontend', 'web', 'deploy', 'prod', 'gateway', 'admin', 'miniprogram', 'skills/proposal-generator'):
        directory = project / name
        if not directory.is_dir() or directory.is_symlink() or directory.is_junction():
            continue
        for folder, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip and not Path(folder,d).is_junction() and not Path(folder,d).is_symlink()]
            for filename in files:
                path = Path(folder) / filename
                if filename in {'group_project_docs.py', 'simplify_project_docs.py'}:
                    continue
                if path.suffix.lower() in TEXT:
                    yield path


def apply(projects, run):
    run.mkdir(parents=True, exist_ok=False)
    plans = {str(p): build_plan(p) for p in projects}
    all_rows = [row for rows in plans.values() for row in rows]
    manifest = {'projects': plans, 'locked': [], 'text_changes': [], 'database_updates': []}
    def checkpoint():
        (run / 'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    checkpoint()
    for project in projects:
        rows = plans[str(project)]
        with zipfile.ZipFile(run / (project.name + '.zip'), 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for row in rows:
                archive.write(row['old'],Path(row['old']).relative_to(project).as_posix())
        with zipfile.ZipFile(run / (project.name + '.zip')) as archive:
            assert archive.testzip() is None
            for row in rows:
                assert hashlib.sha256(archive.read(Path(row['old']).relative_to(project).as_posix())).hexdigest() == row['sha256']
    # Preserve Git ignore behavior for every private source document.
    ignored = []
    for project in projects:
        if not (project / '.git').exists():
            continue
        rows = plans[str(project)]
        files = [Path(row['old']).relative_to(project).as_posix() for row in rows]
        result = subprocess.run(['git','-c','core.quotePath=false','-C',str(project),'check-ignore','--stdin'], input='\n'.join(files)+'\n',capture_output=True,text=True,encoding='utf-8')
        if result.returncode not in (0,1):
            raise RuntimeError('Cannot verify ignore rules: '+project.name)
        private = set(result.stdout.splitlines())
        ignored += [(project,row) for row in rows if Path(row['old']).relative_to(project).as_posix() in private]
    for row in all_rows:
        old,new = Path(row['old']),Path(row['new'])
        assert digest(old) == row['sha256'], 'Changed while planning: '+str(old)
        if old == new:
            continue
        if new.exists():
            raise ValueError('Existing target: '+str(new))
        new.parent.mkdir(parents=True,exist_ok=True)
        try:
            old.rename(new)
        except PermissionError:
            row['intended'] = str(new)
            row['new'] = str(old)
            manifest['locked'].append(str(old))
        assert digest(row['new']) == row['sha256']
        checkpoint()
    mapping = {key(row['old']):Path(row['new']) for row in all_rows}
    directory_map = {}
    for project in projects:
        directory_map[key(project/'docs/01-商务与需求/方案素材')] = project/'docs/素材'
    def save_text(path, text):
        data = text.encode('utf-8',errors='surrogateescape')
        if path.read_bytes() == data:
            return
        project = next(p for p in projects if path.is_relative_to(p))
        backup = run / 'text-originals' / project.name / path.relative_to(project)
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():
            shutil.copy2(path,backup)
        stamp = path.stat()
        temporary = path.with_name('.'+path.name+'.grouping.tmp')
        temporary.write_bytes(data)
        os.replace(temporary,path)
        os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        manifest['text_changes'].append(str(path))
    for project in projects:
        changes = [(Path(row['old']),Path(row['new'])) for row in plans[str(project)] if Path(row['new']).suffix.lower() in TEXT]
        changes += [(p,p) for p in external_texts(project)]
        seen = set()
        for old,new in changes:
            if new in seen or new.stat().st_size > 2*1024*1024:
                continue
            seen.add(new)
            text = new.read_bytes().decode('utf-8-sig',errors='surrogateescape')
            revised = update_references(text,old,new,mapping,directory_map)
            # Also relocate literal directory references used by proposal generators.
            revised = revised.replace('docs/01-商务与需求/方案素材','docs/素材')
            revised = revised.replace('"docs" / "01-商务与需求" / "方案素材"','"docs" / "素材"')
            save_text(new,revised)
    for project,row in ignored:
        if row['old'] == row['new']:
            continue
        path = project / '.gitignore'
        original = path.read_text(encoding='utf-8-sig') if path.exists() else ''
        rule = '/' + Path(row['new']).relative_to(project).as_posix()
        if rule not in original.splitlines():
            if path.exists():
                save_text(path,original.rstrip()+'\n'+rule+'\n')
            else:
                path.write_text(rule+'\n',encoding='utf-8')
    for project in projects:
        docs = project/'docs'
        for folder in sorted((p for p in docs.rglob('*') if p.is_dir()),key=lambda p:-len(p.parts)):
            assert folder.resolve().is_relative_to(docs.resolve())
            if folder.name not in DIRECTORIES and not any(folder.iterdir()):
                folder.rmdir()  # Empty only; no recursive removal.
        for category in DIRECTORIES:
            (docs/category).mkdir(exist_ok=True)
        generated(docs,'README.md',navigation(docs,project.name))
    dbpath = ROOT/'data/platform.db'
    if dbpath.is_file():
        with sqlite3.connect(dbpath) as db:
            with sqlite3.connect(run/'database-before.db') as backup:
                db.backup(backup)
            records = db.execute('SELECT i.link_id,i.relative_path,i.file_id,l.subdirectory FROM source_imports i JOIN source_links l ON i.link_id=l.id WHERE l.source_key=?',('codes',)).fetchall()
            for link_id,relative,file_id,sub in records:
                old = ROOT.parent/sub/relative
                new = mapping.get(key(old))
                if new is None or key(new) == key(old):
                    continue
                assert new.is_relative_to(ROOT.parent/sub)
                newrel = new.relative_to(ROOT.parent/sub).as_posix()
                if db.execute('SELECT 1 FROM source_imports WHERE link_id=? AND relative_path=?',(link_id,newrel)).fetchone():
                    raise ValueError('Duplicate import: '+newrel)
                db.execute('UPDATE source_imports SET relative_path=? WHERE link_id=? AND relative_path=?',(newrel,link_id,relative))
                db.execute('UPDATE files SET name=? WHERE id=?',('[codes] '+newrel.replace('/',' · '),file_id))
                manifest['database_updates'].append({'file_id':file_id,'old':relative,'new':newrel})
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    for row in all_rows:
        row['after_sha256'] = digest(row['new'])
    checkpoint()
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--run',type=Path,default=ROOT/'output/docs-grouping-20261019/migration')
    args=parser.parse_args()
    projects=sorted(p for p in ROOT.parent.iterdir() if p.is_dir() and p.name[:3].isdigit() and (p/'docs').is_dir())
    if args.apply:
        result=apply(projects,args.run)
        print(json.dumps({'projects':len(projects),'moved':sum(row['old']!=row['new'] for rows in result['projects'].values() for row in rows),'locked':result['locked'],'database_updates':len(result['database_updates']),'backup':str(args.run)},ensure_ascii=False))
    else:
        plans={p.name:build_plan(p) for p in projects}
        print(json.dumps({p:dict(Counter(str(Path(row['new']).relative_to(ROOT.parent/p/'docs').parent) for row in rows)) for p,rows in plans.items()},ensure_ascii=False,indent=2))
