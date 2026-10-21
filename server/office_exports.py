"""Deterministic draft exports. No model calls, external images or executable cells."""
import io
import re
from datetime import datetime
from zoneinfo import ZoneInfo

CLIENT_HEADERS=['编号','分类','事项','需要准备的内容','用途','形式','交付格式','参考模板','必需性','建议责任方','状态','甲方填写 / 备注']


def cells(line):
    return [x.strip().replace(r'\|','|') for x in re.split(r'(?<!\\)\|',line.strip().strip('|'))]


def blocks(markdown):
    lines=markdown.splitlines();i=0
    while i<len(lines):
        line=lines[i].strip()
        if '|' in line and i+1<len(lines) and re.fullmatch(r'[\s|:\-]+',lines[i+1]) and '-' in lines[i+1]:
            head=cells(line);rows=[];i+=2
            while i<len(lines) and '|' in lines[i] and lines[i].strip():
                row=cells(lines[i])
                if len(row)!=len(head):raise ValueError('表格列数不一致，请先修订')
                rows.append(row);i+=1
                if len(rows)>2000:raise ValueError('表格超过2000行')
            if len(head)>20:raise ValueError('表格列数过多')
            yield 'table',(head,rows)
            continue
        if line:yield 'line',line
        i+=1


def clean(text):
    text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',text)
    return text.replace('**','').replace('<br>','\n').replace('<br/>','\n')


def word_draft(title,project,markdown):
    from docx import Document
    from docx.shared import Cm,Pt,RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc=Document();section=doc.sections[0]
    section.page_width,section.page_height=Cm(21),Cm(29.7)
    section.top_margin,section.bottom_margin=Cm(2.5),Cm(2.3)
    section.left_margin=section.right_margin=Cm(2.5)
    section.header_distance,section.footer_distance=Cm(1.5),Cm(1.4)
    def font(run,chinese='SimSun',size=12):
        run.font.name='Times New Roman';run.font.size=Pt(size);run.font.color.rgb=RGBColor.from_string('1F2933')
        rf=run._element.get_or_add_rPr().get_or_add_rFonts()
        for k in list(rf.attrib):
            if 'Theme' in k:del rf.attrib[k]
        rf.set(qn('w:eastAsia'),chinese)
    for name in ('Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3'):
        style=doc.styles[name];style.font.name='Times New Roman'
        rf=style.element.get_or_add_rPr().get_or_add_rFonts()
        for key in list(rf.attrib):
            if 'Theme' in key:del rf.attrib[key]
        rf.set(qn('w:eastAsia'),'SimHei' if name in ('Title','Heading 1','Heading 2','Heading 3') else 'SimSun')
    normal=doc.styles['Normal'].paragraph_format
    normal.line_spacing=1.5;normal.space_before=normal.space_after=Pt(0);normal.first_line_indent=Pt(24)
    for text,size,chinese in ((project,18,'SimHei'),(title,26,'SimHei'),('讨论稿',14,'SimSun'),(datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日'),14,'SimSun')):
        p=doc.add_paragraph(style='Title' if size==26 else 'Normal');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_after=Pt(20);font(p.add_run(clean(text)),chinese,size)
    doc.add_page_break()
    p=doc.add_paragraph('目　　录');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;font(p.runs[0],'SimHei',16)
    p=doc.add_paragraph();field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'TOC \\o "1-2" \\h \\z \\u');p._p.append(field)
    update=OxmlElement('w:updateFields');update.set(qn('w:val'),'true');doc.settings.element.append(update)
    doc.add_page_break()
    header=section.header.paragraphs[0];header.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    font(header.add_run(clean(project+' · '+title)),'SimSun',9)
    footer=section.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
    first_title=True
    for kind,value in blocks(markdown):
        if kind=='line':
            heading=re.match(r'^(#{1,6})\s+(.+)',value)
            if heading:
                if len(heading[1])==1 and first_title:first_title=False;continue
                level=min(3,max(1,len(heading[1])-1));p=doc.add_paragraph(clean(heading[2]),style='Heading '+str(level))
                pf=p.paragraph_format;pf.first_line_indent=Pt(0);pf.keep_with_next=True
                pf.space_before=Pt([18,12,8][level-1]);pf.space_after=Pt([10,6,4][level-1])
                for r in p.runs:font(r,'SimHei',[16,14,12][level-1])
            else:
                p=doc.add_paragraph();font(p.add_run(clean(value)))
            continue
        head,rows=value
        if len(head)>7:raise ValueError('宽表请下载清单表格')
        table=doc.add_table(rows=1,cols=len(head));table.autofit=False
        widths=[3]+[13/(len(head)-1)]*(len(head)-1) if len(head)>1 else [16]
        for col,width in zip(table.columns,widths):col.width=Cm(width)
        for values in [head]+rows:
            row=table.rows[0] if values is head else table.add_row()
            trpr=row._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
            if values is head:trpr.append(OxmlElement('w:tblHeader'))
            for index,(cell,text) in enumerate(zip(row.cells,values)):
                cell.width=Cm(widths[index]);cell.text=''
                p=cell.paragraphs[0];p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.line_spacing=1.25
                p.paragraph_format.space_before=p.paragraph_format.space_after=Pt(0)
                if values is head or index==0:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                font(p.add_run(clean(text)),'SimHei' if values is head or index==0 else 'SimSun',10.5)
                props=cell._tc.get_or_add_tcPr()
                if values is head or index==0:
                    shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E6ECF2' if values is head else 'F2F5F8');props.append(shade)
                margins=OxmlElement('w:tcMar')
                for edge,size in (('top','57'),('bottom','57'),('left','113'),('right','113')):
                    x=OxmlElement('w:'+edge);x.set(qn('w:w'),size);x.set(qn('w:type'),'dxa');margins.append(x)
                props.append(margins)
        borders=OxmlElement('w:tblBorders')
        for edge in ('top','bottom','left','right','insideH','insideV'):
            x=OxmlElement('w:'+edge);x.set(qn('w:val'),'single');x.set(qn('w:sz'),'12' if edge in ('top','bottom') else '4');x.set(qn('w:color'),'3E5C76' if edge in ('top','bottom') else 'A6B1BD');borders.append(x)
        table._tbl.tblPr.append(borders)
    output=io.BytesIO();doc.save(output);return output.getvalue()


def checklist_book(title,markdown,kind):
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.page import PageMargins
    tables=[value for block,value in blocks(markdown) if block=='table']
    if not tables or not any(rows for _,rows in tables):raise ValueError('清单缺少有效表格，请先修订')
    if kind=='client_checklist':
        selected=[]
        for head,rows in tables:
            if not {'编号','事项','需要准备的内容'}.issubset(head):continue
            selected.extend([[row[head.index(h)] if h in head else '' for h in CLIENT_HEADERS] for row in rows])
        if not selected:raise ValueError('甲方清单表格缺少编号、事项或需要准备的内容')
        tables=[(CLIENT_HEADERS,selected)]
    wb=Workbook();wb.remove(wb.active)
    for index,(head,rows) in enumerate(tables,1):
        ws=wb.create_sheet(('甲方确认清单' if kind=='client_checklist' else '需求清单')+(str(index) if index>1 else ''))
        ws.sheet_view.showGridLines=False
        ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=len(head));ws.cell(1,1,clean(title)+' · 讨论稿');ws.row_dimensions[1].height=32
        ws.cell(1,1).font=Font(name='宋体',size=16,color='1F3A5F',bold=True)
        ws.append([])
        for r,values in enumerate([head]+rows,3):
            for c,text in enumerate(values,1):
                cell=ws.cell(r,c,clean(text));cell.data_type='s'
                cell.font=Font(name='宋体',size=11,color='1F2933',bold=r==3)
                cell.fill=PatternFill('solid',fgColor='E6ECF2' if r==3 else 'F2F5F8' if c==1 else 'FFFFFF')
                cell.alignment=Alignment(vertical='top',wrap_text=True)
                cell.border=Border(bottom=Side(style='thin',color='D5DDE6'))
            ws.row_dimensions[r].height=32 if r==3 else min(240,max(40,16*max((len(v)//18+1 for v in values),default=1)))
        for c,h in enumerate(head,1):ws.column_dimensions[get_column_letter(c)].width=42 if h in ('需要准备的内容','甲方填写 / 备注','需求内容','验收标准') else 12 if h=='编号' else 20
        ws.freeze_panes='D4' if len(head)>3 else 'B4'
        ws.auto_filter.ref=f'A3:{get_column_letter(len(head))}{len(rows)+3}'
        ws.print_title_rows='1:3';ws.print_area=f'A1:{get_column_letter(len(head))}{len(rows)+3}'
        ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A3 if len(head)>8 else ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=0;ws.sheet_properties.pageSetUpPr.fitToPage=True
        ws.page_margins=PageMargins(left=.3,right=.3,top=.4,bottom=.4)
        if '状态' in head:
            column=get_column_letter(head.index('状态')+1)
            validation=DataValidation(type='list',formula1='"待提供,待确认,已提供,已确认,不适用"',allow_blank=True)
            validation.error='请选择清单状态';validation.showErrorMessage=True;validation.errorStyle='stop';ws.add_data_validation(validation);validation.add(f'{column}4:{column}{len(rows)+3}')
    output=io.BytesIO();wb.save(output);return output.getvalue()
