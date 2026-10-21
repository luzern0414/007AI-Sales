from pathlib import Path

from scripts.simplify_project_docs import key, plan, phase, update_references


def test_plan_preserves_manual_templates_and_resolves_same_name(tmp_path):
    project = tmp_path / '010Example'
    docs = project / 'docs'
    for name, text in [('00-项目管理/项目章程.md', '<!-- sales-agent:placeholder -->\n# 项目章程\n'),
                       ('02-开发与实施/架构设计/系统架构.md', '<!-- sales-agent:placeholder -->\n# 系统架构\n\n已填写'),
                       ('architecture/technical-design.md', 'first'),
                       ('meeting-agent/technical-design.md', 'second')]:
        path = docs / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    rows = plan(project)
    assert sum(r['action'] == 'retire' for r in rows) == 1
    targets = [key(r['new']) for r in rows if r['new']]
    assert len(targets) == len(set(targets)) == 3
    assert all(len(Path(r['new']).relative_to(docs).parts) == 2 for r in rows if r['new'])


def test_moved_doc_rebases_code_and_html_and_markdown_assets(tmp_path):
    project = tmp_path / 'Example'
    (project / 'docs').mkdir(parents=True)
    old = project / 'docs/architecture/design.md'
    new = project / 'docs/02-产品与开发/design.md'
    asset = project / 'docs/architecture/fig.png'
    target = project / 'docs/02-产品与开发/fig.png'
    code = project / 'server/app.py'
    code.parent.mkdir()
    code.write_text('code')
    text = '[代码](../../server/app.py) ![图](fig.png) <img src="fig.png">'
    revised = update_references(text, old, new, {key(asset): target}, {})
    assert '[代码](../../server/app.py)' in revised
    assert '![图](fig.png)' in revised
    assert '<img src="fig.png">' in revised


def test_legacy_categories_and_proposal_assets_keep_their_business_scope(tmp_path):
    for old, expected in [('01-签约前', '01-商务与需求'), ('02-开发过程', '02-产品与开发'),
                          ('03-交付', '03-测试与交付'), ('03-交付与维护', '03-测试与交付')]:
        assert phase(Path(old) / '记录.md', '011Example') == expected
    project = tmp_path / '011Example'
    image = project / 'docs/素材/系统架构.png'
    image.parent.mkdir(parents=True)
    image.write_bytes(b'original-image')
    rows = plan(project)
    assert len(rows) == 1
    assert Path(rows[0]['new']) == image
