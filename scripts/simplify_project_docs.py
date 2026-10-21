"""One-time, backed-up migration to three flat business stages.

Dry run by default. Original bundles and historical records are retained. The
manifest records every old/new path and hash; no business files are discarded.
"""
import argparse
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import quote, unquote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STAGES = ('01-商务与需求', '02-产品与开发', '03-测试与交付')
TEXT = {'.md', '.html', '.htm', '.py', '.ps1', '.js', '.ts', '.tsx', '.vue', '.json', '.toml', '.yaml', '.yml', '.ini', '.sh'}
EXCLUDE = {'docs', 'data', 'output', 'reports', 'research_notes', 'node_modules', 'vendor', 'vendors', 'third_party', 'third-party', 'projects', 'runtime', 'dist', 'build', 'backups', 'delete', 'skill', 'skills', 'assets', '__pycache__', 'secrets', 'backup-keys'}
OWNED_TOP = {'config', 'scripts', 'server', 'web', 'frontend', 'backend', 'app', 'src', 'tests', 'deploy', 'prod', 'gateway', 'admin', 'miniprogram', 'notebooks'}


@lru_cache(maxsize=50000)
def key(path):
    return str(Path(path).resolve()).replace('\\', '/').casefold()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def read(path):
    return path.read_text(encoding='utf-8-sig')


def phase(rel, project):
    parts = rel.parts
    top, name = parts[0], rel.name
    if top in STAGES:
        return top
    if top == '01-签约前':
        return STAGES[0]
    if top == '02-开发过程':
        return STAGES[1]
    if top == '03-交付':
        return STAGES[2]
    if top == '01-对接与立项' or top in ('00_原始资料', '01_方案', '02_调研与确认', '04_会议纪要', '方案', 'source') or top.startswith('产品介绍'):
        return STAGES[0]
    if top == '03-交付与维护' or top in ('06_交付手册', 'manual', 'operations', 'deployment'):
        return STAGES[2]
    if top in ('02-开发与实施', '00-项目管理', 'superpowers', 'adr', 'architecture', 'plans', 'research', 'research_notes', 'hardware', '03_设计', '05_测试与验收'):
        return STAGES[1]
    if top == '培训课程' or project.startswith('005') and name.endswith(('.pptx', '.zip', '.xlsx')):
        return STAGES[2]
    if top == 'project':
        return STAGES[2] if re.search(r'handoff|验收|quickstart', name, re.I) else STAGES[1]
    if project.startswith('010') and re.match(r'(14|27)-', name):
        return STAGES[1]
    if top in ('product', 'reports') or re.search(r'客户|功能需求|业务理解|需求理解|需求规格|^01-PRD|详细方案|^补充|^简介', name):
        return STAGES[0]
    if project.startswith('010') and re.match(r'(15|17|18|19|20|21|22|25|26)-', name):
        return STAGES[2]
    return STAGES[1]


def plan(project):
    docs = project / 'docs'
    rows, used = [], set()
    for path in sorted(docs.rglob('*'), key=lambda p: (len(p.parts), p.as_posix().casefold())):
        if path.is_symlink() or path.is_junction():
            raise ValueError(f'Linked docs path: {path}')
        if not path.is_file():
            continue
        if path.name.startswith('~$'):
            continue  # Office owns its temporary lock while the user is editing.
        if not path.resolve().is_relative_to(docs.resolve()):
            raise ValueError(f'Outside docs: {path}')
        rel = path.relative_to(docs)
        content = read(path) if path.suffix.lower() == '.md' else ''
        placeholder = content == '<!-- sales-agent:placeholder -->\n# ' + path.stem + '\n'
        generated_index = content.startswith('<!-- sales-agent:generated -->') and path.name in ('README.md', '资料导航.md', '会议索引.md')
        generated_meeting = content.startswith('<!-- sales-agent:generated -->') and '会议与沟通' in rel.parts and len(rel.parts) > 3
        action = 'retire' if placeholder or generated_index or generated_meeting or path.name == '.gitkeep' else 'move'
        new = None
        opaque = None
        from server.docs_structure import GROUPS
        current_group = len(rel.parts) == 3 and rel.parts[0] in GROUPS and rel.parts[1] in GROUPS[rel.parts[0]]
        if rel.parts[0] == '素材' or current_group:
            new, action = path, 'move'  # Never flatten the user-approved grouped layout.
        elif project.name.startswith('010') and rel.parts[:2] == ('source', '杭州出差资料汇总'):
            opaque = project / 'data/docs-originals/杭州出差资料汇总'
            new = opaque / Path(*rel.parts[2:])
            action = 'move'
        elif '.workbuddy' in rel.parts or path.name == '.WeDrive' or path.name.startswith('~$'):
            new = project / 'data/docs-originals/文档工作元数据' / rel
            action = 'move'
        elif action == 'move':
            if len(rel.parts) == 1 and path.name in ('README.md', 'AGENTS.md', '项目进展.md'):
                new = path
            else:
                name = path.name
                if name == '项目进度.md' and rel.parts[0] == '00-项目管理':
                    name = '流程进度.md'
                if name == 'README.md':
                    name = rel.parent.name + '-说明.md'
                if '历史版本' in rel.parts or rel.parts[0] == '99-归档':
                    name = '历史-' + name
                if project.name.startswith('005') and any(p.startswith('系列') for p in rel.parts[:-1]):
                    name = next(p for p in rel.parts if p.startswith('系列')) + '-' + name
                category = phase(rel, project.name)
                # Proposal figures are the one intentional subdirectory: keeping
                # them together prevents a flat docs category from mixing binary
                # assets with the proposal text that references them.
                asset_folder = None
                if rel.parts[:2] == (STAGES[0], '方案素材'):
                    asset_folder = '方案素材'
                elif rel.parts[:2] == ('01_方案', '图表'):
                    asset_folder = '方案素材'
                new = docs / category / asset_folder / name if asset_folder else docs / category / name
                if key(new) in used:
                    name = rel.parent.name + '-' + name
                    new = new.with_name(name)
                if key(new) in used:
                    new = new.with_name(new.stem + '-' + hashlib.sha256(rel.as_posix().encode()).hexdigest()[:8] + new.suffix)
        if new:
            if key(new) in used:
                raise ValueError(f'Collision: {new}')
            used.add(key(new))
        rows.append({'old': str(path), 'new': str(new) if new else None, 'action': action,
                     'sha256': digest(path), 'size': path.stat().st_size, 'opaque': str(opaque) if opaque else None})
    return rows


def external_files(project):
    for folder, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if not d.startswith('.') and (d not in EXCLUDE or d == 'docs' and Path(folder) != project) and not Path(folder, d).is_symlink() and not Path(folder, d).is_junction()]
        if Path(folder) == project:
            dirs[:] = [d for d in dirs if d in OWNED_TOP]
        for name in files:
            path = Path(folder, name)
            if path.suffix.lower() in TEXT and path.stat().st_size < 2 * 1024 * 1024 and path.name != Path(__file__).name:
                yield path
            elif path == project / '.gitignore':
                yield path


def update_references(text, old_origin, new_origin, mapping, directory_map):
    if old_origin == new_origin and 'docs' not in old_origin.parts and not any(s in text for s in ('docs', '00-项目管理', '01-对接与立项', '02-开发与实施', '03-交付与维护', '01-签约前', '02-开发过程', '03-交付')):
        return text
    def target(value):
        if value.startswith(('#', 'http:', 'https:', 'data:', 'mailto:', 'app:', 'codex:', 'plugin:')):
            return value
        value = unquote(value)
        fragment = ''
        if '#' in value:
            value, fragment = value.split('#', 1)
            fragment = '#' + fragment
        raw = value.replace('\\', '/')
        absolute = bool(re.match(r'^[A-Za-z]:/', raw)) or raw.startswith('/')
        source = Path(raw) if absolute else old_origin.parent / raw
        replacement = mapping.get(key(source)) or directory_map.get(key(source))
        if replacement is None:
            # Moving a document also changes links to unchanged code/config/assets.
            if not source.exists():
                return value + fragment
            replacement = source.resolve()
        dest = str(replacement).replace('\\', '/') if absolute else os.path.relpath(replacement, new_origin.parent).replace('\\', '/')
        return quote(dest, safe='/:@-._~') + fragment

    # Angle targets permit spaces and parentheses. Plain targets allow balanced one-level parentheses.
    pattern = r'(!?\[[^\]\n]*\]\()(<[^>\n]+>|(?:[^()\n]|\([^()\n]*\))+)(\))'
    def markdown(match):
        raw = match[2]
        angle = raw.startswith('<') and raw.endswith('>')
        value = raw[1:-1] if angle else raw
        suffix = ''
        titled = re.match(r'^(.*?)\s+("[^"\n]*")$', value)
        if titled:
            value, suffix = titled[1], ' ' + titled[2]
        new = target(value)
        return match[1] + ('<' + new + '>' if angle else new) + suffix + match[3]
    text = re.sub(pattern, markdown, text)
    text = re.sub(r'((?:src|href)\s*=\s*)(["\'])(.*?)(\2)', lambda m: m[1] + m[2] + target(m[3]) + m[4], text, flags=re.I)
    # Literal paths in prose, backticks, commands and config (most specific first).
    project = next((p for p in old_origin.parents if (p / 'docs').is_dir()), None)
    pairs = []
    for old_key, new in mapping.items():
        old = Path(old_key)
        old_s = old.as_posix()
        new_s = Path(new).as_posix()
        pairs += [(old_s, new_s), (old_s.replace('/', '\\'), new_s.replace('/', '\\'))]
        if project and old_key.startswith(key(project) + '/'):
            short = os.path.relpath(old, project).replace('\\', '/')
            dest = os.path.relpath(new, project).replace('\\', '/')
            pairs += [(short, dest), (short.replace('/', '\\'), dest.replace('/', '\\'))]
    for old, new in sorted(pairs, key=lambda pair: -len(pair[0])):
        text = re.sub(re.escape(old), lambda _: new, text, flags=re.I)
    return text


def migrate(projects, run, resume=False):
    if resume:
        manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
        plans = manifest['projects']
    else:
        run.mkdir(parents=True, exist_ok=False)
        plans = {str(p): plan(p) for p in projects}
    rows = [r for group in plans.values() for r in group]
    manifest = {'projects': plans, 'external_changes': [], 'version': 1}
    (run / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    # Back up every source file and verify the archive before any migration.
    for project in projects:
        if resume:
            with zipfile.ZipFile(run / (project.name + '.zip')) as archive:
                assert archive.testzip() is None
            continue
        with zipfile.ZipFile(run / (project.name + '.zip'), 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for r in plans[str(project)]:
                archive.write(r['old'], Path(r['old']).relative_to(project).as_posix())
        with zipfile.ZipFile(run / (project.name + '.zip')) as archive:
            assert archive.testzip() is None
    mapping = {key(r['old']): Path(r['new']) for r in rows if r['new']}
    directories = {}
    for r in rows:
        if not r['new']:
            continue
        old, new = Path(r['old']), Path(r['new'])
        directories.setdefault(key(old.parent), set()).add(str(new.parent))
    directory_map = {old: Path(next(iter(dest))) for old, dest in directories.items() if len(dest) == 1}
    # Snapshot ignore decisions at old paths before moving sensitive local originals.
    ignored = []
    for project in projects:
        project_rows = plans[str(project)]
        if not (project / '.git').exists():
            continue
        paths = [Path(r['old']).relative_to(project).as_posix() for r in project_rows]
        result = subprocess.run(['git', '-C', str(project), 'check-ignore', '--stdin'], input='\n'.join(paths) + '\n', capture_output=True, text=True, encoding='utf-8')
        old_ignored = set(result.stdout.splitlines())
        ignored += [(project, r) for r in project_rows if Path(r['old']).relative_to(project).as_posix() in old_ignored and r['new']]
    # Move entire dependent source bundles as units, leaving their internal refs intact.
    opaque_done = set()
    for r in rows:
        old, new = Path(r['old']), Path(r['new']) if r['new'] else None
        if r['opaque']:
            dest = Path(r['opaque'])
            if dest in opaque_done:
                continue
            src = old.parents[len(new.relative_to(dest).parts) - 1]
            assert src.resolve().is_relative_to(next(p / 'docs' for p in projects if old.is_relative_to(p)))
            if dest.exists():
                assert resume and not src.exists()
                opaque_done.add(dest)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            opaque_done.add(dest)
        elif r['action'] == 'retire':
            old.unlink(missing_ok=True)  # Exact empty templates/machine exports, all backed up.
        elif key(old) != key(new):
            if new.exists():
                if not old.exists():
                    assert digest(new) == r['sha256']
                    continue
                # Interrupted shutil.move may have copied a locked file but failed to unlink it.
                assert resume and digest(old) == digest(new) == r['sha256']
                new.unlink()
            new.parent.mkdir(parents=True, exist_ok=True)
            try:
                old.rename(new)
            except PermissionError:
                r['new'] = str(old)
                r['action'] = 'keep_open'
                print('Open document kept in place:', old.name)
    mapping = {key(r['old']): Path(r['new']) for r in rows if r['new']}
    # Original binary content and relocated bundle contents must be byte-identical.
    for r in rows:
        if r['new']:
            assert digest(Path(r['new'])) == r['sha256'], r['old']
    changed = []
    for project in projects:
        changes = [(Path(r['old']), Path(r['new'])) for r in plans[str(project)] if r['new'] and not r['opaque'] and Path(r['new']).suffix.lower() in TEXT and not any(part.startswith('.') for part in Path(r['old']).relative_to(project).parts)]
        changes += [(p, p) for p in external_files(project)]
        for old, new in changes:
            if new.stat().st_size > 2 * 1024 * 1024:
                continue
            try:
                original = read(new)
            except UnicodeError:
                continue
            revised = update_references(original, old, new, mapping, directory_map)
            if revised != original:
                backup = run / 'text-originals' / project.name / old.relative_to(project)
                backup.parent.mkdir(parents=True, exist_ok=True)
                if not backup.exists():
                    shutil.copy2(new, backup)
                stat = new.stat()
                new.write_text(revised, encoding='utf-8', newline='\n')
                os.utime(new, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                changed.append(str(new))
    for project, r in ignored:
        ignore = project / '.gitignore'
        pattern = '/' + Path(r['new']).relative_to(project).as_posix()
        if pattern not in read(ignore).splitlines():
            with ignore.open('a', encoding='utf-8') as stream:
                stream.write('\n' + pattern + '\n')
    for project in projects:
        docs = project / 'docs'
        # Native empty-directory removal only, deepest first, always within this docs root.
        for folder in sorted((p for p in docs.rglob('*') if p.is_dir()), key=lambda p: -len(p.parts)):
            assert folder.resolve().is_relative_to(docs.resolve())
            if not any(folder.iterdir()):
                folder.rmdir()
        for stage in STAGES:
            (docs / stage).mkdir(exist_ok=True)
    manifest['external_changes'] = changed
    for r in rows:
        if r['new']:
            r['after_sha256'] = digest(Path(r['new']))
    (run / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--run', type=Path, default=ROOT / 'output/docs-restructure-20261019')
    args = parser.parse_args()
    projects = sorted(p for p in ROOT.parent.iterdir() if p.is_dir() and re.match(r'^\d{3}', p.name) and (p / 'docs').is_dir())
    if args.apply:
        grouped = ('客户资料', '方案文件', '报价与合同', '设计文档', '开发记录', '测试验收', '交付资料', '产品宣传')
        if any((p / 'docs' / stage / group).is_dir() for p in projects for stage in STAGES for group in grouped) or any((p / 'docs/素材').is_dir() for p in projects):
            parser.error('项目已使用二级分组，请使用 python -m scripts.group_project_docs，禁止重新压平目录。')
        result = migrate(projects, args.run, args.resume)
        print(json.dumps({'backup': str(args.run), 'projects': len(projects), 'references_updated': len(result['external_changes'])}, ensure_ascii=False))
    else:
        print(json.dumps({p.name: {'files': len(rows := plan(p)), 'retire_empty_or_generated': sum(r['action'] == 'retire' for r in rows), 'move': sum(r['new'] is not None and key(r['old']) != key(r['new']) for r in rows)} for p in projects}, ensure_ascii=False, indent=2))
