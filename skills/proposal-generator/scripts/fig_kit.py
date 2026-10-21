"""方案配图组件库：HTML/CSS 设计 → Chrome 无头渲染 → 高清 PNG。

每个函数返回一段完整 HTML，交给 render() 输出 PNG。所有组件共用同一套配色、字号和图标，
保证全文配图风格一致。规范详见 references/05_配图规范.md。

依赖：pip install playwright（使用本机 Chrome：channel="chrome"；无 Chrome 时 playwright install chromium）
用法示例见 scripts/figures_template.py。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 图标目录：与脚本同级的 assets/icons（项目内用法）或上一级的 assets/icons（skill 内用法）
ICONS = next((d for d in (HERE / "assets" / "icons", HERE.parent / "assets" / "icons") if d.exists()), HERE / "assets" / "icons")

# ------------------------------------------------------------------ 设计令牌
NAVY, SLATE, STEEL = "#1F3A5F", "#3E5C76", "#7489A3"
MIST, PAPER, LINE = "#E6ECF2", "#F5F7FA", "#D5DDE6"
INK, SUB = "#1F2933", "#66727F"
GOLD, GOLD_BG, GOLD_LINE, GOLD_INK = "#A8875A", "#F7F2EA", "#E2D3BC", "#7A5F38"
# 序列色（同一图中多个类别，由深到浅）
SHADES = ["#1F3A5F", "#2F4C6E", "#4A6582", "#7489A3", "#A3B3C6", "#C8D2DE"]
# 等级色（好 → 差）
LEVELS = ["#1F3A5F", "#7489A3", "#B49A72", "#8A6A4F"]

FONT_SCALE = 1.2      # 设计宽 1000px 的图插入 A4 后约 15.5cm，字号整体放大，保证图内文字 ≥ 约 8 磅
WIDTH = 1000          # 设计宽度（px）
DPR = 3               # 导出倍率（3 倍 ≈ 300dpi）

CSS = f"""
:root{{--navy:{NAVY};--slate:{SLATE};--steel:{STEEL};--mist:{MIST};--paper:{PAPER};--line:{LINE};
--ink:{INK};--sub:{SUB};--gold:{GOLD};--goldbg:{GOLD_BG};}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#fff;font-family:"Microsoft YaHei","微软雅黑","PingFang SC",sans-serif;color:var(--ink);}}
#fig{{width:{WIDTH}px;padding:26px 28px;background:#fff}}
.ic{{display:inline-flex;width:22px;height:22px;flex:none}}
.ic svg{{width:100%;height:100%;stroke-width:1.8}}
.legend{{display:flex;gap:22px;justify-content:flex-end;font-size:15px;color:var(--sub);margin-bottom:14px}}
.legend i{{display:inline-block;width:16px;height:16px;border-radius:4px;vertical-align:-3px;margin-right:6px}}
"""


def icon(name, color="currentColor", size=22):
    """Lucide 线性图标。名称见 assets/icons/；缺少时到 https://unpkg.com/lucide-static@0.469.0/icons/<name>.svg 下载。"""
    path = ICONS / f"{name}.svg"
    if not path.exists():
        raise FileNotFoundError(f"缺少图标 {name}.svg，请下载到 {ICONS}")
    svg = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S).strip()
    return f'<span class="ic" style="color:{color};width:{size}px;height:{size}px">{svg}</span>'


def _scale(css):
    return re.sub(r"font-size:([\d.]+)px", lambda m: f"font-size:{float(m.group(1)) * FONT_SCALE:.1f}px", css)


def page(body, extra_css=""):
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{_scale(CSS + extra_css)}</style>"
            f"</head><body><div id='fig'>{body}</div></body></html>")


def render(figures, out_dir):
    """figures: {"文件名.png": html字符串}；输出到 out_dir。"""
    from playwright.sync_api import sync_playwright
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome")
        except Exception:
            browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": WIDTH, "height": 800}, device_scale_factor=DPR)
        for name, html in figures.items():
            pg.set_content(html, wait_until="load")
            pg.locator("#fig").screenshot(path=str(out / name))
        browser.close()


def _legend(items):
    return '<div class="legend">' + "".join(f'<span><i style="background:{c};border:1px solid {b}"></i>{n}</span>'
                                            for n, c, b in items) + "</div>"


# ================================================================== 1. 概况图
def kpi_overview(kpis, stack_title=None, stack_rows=None):
    """指标卡 + 分层/分区示意。
    kpis: [(图标, 标题, 数值, 单位, 一句说明, 是否强调)]，建议 3–4 个；强调用暖金（如空置、风险）。
    stack_rows: [(层名, [标签...], 提示或None)]，可选，如楼层业态、区域划分。
    """
    k = "".join(
        f"""<div class="kpi {'warn' if w else ''}"><div class="kh">{icon(i, 'var(--gold)' if w else 'var(--slate)')}<span>{t}</span></div>
        <div class="kv"><b>{v}</b><small>{u}</small></div><div class="kn">{n}</div></div>""" for i, t, v, u, n, w in kpis)
    rows = ""
    for name, chips, tip in (stack_rows or []):
        tag = f'<span class="vac">{icon("triangle-alert", "var(--gold)", 18)}{tip}</span>' if tip else ""
        rows += f'<div class="fl"><div class="fn">{name}</div><div class="fb">{"".join(f"<span class=chip>{c}</span>" for c in chips)}{tag}</div></div>'
    stack = f'<div class="stack"><div class="st">{stack_title or ""}</div>{rows}</div>' if stack_rows else ""
    css = f"""
    .kpis{{display:grid;grid-template-columns:repeat({len(kpis)},1fr);gap:14px;margin-bottom:{22 if stack else 0}px}}
    .kpi{{border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:#fff;border-top:4px solid var(--slate)}}
    .kpi.warn{{border-top-color:var(--gold);background:var(--goldbg)}}
    .kh{{display:flex;align-items:center;gap:8px;font-size:16px;color:var(--sub)}}
    .kv{{margin-top:8px}}.kv b{{font-size:34px;color:var(--navy);font-weight:700}}
    .kv small{{font-size:15px;color:var(--sub);margin-left:6px}}.kpi.warn .kv b{{color:{GOLD_INK}}}
    .kn{{font-size:14px;color:var(--sub);margin-top:4px}}
    .stack{{border:1px solid var(--line);border-radius:12px;padding:16px;background:var(--paper)}}
    .st{{font-size:16px;color:var(--sub);margin-bottom:12px}}
    .fl{{display:flex;gap:12px;margin-bottom:10px}}.fl:last-child{{margin-bottom:0}}
    .fn{{width:70px;height:54px;border-radius:8px;background:var(--navy);color:#fff;font-size:22px;font-weight:700;display:flex;align-items:center;justify-content:center}}
    .fb{{flex:1;background:#fff;border:1px solid var(--line);border-radius:8px;display:flex;align-items:center;gap:10px;padding:0 16px}}
    .chip{{font-size:17px;padding:5px 14px;border-radius:20px;background:var(--mist);color:var(--navy)}}
    .vac{{margin-left:auto;display:flex;align-items:center;gap:6px;font-size:15px;color:{GOLD_INK};background:var(--goldbg);border:1px solid {GOLD_LINE};padding:5px 12px;border-radius:20px}}
    """
    return page(f'<div class="kpis">{k}</div>{stack}', css)


# ================================================================== 2. 结构图（占比）
def donut_bars(data, center_value, center_label, title, conclusion):
    """环形图 + 横向条形图 + 一句结论。data: [(名称, 百分比数值)]，按大小降序，不超过 6 项。"""
    mx = max(v for _, v in data) * 1.06
    bars = "".join(
        f'<div class="br"><span class="bl">{n}</span><div class="bt"><div class="bf" style="width:{v / mx * 100:.1f}%;background:{c}"></div></div><span class="bv">{v:g}%</span></div>'
        for (n, v), c in zip(data, SHADES))
    acc, stops = 0, []
    total = sum(v for _, v in data)
    for (_, v), c in zip(data, SHADES):
        stops.append(f"{c} {acc / total * 100:.2f}% {(acc + v) / total * 100:.2f}%")
        acc += v
    css = """
    .wrap{display:flex;gap:34px;align-items:center}
    .donut{width:230px;height:230px;border-radius:50%;position:relative;flex:none}
    .donut::after{content:"";position:absolute;inset:42px;background:#fff;border-radius:50%}
    .dc{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:1}
    .dc b{font-size:38px;color:var(--navy)}.dc span{font-size:15px;color:var(--sub)}
    .bars{flex:1}.br{display:flex;align-items:center;gap:14px;margin:12px 0}
    .bl{width:130px;text-align:right;font-size:17px}.bt{flex:1;height:22px;background:var(--paper);border-radius:6px;overflow:hidden}
    .bf{height:100%;border-radius:6px}.bv{width:60px;font-size:17px;font-weight:700;color:var(--navy)}
    .tip{margin-top:18px;font-size:15px;color:var(--sub);border-top:1px dashed var(--line);padding-top:12px}
    """
    body = (f'<div class="wrap"><div class="donut" style="background:conic-gradient({",".join(stops)})">'
            f'<div class="dc"><b>{center_value}</b><span>{center_label}</span></div></div>'
            f'<div class="bars"><div style="font-size:16px;color:var(--sub);margin-bottom:4px">{title}</div>{bars}</div></div>'
            f'<div class="tip">{conclusion}</div>')
    return page(body, css)


# ================================================================== 3. 数据流向图
def hub(sources, core_title, core_items, core_band, apps, headers=("数据从哪里来", "统一存放 · 统一口径", "用在哪里"),
        core_note="入库前自动校验 · 异常单独标记"):
    """来源 → 底座 → 应用 三栏。sources: [(图标, 名称, 说明)]；apps: [(图标, 名称)]；core_items: 底座内的分库名；
    core_band: (标题, 说明)。两侧各 4–6 项为宜。"""
    n = max(len(sources), len(apps))
    h = 90 * n
    s = "".join(f'<div class="it">{icon(i, "var(--slate)", 26)}<div><b>{t}</b><span>{d}</span></div></div>' for i, t, d in sources)
    a = "".join(f'<div class="it">{icon(i, "var(--slate)", 24)}<div><b>{t}</b></div></div>' for i, t in apps)
    libs = "".join(f'<div class="lib">{x}</div>' for x in core_items)
    css = f"""
    .cols{{display:grid;grid-template-columns:1fr 46px 1.05fr 46px 1fr;align-items:start}}
    .hd{{font-size:15px;color:var(--sub);text-align:center;margin-bottom:10px;letter-spacing:2px}}
    .list{{display:flex;flex-direction:column;gap:12px;justify-content:center;min-height:{h}px}}
    .it{{display:flex;align-items:center;gap:14px;padding:14px 16px;background:#fff;border:1px solid var(--line);border-radius:10px}}
    .it b{{display:block;font-size:17px;font-weight:600}}.it span{{display:block;font-size:14px;color:var(--sub);margin-top:2px}}
    .ar{{display:flex;align-items:center;justify-content:center;color:var(--steel);font-size:30px;height:{h}px;margin-top:32px}}
    .core{{background:var(--navy);border-radius:14px;color:#fff;padding:22px 20px;display:flex;flex-direction:column;justify-content:center;gap:14px;min-height:{h}px}}
    .core h4{{font-size:21px;font-weight:600;text-align:center;display:flex;gap:8px;align-items:center;justify-content:center}}
    .libs{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
    .lib{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.22);border-radius:8px;padding:10px;text-align:center;font-size:16px}}
    .band{{background:#fff;color:var(--navy);border-radius:8px;padding:11px;text-align:center;font-size:16px;font-weight:600}}
    .band span{{display:block;font-size:13px;font-weight:400;color:var(--sub);margin-top:2px}}
    .q{{font-size:13px;text-align:center;color:#C9D4E0}}
    """
    body = f"""<div class="cols">
    <div><div class="hd">{headers[0]}</div><div class="list">{s}</div></div><div class="ar">›</div>
    <div><div class="hd">{headers[1]}</div><div class="core"><h4>{icon("database", "#fff", 24)}{core_title}</h4>
      <div class="libs">{libs}</div><div class="band">{core_band[0]}<span>{core_band[1]}</span></div><div class="q">{core_note}</div></div></div>
    <div class="ar">›</div><div><div class="hd">{headers[2]}</div><div class="list">{a}</div></div></div>"""
    return page(body, css)


# ================================================================== 4. 业务线（泳道）流程图
def lanes(rows, legend=("系统自动完成", "人工操作或确认")):
    """rows: [(图标, 业务线名, [(步骤名, 是否人工)])]。每行 4–6 步，步骤名 ≤ 5 字；人工步骤用暖金并带人形图标。"""
    out = ""
    for ic, name, steps in rows:
        cells = ""
        for i, (t, human) in enumerate(steps):
            badge = f'<em>{icon("user-check", GOLD_INK, 14)}</em>' if human else f"<em>{i + 1}</em>"
            cells += f'<div class="sp {"hm" if human else ""}">{badge}<span>{t}</span></div>'
            if i < len(steps) - 1:
                cells += '<div class="ar">›</div>'
        out += f'<div class="lane"><div class="ln">{icon(ic, "#fff", 22)}<span>{name}</span></div><div class="steps">{cells}</div></div>'
    css = f"""
    .lane{{display:flex;gap:14px;margin-bottom:12px;align-items:stretch}}.lane:last-child{{margin-bottom:0}}
    .ln{{width:136px;flex:none;background:var(--navy);color:#fff;border-radius:10px;display:flex;align-items:center;justify-content:center;gap:8px;font-size:17px;font-weight:600}}
    .steps{{flex:1;display:flex;align-items:center;background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
    .sp{{flex:1;height:52px;white-space:nowrap;background:#fff;border:1px solid var(--line);border-radius:8px;display:flex;align-items:center;gap:8px;padding:0 8px;font-size:16px}}
    .sp em{{font-style:normal;width:22px;height:22px;border-radius:50%;background:var(--mist);color:var(--slate);font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:none}}
    .sp.hm{{border-color:#D9C6A6;background:var(--goldbg)}}.sp.hm em{{background:#EADFCB}}
    .ar{{width:14px;text-align:center;color:var(--steel);font-size:20px;flex:none}}
    """
    lg = _legend([(legend[0], "#fff", LINE), (legend[1], GOLD_BG, "#D9C6A6")])
    return page(lg + out, css)


# ================================================================== 5. 分层架构图（总体框架）
def layers(rows, side_title="安全保障", side_items=("权限", "加密", "审计", "备份"), gateway_text=None):
    """rows（自上而下）: [(层名, 图标, [模块...], 是否重点层)]。每层模块 ≤ 7 个、每个 ≤ 5 字。
    重点层（如 AI 层）用深藏青；gateway_text 显示在重点层底部（如模型网关说明）。"""
    out = ""
    for name, ic, items, hl in rows:
        chips = "".join(f'<div class="c">{x}</div>' for x in items)
        extra = f'<div class="gw">{gateway_text}</div>' if (hl and gateway_text) else ""
        out += f'<div class="ly {"hl" if hl else ""}"><div class="lb">{icon(ic, "#fff", 20)}<span>{name}</span></div><div class="bd"><div class="cs">{chips}</div>{extra}</div></div>'
    side = "".join(f'<span class="si">{x}</span>' for x in side_items)
    css = """
    .wrap{display:flex;gap:12px}.main{flex:1}
    .ly{display:flex;gap:10px;margin-bottom:9px}.ly:last-child{margin-bottom:0}
    .lb{width:138px;flex:none;background:var(--slate);color:#fff;border-radius:8px;display:flex;align-items:center;justify-content:center;gap:8px;font-size:16px;font-weight:600}
    .ly.hl .lb{background:var(--navy)}
    .bd{flex:1;background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:8px}
    .ly.hl .bd{background:var(--mist);border-color:#BFCCDA}
    .cs{display:flex;gap:8px}.c{flex:1;background:#fff;border:1px solid var(--line);border-radius:6px;text-align:center;padding:11px 4px;font-size:15px;white-space:nowrap}
    .gw{margin-top:8px;background:var(--navy);color:#fff;border-radius:6px;text-align:center;font-size:14px;padding:7px}
    .side{width:64px;flex:none;background:var(--paper);border:1px solid var(--line);border-radius:8px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px}
    .side b{writing-mode:vertical-rl;font-size:15px;letter-spacing:6px;color:var(--navy);margin-bottom:8px}
    .side .si{font-size:14px;background:#fff;border:1px solid var(--line);border-radius:6px;padding:6px 0;width:42px;text-align:center}
    """
    return page(f'<div class="wrap"><div class="main">{out}</div><div class="side">{icon("lock", "var(--slate)", 22)}<b>{side_title}</b>{side}</div></div>', css)


# ================================================================== 6. 圆形节点流程图
def circle_flow(steps, notes=()):
    """steps: [(图标, 步骤名, 一句说明, 是否人工)]，4–6 步，说明 ≤ 8 字；
    notes: [(标题, 内容, 是否警示)]，0–3 个，显示在下方（警示用暖金，如“不替代消防设施”）。"""
    items = ""
    for i, (ic, t, d, h) in enumerate(steps):
        items += f'<div class="st {"hm" if h else ""}"><div class="cir">{icon(ic, GOLD_INK if h else "#fff", 26)}</div><b>{t}</b><span>{d}</span></div>'
        if i < len(steps) - 1:
            items += '<div class="ln"></div>'
    nb = "".join(f'<div class="fbx {"w" if w else ""}"><b>{t}：</b>{c}</div>' for t, c, w in notes)
    css = f"""
    .flow{{display:flex;align-items:flex-start}}
    .st{{width:128px;flex:none;text-align:center}}
    .cir{{width:64px;height:64px;border-radius:50%;background:var(--navy);margin:0 auto 10px;display:flex;align-items:center;justify-content:center}}
    .st.hm .cir{{background:var(--goldbg);border:2px solid #C9B08A}}
    .st b{{display:block;font-size:16px;white-space:nowrap}}.st span{{display:block;font-size:13px;color:var(--sub);margin-top:3px}}
    .ln{{flex:1;height:2px;background:var(--line);margin-top:32px;position:relative}}
    .ln::after{{content:"";position:absolute;right:-1px;top:-4px;border:5px solid transparent;border-left:7px solid #B8C4D1}}
    .foot{{display:flex;gap:14px;margin-top:20px}}
    .fbx{{flex:1;background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:12px 16px;font-size:14px}}
    .fbx b{{color:var(--navy)}}.fbx.w{{background:var(--goldbg);border-color:{GOLD_LINE}}}.fbx.w b{{color:{GOLD_INK}}}
    """
    return page(f'<div class="flow">{items}</div>' + (f'<div class="foot">{nb}</div>' if notes else ""), css)


# ================================================================== 7. 原则卡片
def principle_cards(roles, cards, highlight_role=1):
    """roles: 顶部分工条文字（2–3 段，如“AI 负责…/程序负责…/人负责…”），highlight_role 为突出的一段；
    cards: [(图标, 标题 ≤ 6 字, 说明 ≤ 16 字)]，3–5 张。"""
    r = "".join(f'<div class="role {"mid" if i == highlight_role else ""}">{t}</div>' for i, t in enumerate(roles))
    c = "".join(f'<div class="g"><div class="n">{i + 1:02d}</div>{icon(ic, "var(--navy)", 30)}<b>{t}</b><p>{d}</p></div>'
                for i, (ic, t, d) in enumerate(cards))
    css = f"""
    .top{{display:flex;justify-content:center;margin-bottom:18px}}
    .role{{padding:10px 26px;font-size:16px;background:var(--mist);color:var(--navy)}}
    .role:first-child{{border-radius:24px 0 0 24px}}.role:last-child{{border-radius:0 24px 24px 0}}
    .role.mid{{background:var(--navy);color:#fff}}
    .gs{{display:grid;grid-template-columns:repeat({len(cards)},1fr);gap:12px}}
    .g{{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:16px 14px;position:relative;text-align:center}}
    .g .n{{position:absolute;top:10px;left:12px;font-size:13px;color:var(--steel);font-weight:700}}
    .g .ic{{margin:8px auto 10px}}.g b{{display:block;font-size:16.5px;margin-bottom:6px;white-space:nowrap}}
    .g p{{font-size:13.5px;color:var(--sub);line-height:1.55}}
    """
    return page(f'<div class="top">{r}</div><div class="gs">{c}</div>', css)


# ================================================================== 8. 评分分级图
def grade(dims, levels, red_lines=(), footnote="", title="打分维度与权重（满分 100 分）"):
    """dims: [(维度, 权重, 说明)]，权重合计 100；levels: [(等级, 分数区间, 处理方式)]，按好→差 4 级；
    red_lines: 红线规则文字，可空。"""
    bar = "".join(f'<div class="seg" style="flex:{w};background:{SHADES[i]}"><b>{n}</b><span>{w} 分</span></div>' for i, (n, w, _) in enumerate(dims))
    desc = "".join(f'<div style="flex:{w}" class="sd">{d}</div>' for _, w, d in dims)
    lv = "".join(f'<div class="lv"><div class="lt" style="background:{LEVELS[i]}"><b>{n}</b><span>{r} 分</span></div><p>{d}</p></div>'
                 for i, (n, r, d) in enumerate(levels))
    red = ""
    if red_lines:
        red = (f'<div class="red"><h5>{icon("triangle-alert", GOLD, 20)}红线规则</h5><ul>'
               + "".join(f"<li>{x}</li>" for x in red_lines) + "</ul></div>")
    css = f"""
    .t{{font-size:16px;color:var(--sub);margin:0 0 10px}}
    .bar{{display:flex;height:66px;border-radius:10px;overflow:hidden}}
    .seg{{color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;border-right:2px solid #fff}}
    .seg:last-child{{border-right:none}}.seg b{{font-size:17px}}.seg span{{font-size:14px;opacity:.85}}
    .sds{{display:flex;margin-top:6px}}.sd{{font-size:13.5px;color:var(--sub);text-align:center}}
    .lvs{{display:grid;grid-template-columns:repeat({len(levels)},1fr);gap:12px;margin-top:22px}}
    .lv{{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}}
    .lt{{color:#fff;padding:12px;text-align:center}}.lt b{{font-size:20px;display:block}}.lt span{{font-size:14px;opacity:.9}}
    .lv p{{font-size:14.5px;padding:10px;text-align:center}}
    .red{{margin-top:18px;background:var(--goldbg);border:1px solid {GOLD_LINE};border-radius:10px;padding:14px 18px;display:flex;gap:14px}}
    .red h5{{font-size:16px;color:{GOLD_INK};white-space:nowrap;display:flex;gap:6px;align-items:flex-start}}
    .red ul{{list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:6px 24px;font-size:15px}}
    .red li::before{{content:"·";color:{GOLD};margin-right:8px;font-weight:700}}
    .fn{{font-size:13.5px;color:var(--sub);margin-top:8px}}
    """
    body = (f'<div class="t">{title}</div><div class="bar">{bar}</div><div class="sds">{desc}</div>'
            f'<div class="lvs">{lv}</div>{red}' + (f'<div class="fn">{footnote}</div>' if footnote else ""))
    return page(body, css)


# ================================================================== 9. 硬件/部署布置图
def zone_cards(zones, bus_text, base_title, base_sub, bus_icon="wifi"):
    """zones: [(图标, 位置, 设备名, 采集数据, 是否强调)]，3–5 个；bus_text: 中间供电/网络说明；
    base_title/base_sub: 底部汇聚平台。"""
    cards = "".join(
        f'<div class="z {"warm" if w else ""}"><div class="zh">{icon(ic, GOLD_INK if w else "var(--navy)", 26)}<span>{loc}</span></div>'
        f'<div class="dv"><b>{dev}</b><span>{out}</span></div></div>' for ic, loc, dev, out, w in zones)
    n = len(zones)
    css = f"""
    .zs{{display:grid;grid-template-columns:repeat({n},1fr);gap:12px}}
    .z{{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:16px 10px;text-align:center}}
    .z.warm{{background:var(--goldbg);border-color:{GOLD_LINE}}}
    .zh{{display:flex;flex-direction:column;align-items:center;gap:8px;font-size:16px;font-weight:600;margin-bottom:12px;white-space:nowrap}}
    .dv{{background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 4px}}
    .dv b{{display:block;font-size:14.5px;color:var(--navy);white-space:nowrap}}.dv span{{display:block;font-size:13px;color:var(--sub);margin-top:3px}}
    .down{{display:grid;grid-template-columns:repeat({n},1fr);text-align:center;color:var(--steel);font-size:22px;margin:4px 0}}
    .net{{background:var(--mist);border-radius:10px;text-align:center;padding:12px;font-size:15px;color:var(--navy);display:flex;align-items:center;justify-content:center;gap:10px}}
    .plat{{margin-top:12px;background:var(--navy);color:#fff;border-radius:10px;text-align:center;padding:14px;font-size:17px;font-weight:600}}
    .plat span{{display:block;font-size:13.5px;font-weight:400;opacity:.85;margin-top:4px}}
    """
    body = (f'<div class="zs">{cards}</div><div class="down">{"<span>↓</span>" * n}</div>'
            f'<div class="net">{icon(bus_icon, "var(--navy)", 22)}{bus_text}</div>'
            f'<div class="plat">{base_title}<span>{base_sub}</span></div>')
    return page(body, css)


# ================================================================== 10. 甘特图
STREAM_COLORS = ["#8EA1B8", "#5E7896", "#1F3A5F", "#B49A72"]


def gantt(tasks, weeks, streams, milestones=None, after=None, prep=True):
    """tasks: [(任务名 ≤ 10 字, 开始周, 结束周, 工作线名)]，第 0 周表示“准备”；
    streams: [工作线名]（≤ 4 条，依次取 STREAM_COLORS）；milestones: {周: 名称}；after: (标签, 说明) 验收后服务。"""
    cols = weeks + (1 if prep else 0)
    off = 0 if prep else 1
    color = dict(zip(streams, STREAM_COLORS))
    head = '<div class="lbl wkh">周次</div>' + ('<div class="wk">准备</div>' if prep else "") + "".join(f'<div class="wk">{i}</div>' for i in range(1, weeks + 1))
    grid = '<div class="cell"></div>' * cols
    rows = ""
    for name, s, e, k in tasks:
        rows += (f'<div class="lbl">{name}</div><div class="track" style="grid-column:2 / span {cols}">{grid}'
                 f'<div class="bar" style="left:calc({s - off} * 100% / {cols} + 3px);width:calc({e - s + 1} * 100% / {cols} - 6px);background:{color[k]}"></div></div>')
    if milestones:
        rows += f'<div class="lbl ms-l">里程碑</div><div class="track" style="grid-column:2 / span {cols}">{grid}'
        rows += "".join(f'<div class="ms" style="left:calc({w - off + 0.5} * 100% / {cols})"><i></i><span>{t}</span></div>' for w, t in milestones.items())
        rows += "</div>"
    legend = "".join(f'<span><i style="background:{color[k]}"></i>{k}</span>' for k in streams)
    css = f"""
    .g{{display:grid;grid-template-columns:230px repeat({cols},1fr);row-gap:8px}}
    .wk{{font-size:13px;color:var(--sub);text-align:center;padding-bottom:4px;border-bottom:1px solid var(--line)}}
    .lbl{{font-size:15px;display:flex;align-items:center;justify-content:flex-end;padding-right:14px;white-space:nowrap}}
    .track{{position:relative;display:grid;grid-template-columns:repeat({cols},1fr);height:28px}}
    .cell{{border-left:1px dashed #E3E8EE}}
    .bar{{position:absolute;top:4px;height:20px;border-radius:5px}}
    .ms-l{{color:var(--sub)}}.wkh{{font-size:13px;color:var(--sub);border-bottom:1px solid var(--line);padding-bottom:4px}}
    .ms{{position:absolute;top:0;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center}}
    .ms i{{width:14px;height:14px;background:var(--gold);transform:rotate(45deg);margin-top:3px}}
    .ms span{{font-size:12.5px;color:{GOLD_INK};margin-top:6px;white-space:nowrap}}
    .after{{margin-top:34px;display:flex;align-items:center;gap:12px;font-size:14.5px;color:var(--sub)}}
    .after b{{background:var(--mist);color:var(--navy);padding:6px 14px;border-radius:6px;font-weight:600}}
    """
    tail = f'<div class="after"><b>{after[0]}</b>{after[1]}</div>' if after else ""
    return page(f'<div class="legend">{legend}</div><div class="g">{head}{rows}</div>{tail}', css)


# ================================================================== 11. 方案对比图
def compare(options, recommend=None):
    """options: [(方案名, 一句定位, [(要点, 是否优势)])]，2–3 个；recommend 为推荐方案下标（加“建议”角标）。"""
    cards = ""
    for i, (name, pos, points) in enumerate(options):
        pts = "".join(f'<li class="{"ok" if good else "no"}">{icon("circle-check" if good else "triangle-alert", NAVY if good else GOLD, 18)}<span>{p}</span></li>'
                      for p, good in points)
        tag = '<em>建议</em>' if i == recommend else ""
        cards += f'<div class="op {"rec" if i == recommend else ""}">{tag}<h4>{name}</h4><p>{pos}</p><ul>{pts}</ul></div>'
    css = f"""
    .ops{{display:grid;grid-template-columns:repeat({len(options)},1fr);gap:14px}}
    .op{{border:1px solid var(--line);border-radius:12px;padding:18px;background:var(--paper);position:relative}}
    .op.rec{{border:2px solid var(--navy);background:#fff}}
    .op em{{position:absolute;top:-12px;right:16px;font-style:normal;background:var(--navy);color:#fff;font-size:13px;padding:3px 12px;border-radius:12px}}
    .op h4{{font-size:19px;color:var(--navy)}}.op p{{font-size:14.5px;color:var(--sub);margin:4px 0 12px}}
    .op ul{{list-style:none}}.op li{{display:flex;gap:8px;align-items:flex-start;font-size:15px;margin:8px 0}}
    """
    return page(f'<div class="ops">{cards}</div>', css)


# ================================================================== 12. 场景全景图
def scenario_grid(groups):
    """groups: [(分组名, 图标, [(图标, 场景名 ≤ 8 字, 一句价值 ≤ 14 字)])]，2–4 组，每组 2–4 个场景。
    用于汇报版“应用场景全景”：按使用对象或业务领域分组。"""
    cols = ""
    for gname, gic, items in groups:
        cards = "".join(f'<div class="sc"><div class="si">{icon(ic, "var(--navy)", 24)}</div><div><b>{n}</b><span>{d}</span></div></div>'
                        for ic, n, d in items)
        cols += f'<div class="grp"><div class="gh">{icon(gic, "#fff", 20)}<span>{gname}</span></div><div class="gb">{cards}</div></div>'
    css = f"""
    .gs{{display:grid;grid-template-columns:repeat({len(groups)},1fr);gap:14px}}
    .grp{{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--paper)}}
    .gh{{background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;gap:8px;padding:12px;font-size:17px;font-weight:600}}
    .gb{{padding:12px;display:flex;flex-direction:column;gap:10px}}
    .sc{{display:flex;gap:12px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px}}
    .si{{width:44px;height:44px;border-radius:10px;background:var(--mist);display:flex;align-items:center;justify-content:center;flex:none}}
    .sc b{{display:block;font-size:16px}}.sc span{{display:block;font-size:13.5px;color:var(--sub);margin-top:3px}}
    """
    return page(f'<div class="gs">{cols}</div>', css)


# ================================================================== 13. AI 助手对话示意
def chat_mock(title, dialogs, footnote="示意图，实际界面以系统为准"):
    """dialogs: [(提问, 回答, 出处说明)]，2–3 组；回答 ≤ 40 字，出处如“数据来源：客流库，2026-09”。
    用于直观展示 AI 怎么用。必须标注“示意”。"""
    msgs = ""
    for q, a, src in dialogs:
        msgs += (f'<div class="q"><span class="tx">{q}</span>{icon("users", "var(--slate)", 22)}</div>'
                 f'<div class="a">{icon("bot", "var(--navy)", 22)}<div><span class="tx">{a}</span><em>{src}</em></div></div>')
    css = """
    .win{border:1px solid var(--line);border-radius:14px;overflow:hidden;background:var(--paper)}
    .bar{background:var(--navy);color:#fff;padding:12px 18px;font-size:17px;font-weight:600;display:flex;gap:8px;align-items:center}
    .body{padding:16px 22px;display:flex;flex-direction:column;gap:12px}
    .q{display:flex;justify-content:flex-end;align-items:center;gap:10px}
    .q .tx{background:var(--navy);color:#fff;border-radius:14px 14px 4px 14px;padding:10px 16px;font-size:15.5px;max-width:70%}
    .a{display:flex;gap:10px;align-items:flex-start}
    .a>div{background:#fff;border:1px solid var(--line);border-radius:14px 14px 14px 4px;padding:10px 16px;max-width:78%}
    .a .tx{display:block;font-size:15.5px}.a em{display:block;font-style:normal;font-size:13px;color:var(--sub);margin-top:6px}
    .fn{font-size:13px;color:var(--sub);text-align:right;margin-top:8px}
    """
    return page(f'<div class="win"><div class="bar">{icon("sparkles", "#fff", 20)}{title}</div><div class="body">{msgs}</div></div><div class="fn">{footnote}</div>', css)


# ================================================================== 14. 创新点卡片
def innovation_grid(items, cols=2):
    """items: [(图标, 创新点名 ≤ 10 字, 传统做法 ≤ 18 字, 本方案 ≤ 22 字)]，4–8 个，按 cols 列排布。"""
    cards = "".join(
        f'<div class="iv"><div class="ih"><em>{i + 1:02d}</em>{icon(ic, "var(--navy)", 24)}<b>{t}</b></div>'
        f'<div class="row old"><i>传统</i><span>{old}</span></div><div class="row new"><i>本方案</i><span>{new}</span></div></div>'
        for i, (ic, t, old, new) in enumerate(items))
    css = f"""
    .ivs{{display:grid;grid-template-columns:repeat({cols},1fr);gap:12px}}
    .iv{{border:1px solid var(--line);border-radius:12px;padding:14px 16px;background:#fff}}
    .ih{{display:flex;align-items:center;gap:10px;margin-bottom:10px}}
    .ih em{{font-style:normal;font-size:14px;font-weight:700;color:var(--steel)}}.ih b{{font-size:17px;color:var(--navy)}}
    .row{{display:flex;gap:10px;align-items:flex-start;font-size:14.5px;margin-top:6px}}
    .row i{{font-style:normal;flex:none;width:52px;text-align:center;font-size:12.5px;border-radius:10px;padding:2px 0}}
    .old i{{background:var(--paper);color:var(--sub);border:1px solid var(--line)}}.old span{{color:var(--sub)}}
    .new i{{background:var(--navy);color:#fff}}
    """
    return page(f'<div class="ivs">{cards}</div>', css)
