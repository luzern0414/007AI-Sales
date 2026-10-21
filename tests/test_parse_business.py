import base64
import io
import urllib.parse
import zipfile
import zlib
from xml.sax.saxutils import escape

import pytest

from server import parse_file


def write_file(tmp_path, suffix, text):
    path = tmp_path / ('business' + suffix)
    path.write_text(text, encoding='utf-8')
    return path


def pptx_file(tmp_path, slides):
    path = tmp_path / 'business.pptx'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        ids = ''.join(f'<p:sldId id="{256+i}" r:id="r{i}"/>' for i in range(len(slides)))
        archive.writestr('ppt/presentation.xml', '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst>' + ids + '</p:sldIdLst></p:presentation>')
        rels = ''.join(f'<Relationship Id="r{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{len(slides)-i}.xml"/>' for i in range(len(slides)))
        archive.writestr('ppt/_rels/presentation.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + rels + '</Relationships>')
        for i, body in enumerate(slides):
            archive.writestr(f'ppt/slides/slide{len(slides)-i}.xml', '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree>' + body + '</p:spTree></p:cSld></p:sld>')
    return path


def text_shape(text):
    return '<p:sp><p:txBody><a:p><a:r><a:t>' + escape(text) + '</a:t></a:r></a:p></p:txBody></p:sp>'


def test_html_extracts_business_text_and_table_without_active_content(tmp_path):
    path = write_file(tmp_path, '.html', '<html><head><style>秘密样式</style><script>秘密脚本</script></head><body><h1>审批 &amp; 权限</h1><p>财务审核</p><table><tr><th>角色</th><th>操作</th></tr><tr><td>主管</td><td>确认报销</td></tr></table><script src="https://invalid.example/script.js">不要执行</script></body></html>')
    text, status = parse_file.extract(path)
    assert status == 'ready'
    assert '审批 & 权限' in text and '财务审核' in text
    assert '角色 | 操作' in text and '主管 | 确认报销' in text
    assert '秘密' not in text and '不要执行' not in text and 'https:' not in text


def test_pptx_preserves_presentation_order_and_table_rows(tmp_path):
    table = '<p:graphicFrame><a:graphic><a:graphicData><a:tbl><a:tr><a:tc><a:txBody><a:p><a:r><a:t>财务</a:t></a:r></a:p></a:txBody></a:tc><a:tc><a:txBody><a:p><a:r><a:t>审批</a:t></a:r></a:p></a:txBody></a:tc></a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame>'
    path = pptx_file(tmp_path, [text_shape('方案起点') + table, text_shape('方案结论')])
    text, status = parse_file.extract(path)
    assert status == 'ready'
    assert text.index('第1页') < text.index('方案起点') < text.index('第2页') < text.index('方案结论')
    assert '财务 | 审批' in text


@pytest.mark.parametrize('compressed', [False, True])
def test_drawio_extracts_node_labels_and_named_pages(tmp_path, compressed):
    graph = '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="2" value="&lt;b&gt;报销申请&lt;/b&gt;" vertex="1"/><mxCell id="3" value="通过" edge="1" source="2" target="4"/><object label="财务审核"><mxCell id="4" vertex="1"/></object></root></mxGraphModel>'
    payload = graph
    if compressed:
        compressor = zlib.compressobj(wbits=-15)
        encoded = urllib.parse.quote(graph).encode()
        payload = base64.b64encode(compressor.compress(encoded) + compressor.flush()).decode()
    path = write_file(tmp_path, '.drawio', '<mxfile><diagram name="报销流程">' + payload + '</diagram></mxfile>')
    text, status = parse_file.extract(path)
    assert status == 'ready'
    assert '第1页' in text and '报销流程' in text and '报销申请' in text and '财务审核' in text and '通过' in text
    assert '<b>' not in text


def test_unsupported_drawio_is_archived(tmp_path):
    assert parse_file.extract(write_file(tmp_path, '.drawio', '<svg/>')) == ('', 'archived')


def test_drawio_compression_bomb_is_failed(tmp_path, monkeypatch):
    compressor = zlib.compressobj(wbits=-15)
    payload = base64.b64encode(compressor.compress(b'A' * 10000) + compressor.flush()).decode()
    path = write_file(tmp_path, '.drawio', '<mxfile><diagram>' + payload + '</diagram></mxfile>')
    monkeypatch.setattr(parse_file, 'MAX_XML_BYTES', 1000, raising=False)
    assert parse_file.extract(path) == ('', 'failed')


@pytest.mark.parametrize('suffix', ['.html', '.drawio'])
def test_xml_entities_are_rejected_without_loading_external_files(tmp_path, suffix):
    payload = '<!DOCTYPE mxfile [<!ENTITY x SYSTEM "file:///secret.txt">]><mxfile><diagram>&x;</diagram></mxfile>'
    assert parse_file.extract(write_file(tmp_path, suffix, payload)) == ('', 'failed')


@pytest.mark.parametrize('suffix', ['.png', '.jpg', '.jpeg', '.webp', '.tiff'])
def test_images_are_explicitly_awaiting_ocr(tmp_path, suffix):
    path = tmp_path / ('scan' + suffix)
    path.write_bytes(b'image is archived for later OCR')
    assert parse_file.extract(path) == ('', 'needs_ocr')


@pytest.mark.parametrize('suffix', ['.md', '.txt', '.html'])
def test_character_limit_returns_no_partial_document(tmp_path, monkeypatch, suffix):
    path = write_file(tmp_path, suffix, '业务正文' * 30)
    monkeypatch.setattr(parse_file, 'MAX_CHARS', 20)
    assert parse_file.extract(path) == ('', 'failed')


def test_non_utf8_markdown_is_failed_without_guessing(tmp_path):
    path = tmp_path / 'meeting.md'
    path.write_bytes('审批规则'.encode('gbk'))
    assert parse_file.extract(path) == ('', 'failed')


def test_pptx_zip_expansion_is_bounded(tmp_path, monkeypatch):
    path = pptx_file(tmp_path, [text_shape('A' * 10000)])
    monkeypatch.setattr(parse_file, 'MAX_ZIP_BYTES', 2000, raising=False)
    assert parse_file.extract(path) == ('', 'failed')


def test_pdf_49_mib_is_parsed_with_page_context(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 10 20 Td (Business approval) Tj ET')
    page[NameObject('/Contents')] = stream
    buf = io.BytesIO()
    writer.write(buf)
    data = buf.getvalue()
    start = data.rfind(b'startxref')
    path = tmp_path / 'training.pdf'
    with path.open('wb') as output:
        output.write(data[:start])
        output.write(b'%')
        output.seek(49 * 1024 * 1024)
        output.write(b'\n' + data[start:])
    text, status = parse_file.extract(path)
    assert status == 'ready' and '第1页' in text and 'Business approval' in text


def test_pdf_decompression_overflow_is_failed(tmp_path, monkeypatch):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    stream = DecodedStreamObject()
    stream.set_data(b' ' * 10000)
    page[NameObject('/Contents')] = stream.flate_encode()
    path = tmp_path / 'compressed.pdf'
    writer.write(path)
    monkeypatch.setattr(parse_file, 'MAX_PDF_STREAM_BYTES', 2000, raising=False)
    assert parse_file.extract(path) == ('', 'failed')


def test_drawio_limits_combined_expanded_pages(tmp_path, monkeypatch):
    graph = '<mxGraphModel><root><!--' + 'padding' * 150 + '--><mxCell value="审批"/></root></mxGraphModel>'
    compressor = zlib.compressobj(wbits=-15)
    payload = base64.b64encode(compressor.compress(urllib.parse.quote(graph).encode()) + compressor.flush()).decode()
    path = write_file(tmp_path, '.drawio', '<mxfile><diagram>' + payload + '</diagram><diagram>' + payload + '</diagram></mxfile>')
    monkeypatch.setattr(parse_file, 'MAX_ZIP_BYTES', 2000)
    assert parse_file.extract(path) == ('', 'failed')


def test_pdf_filter_limits_do_not_leak_to_other_readers(tmp_path, monkeypatch):
    from pypdf import PdfWriter, filters
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    path = tmp_path / 'blank.pdf'
    writer.write(path)
    original = filters.ZLIB_MAX_OUTPUT_LENGTH
    monkeypatch.setattr(parse_file, 'MAX_PDF_STREAM_BYTES', 1000)
    assert parse_file.extract(path) == ('', 'needs_ocr')
    assert filters.ZLIB_MAX_OUTPUT_LENGTH == original


def test_pptx_fails_instead_of_returning_first_slide_when_later_slide_is_missing(tmp_path):
    path = pptx_file(tmp_path, [text_shape('第一页完整'), text_shape('第二页不可用')])
    with zipfile.ZipFile(path) as archive:
        contents = [(name, archive.read(name)) for name in archive.namelist() if name != 'ppt/slides/slide1.xml']
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in contents:
            archive.writestr(name, data)
    assert parse_file.extract(path) == ('', 'failed')


def test_pptx_character_limit_and_page_limit_are_explicit(tmp_path, monkeypatch):
    path = pptx_file(tmp_path, [text_shape('审批' * 100), text_shape('财务')])
    monkeypatch.setattr(parse_file, 'MAX_CHARS', 30)
    assert parse_file.extract(path) == ('', 'failed')
    monkeypatch.setattr(parse_file, 'MAX_CHARS', 1000)
    monkeypatch.setattr(parse_file, 'MAX_PAGES', 1)
    assert parse_file.extract(path) == ('', 'failed')


def test_pdf_page_and_file_limits_are_explicit(tmp_path, monkeypatch):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.add_blank_page(width=300, height=300)
    path = tmp_path / 'pages.pdf'
    writer.write(path)
    monkeypatch.setattr(parse_file, 'MAX_PAGES', 1)
    assert parse_file.extract(path) == ('', 'failed')
    monkeypatch.setattr(parse_file, 'MAX_PDF_BYTES', 100)
    assert parse_file.extract(path) == ('', 'failed')


def surrogate_pdf(tmp_path, codes):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    cmap = DecodedStreamObject()
    cmap.set_data(b'/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n1 begincodespacerange\n<00> <FF>\nendcodespacerange\n3 beginbfchar\n<41> <D83D>\n<42> <DE00>\n<43> <D83D>\nendbfchar\nendcmap end end')
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica'), NameObject('/ToUnicode'): cmap})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 10 20 Td (' + codes + b') Tj ET')
    page[NameObject('/Contents')] = stream
    path = tmp_path / 'surrogate.pdf'
    writer.write(path)
    return path


@pytest.mark.parametrize(('codes', 'expected'), [(b'AB', '\U0001f600'), (b'C', '[无法辨认字符]'), (b'B', '[无法辨认字符]'), (b'A B', '[无法辨认字符] [无法辨认字符]')])
def test_pdf_surrogates_produce_storage_safe_text(tmp_path, codes, expected):
    import sqlite3
    path = surrogate_pdf(tmp_path, codes)
    text, status = parse_file.extract(path)
    assert status == 'ready' and expected in text
    assert not any(0xD800 <= ord(c) <= 0xDFFF for c in text)
    text.encode('utf-8')
    with sqlite3.connect(':memory:') as db:
        db.execute('create table parsed (text text)')
        db.execute('insert into parsed values (?)', (text,))
        assert db.execute('select text from parsed').fetchone()[0] == text


def test_surrogate_replacement_is_also_subject_to_character_limit(tmp_path, monkeypatch):
    path = surrogate_pdf(tmp_path, b'C')
    monkeypatch.setattr(parse_file, 'MAX_CHARS', 10)
    assert parse_file.extract(path) == ('', 'failed')


@pytest.mark.parametrize(('target', 'expected'), [('/ppt/slides/slide1.xml', 'ready'), ('../ppt/slides/slide1.xml', 'failed'), ('/ppt/../ppt/slides/slide1.xml', 'failed'), ('//ppt/slides/slide1.xml', 'failed'), ('/ppt/theme/slide1.xml', 'failed')])
def test_pptx_package_root_targets_and_traversal_boundaries(tmp_path, target, expected):
    path = pptx_file(tmp_path, [text_shape('健身房产品介绍')])
    with zipfile.ZipFile(path) as archive:
        contents = [(name, archive.read(name)) for name in archive.namelist()]
    with zipfile.ZipFile(path, 'w') as archive:
        for name, content in contents:
            if name.endswith('presentation.xml.rels'):
                content = content.replace(b'Target="slides/slide1.xml"', ('Target="' + target + '"').encode())
            archive.writestr(name, content)
    text, status = parse_file.extract(path)
    assert status == expected
    if status == 'ready':
        assert '健身房产品介绍' in text and '第1页' in text
