from pathlib import Path

from scripts.group_project_docs import destination, build_plan


def test_classification_uses_only_six_groups_and_preserves_unknown_files():
    examples = {
        '01-商务与需求/客户与业务背景.md': '01-商务与需求/客户资料/客户与业务背景.md',
        '01-商务与需求/会议纪要.md': '01-商务与需求/客户资料/会议纪要.md',
        '01-商务与需求/实施方案.pdf': '01-商务与需求/方案文件/实施方案.pdf',
        '02-产品与开发/数据库设计.md': '02-产品与开发/设计文档/数据库设计.md',
        '02-产品与开发/变更记录.md': '02-产品与开发/开发记录/变更记录.md',
        '02-产品与开发/未识别附件.bin': '02-产品与开发/未识别附件.bin',
        '02-产品与开发/测试记录.md': '03-测试与交付/测试验收/测试记录.md',
        '02-产品与开发/隔离演示启动.md': '03-测试与交付/交付资料/隔离演示启动.md',
        '01-商务与需求/方案素材/系统架构.png': '素材/系统架构.png',
        '03-测试与交付/系列01-AI认知启蒙-D01-第一课.html': '03-测试与交付/交付资料/系列01-AI认知启蒙-D01-第一课.html',
        '03-测试与交付/系列10-AI助手与知识库-D99-用测试问题检查助手是否可靠.html': '03-测试与交付/交付资料/系列10-AI助手与知识库-D99-用测试问题检查助手是否可靠.html',
        '01-商务与需求/Web 销售助手 实时会议 架构调研.md': '02-产品与开发/设计文档/Web 销售助手 实时会议 架构调研.md',
        'README.md': 'README.md',
    }
    for old, expected in examples.items():
        assert destination(Path(old)).as_posix() == expected
        assert destination(Path(expected)).as_posix() == expected


def test_plan_never_overwrites_colliding_assets_and_keeps_all_bytes(tmp_path):
    project = tmp_path / '011Example'
    for relative, value in [('01-商务与需求/方案素材/图.png', b'first'), ('素材/图.png', b'second')]:
        path = project / 'docs' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    rows = build_plan(project)
    targets = [row['new'] for row in rows]
    assert len(targets) == len(set(targets)) == 2
    assert sum(row['old'] == row['new'] for row in rows) == 1


def test_navigation_includes_second_level_and_loose_files_without_following_links(tmp_path):
    from server.docs_structure import navigation
    docs = tmp_path / 'docs'
    for name in ['01-商务与需求/客户资料/背景.md', '02-产品与开发/设计文档/架构.md',
                 '02-产品与开发/未知附件.txt', '素材/系统架构.png']:
        path = docs / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('example', encoding='utf-8')
    text = navigation(docs, '测试项目')
    assert all(name in text for name in ['背景.md', '架构.md', '未知附件.txt', '素材'])


def test_quote_contract_and_promotion_groups():
    examples = {
        '01-商务与需求/财务智能化报价单.xlsx': '01-商务与需求/报价与合同/财务智能化报价单.xlsx',
        '01-商务与需求/技术开发合同（草案）.docx': '01-商务与需求/报价与合同/技术开发合同（草案）.docx',
        '01-商务与需求/变更确认单（01）.docx': '01-商务与需求/报价与合同/变更确认单（01）.docx',
        '01-商务与需求/实施方案.docx': '01-商务与需求/方案文件/实施方案.docx',
        '03-测试与交付/智能财务助手产品白皮书.pdf': '03-测试与交付/产品宣传/智能财务助手产品白皮书.pdf',
        '03-测试与交付/制造业客户案例.docx': '03-测试与交付/产品宣传/制造业客户案例.docx',
    }
    for old, expected in examples.items():
        assert destination(Path(old)).as_posix() == expected
        assert destination(Path(expected)).as_posix() == expected


def test_navigation_links_each_group_to_sop_standard(tmp_path, monkeypatch):
    from server.docs_structure import navigation
    sop = tmp_path / 'SOP'
    for folder in ['', '01-需求', '02-方案', '03-报价合同', '04-设计', '05-交付', '06-宣传']:
        (sop / folder).mkdir(parents=True, exist_ok=True)
        (sop / folder / 'README.md').write_text('# x', encoding='utf-8')
    monkeypatch.setenv('SOP_ROOT', str(sop))
    docs = tmp_path / 'proj' / 'docs'
    path = docs / '01-商务与需求/报价与合同/报价单.xlsx'
    path.parent.mkdir(parents=True)
    path.write_text('x', encoding='utf-8')
    text = navigation(docs, '测试项目')
    assert '### 报价与合同 · [规范](../../SOP/03-%E6%8A%A5%E4%BB%B7%E5%90%88%E5%90%8C/README.md)' in text
    assert '| 03-测试与交付/产品宣传 |' in text and '最多三个分组' in text


def test_navigation_without_sop_has_no_standard_links(tmp_path, monkeypatch):
    from server.docs_structure import navigation
    monkeypatch.setenv('SOP_ROOT', str(tmp_path / 'missing'))
    docs = tmp_path / 'docs'
    (docs / '01-商务与需求/方案文件').mkdir(parents=True)
    text = navigation(docs, '测试项目')
    assert '规范' not in text and '### 方案文件' in text
