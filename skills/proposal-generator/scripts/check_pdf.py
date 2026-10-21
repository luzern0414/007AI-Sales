"""PDF 交付前自检：字体、禁用词、页面留白、空白页，并生成缩略图供逐页目检。

用法：python check_pdf.py <方案.pdf> [缩略图输出目录] [--forbid 词1,词2]
依赖：pip install pymupdf
检查项：
  1. 字体：只允许 黑体(SimHei)、宋体(SimSun)、Times New Roman
  2. 禁用词：默认检查“一期、二期、暂不纳入、TODO、<、>、待补充”等残留，可用 --forbid 追加
  3. 空白页：除页眉页码外无内容的页面
  4. 大块留白：正文页内容底部高于页面 55% 的页面（可能是表格/图片被挤到下页），需目检确认
  5. 缩略图：每 6 页拼一张 PNG，逐张查看排版
"""
import sys
from pathlib import Path

import fitz

ALLOWED_FONTS = ("SimHei", "SimSun", "TimesNewRoman", "Times New Roman")
FORBID = ["一期", "二期", "暂不纳入", "TODO", "待补充", "<", ">", "XXX", "××"]


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        return
    if "--forbid" in args:
        i = args.index("--forbid")
        FORBID.extend(args[i + 1].split(","))
        del args[i:i + 2]
    pdf = Path(args[0])
    out = Path(args[1]) if len(args) > 1 else pdf.parent / f"{pdf.stem}_检查"
    out.mkdir(parents=True, exist_ok=True)
    d = fitz.open(pdf)
    problems = []

    fonts = {s["font"] for p in d for b in p.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]}
    bad = [f for f in fonts if not any(a.replace(" ", "") in f.replace(" ", "") for a in ALLOWED_FONTS)]
    if bad:
        problems.append(f"出现规范外字体：{bad}")

    text = "".join(p.get_text() for p in d)
    for w in FORBID:
        n = text.count(w)
        if n:
            problems.append(f"含禁用词“{w}” {n} 处（确认是否为正文正常用法）")

    H = d[0].rect.height
    for i, p in enumerate(d):
        blocks = [b for b in p.get_text("blocks") if 0.07 * H < b[1] < 0.93 * H]
        imgs = p.get_images()
        if not blocks and not imgs:
            problems.append(f"第 {i + 1} 页为空白页")
            continue
        if i >= 2 and blocks and not imgs:
            bottom = max(b[3] for b in blocks)
            if bottom < 0.55 * H and i < len(d) - 1:
                problems.append(f"第 {i + 1} 页内容只到页面 {bottom / H:.0%}，下方留白较大，请目检")

    W, Hh = 595, 842
    for s in range(0, d.page_count, 6):
        sheet = fitz.open()
        pg = sheet.new_page(width=W * 3, height=Hh * 2)
        for k, i in enumerate(range(s, min(s + 6, d.page_count))):
            pg.show_pdf_page(fitz.Rect((k % 3) * W, (k // 3) * Hh, (k % 3 + 1) * W, (k // 3 + 1) * Hh), d, i)
        pg.get_pixmap(dpi=100).save(out / f"缩略图_{s // 6 + 1:02d}.png")

    print(f"{pdf.name}：{d.page_count} 页；字体 {sorted(fonts)}")
    print("问题：" if problems else "未发现问题。")
    for x in problems:
        print("  - " + x)
    print(f"缩略图已输出到 {out}，请逐张查看。")


if __name__ == "__main__":
    main()
