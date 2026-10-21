"""方案配图：HTML/CSS 设计，Chrome 无头渲染为高清 PNG，输出到 docs/素材/。

配色：藏青 / 石板灰 / 雾蓝为主，低饱和暖金只用于“空置”“人工确认”等少量强调。
图标：Lucide（ISC 许可），位于 scripts/docs/assets/icons/。
用法：python scripts/docs/figures.py
"""
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ICONS = HERE / "assets" / "icons"
OUT = HERE.parents[1] / "docs" / "素材"

CSS = """
:root{--navy:#1F3A5F;--slate:#3E5C76;--steel:#7489A3;--mist:#E6ECF2;--paper:#F5F7FA;--line:#D5DDE6;
--ink:#1F2933;--sub:#66727F;--gold:#A8875A;--goldbg:#F7F2EA;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#fff;font-family:"Microsoft YaHei","微软雅黑",sans-serif;color:var(--ink);}
#fig{width:1000px;padding:26px 28px;background:#fff}
.ic{display:inline-flex;width:22px;height:22px;flex:none}
.ic svg{width:100%;height:100%;stroke-width:1.8}
.row{display:flex;gap:14px}
.card{background:var(--paper);border:1px solid var(--line);border-radius:10px}
.sub{color:var(--sub)}
.legend{display:flex;gap:22px;justify-content:flex-end;font-size:15px;color:var(--sub);margin-bottom:14px}
.legend i{display:inline-block;width:16px;height:16px;border-radius:4px;vertical-align:-3px;margin-right:6px}
"""


def icon(name, color="currentColor", size=22):
    svg = (ICONS / f"{name}.svg").read_text(encoding="utf-8")
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S).strip()
    return f'<span class="ic" style="color:{color};width:{size}px;height:{size}px">{svg}</span>'


FONT_SCALE = 1.2  # 图插入 A4 后宽约 15.5cm，放大字号保证图内文字不小于约 8 磅


def _scale_fonts(css):
    return re.sub(r"font-size:([\d.]+)px", lambda m: f"font-size:{float(m.group(1)) * FONT_SCALE:.1f}px", css)


def page(body, extra_css=""):
    css = _scale_fonts(CSS + extra_css)
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body><div id='fig'>{body}</div></body></html>"


# ---------------------------------------------------------------- 图：项目概况
def fig_overview():
    kpis = [
        ("building-2", "可租面积", "2.81", "万㎡", "集中式开放街区", False),
        ("store", "在营商家", "75", "家", "餐饮、配套、金融等", False),
        ("chart-line", "餐饮商家占比", "50.7", "%", "餐饮独大，配套偏弱", False),
        ("map", "空置面积", "3,010", "㎡", "约占可租面积 10.7%", True),
    ]
    k = "".join(
        f"""<div class="kpi {'warn' if w else ''}"><div class="kh">{icon(i, 'var(--gold)' if w else 'var(--slate)')}<span>{t}</span></div>
        <div class="kv"><b>{v}</b><small>{u}</small></div><div class="kn">{n}</div></div>""" for i, t, v, u, n, w in kpis)
    floors = [
        ("3F", ["正餐", "酒楼宴请", "生活配套"], None),
        ("2F", ["正餐", "酒楼宴请", "生活配套"], "空置集中 · 非主动线"),
        ("1F", ["休闲餐饮", "展示体验"], None),
        ("B1", ["快餐", "食堂", "娱乐"], "空置集中 · 非主动线"),
    ]
    f = "".join(
        f"""<div class="fl"><div class="fn">{n}</div><div class="fb">{''.join(f'<span class="chip">{c}</span>' for c in chips)}
        {f'<span class="vac">{icon("triangle-alert", "var(--gold)", 18)}{v}</span>' if v else ''}</div></div>""" for n, chips, v in floors)
    css = """
    .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
    .kpi{border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:#fff;border-top:4px solid var(--slate)}
    .kpi.warn{border-top-color:var(--gold);background:var(--goldbg)}
    .kh{display:flex;align-items:center;gap:8px;font-size:16px;color:var(--sub)}
    .kv{margin-top:8px}.kv b{font-size:34px;color:var(--navy);font-weight:700;letter-spacing:.5px}
    .kn{font-size:14px;color:var(--sub);margin-top:4px}.kpi.warn .kv b{color:#7A5F38}.kv small{font-size:15px;color:var(--sub);margin-left:6px}
    .stack{border:1px solid var(--line);border-radius:12px;padding:16px;background:var(--paper)}
    .st{font-size:16px;color:var(--sub);margin-bottom:12px}
    .fl{display:flex;gap:12px;margin-bottom:10px}.fl:last-child{margin-bottom:0}
    .fn{width:70px;height:54px;border-radius:8px;background:var(--navy);color:#fff;font-size:22px;font-weight:700;display:flex;align-items:center;justify-content:center}
    .fb{flex:1;background:#fff;border:1px solid var(--line);border-radius:8px;display:flex;align-items:center;gap:10px;padding:0 16px}
    .chip{font-size:17px;padding:5px 14px;border-radius:20px;background:var(--mist);color:var(--navy)}
    .vac{margin-left:auto;display:flex;align-items:center;gap:6px;font-size:15px;color:#7A5F38;background:var(--goldbg);border:1px solid #E2D3BC;padding:5px 12px;border-radius:20px}
    """
    return page(f'<div class="kpis">{k}</div><div class="stack"><div class="st">楼层业态分布</div>{f}</div>', css)


# ---------------------------------------------------------------- 图：餐饮结构
def fig_dining():
    data = [("正餐", 33), ("酒楼商务宴请", 23), ("快餐", 20), ("食堂", 15), ("休闲餐饮", 9.3)]
    shades = ["#1F3A5F", "#2F4C6E", "#4A6582", "#7489A3", "#A3B3C6"]
    bars = "".join(
        f"""<div class="br"><span class="bl">{n}</span><div class="bt"><div class="bf" style="width:{v / 35 * 100:.1f}%;background:{c}"></div></div>
        <span class="bv">{v:g}%</span></div>""" for (n, v), c in zip(data, shades))
    acc, stops = 0, []
    for (_, v), c in zip(data, shades):
        stops.append(f"{c} {acc}% {acc + v}%")
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
    body = f"""<div class="wrap"><div class="donut" style="background:conic-gradient({','.join(stops)})">
    <div class="dc"><b>50.7%</b><span>餐饮商家占比</span></div></div><div class="bars">
    <div style="font-size:16px;color:var(--sub);margin-bottom:4px">餐饮内部结构</div>{bars}</div></div>
    <div class="tip">正餐与酒楼宴请合计 56%，以商务和午市需求为主；晚市、周末和家庭客群的潜力尚未发挥。</div>"""
    return page(body, css)


# ---------------------------------------------------------------- 图：数据底座
def fig_hub():
    src = [("footprints", "客流计数器", "出入口 · 楼层 · 进店"), ("printer", "小票打印机", "每笔交易金额"),
           ("gauge", "智能电表", "商户与公区用电"), ("flame", "动火离人设备", "厨房报警记录"),
           ("file-spreadsheet", "明源导出文件", "合同 · 收费 · 欠费"), ("smartphone", "小程序", "销售补报 · 巡查整改")]
    app = [("monitor", "驾驶舱 · 经营问答"), ("file-text", "AI 运营月报"), ("heart-pulse", "商户健康预警"),
           ("handshake", "招商与业态分析"), ("siren", "能耗与安全提醒"), ("book-open", "知识库助手")]
    s = "".join(f'<div class="it card">{icon(i, "var(--slate)", 26)}<div><b>{t}</b><span>{d}</span></div></div>' for i, t, d in src)
    a = "".join(f'<div class="it card">{icon(i, "var(--slate)", 24)}<div><b>{t}</b></div></div>' for i, t in app)
    css = """
    .cols{display:grid;grid-template-columns:1fr 46px 1.05fr 46px 1fr;align-items:start}
    .hd{font-size:15px;color:var(--sub);text-align:center;margin-bottom:10px;letter-spacing:2px}
    .list{display:flex;flex-direction:column;gap:12px;justify-content:center;min-height:540px}
    .it{display:flex;align-items:center;gap:14px;padding:14px 16px;background:#fff}
    .it b{display:block;font-size:17px;font-weight:600}.it span{display:block;font-size:14px;color:var(--sub);margin-top:2px}
    .ar{display:flex;align-items:center;justify-content:center;color:var(--steel);font-size:30px;height:540px;margin-top:32px}
    .core{background:var(--navy);border-radius:14px;color:#fff;padding:22px 20px;display:flex;flex-direction:column;justify-content:center;gap:14px;min-height:540px}
    .core h4{font-size:21px;font-weight:600;text-align:center;display:flex;gap:8px;align-items:center;justify-content:center}
    .libs{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    .lib{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.22);border-radius:8px;padding:10px;text-align:center;font-size:16px}
    .band{background:#fff;color:var(--navy);border-radius:8px;padding:11px;text-align:center;font-size:16px;font-weight:600}
    .band span{display:block;font-size:13px;font-weight:400;color:var(--sub);margin-top:2px}
    .q{font-size:13px;text-align:center;color:#C9D4E0}
    """
    body = f"""<div class="cols">
    <div><div class="hd">数据从哪里来</div><div class="list">{s}</div></div>
    <div class="ar">›</div>
    <div><div class="hd">统一存放 · 统一口径</div><div class="core"><h4>{icon("database", "#fff", 24)}数据底座</h4>
      <div class="libs"><div class="lib">客流</div><div class="lib">销售</div><div class="lib">能耗</div><div class="lib">安全报警</div><div class="lib">租赁与合同</div><div class="lib">商户与铺位</div></div>
      <div class="band">统一指标库<span>每个指标只定义一次</span></div>
      <div class="q">入库前自动校验 · 异常单独标记</div></div></div>
    <div class="ar">›</div>
    <div><div class="hd">用在哪里</div><div class="list">{a}</div></div></div>"""
    return page(body, css)


# ---------------------------------------------------------------- 图：五条业务主线
def fig_lanes():
    lanes = [
        ("database", "数据采集", [("设备采集", 0), ("自动检查", 0), ("核实异常", 1), ("数据入库", 0), ("指标计算", 0)]),
        ("chart-line", "经营分析", [("自动取数", 0), ("程序计算", 0), ("AI 写初稿", 0), ("人工复核", 1), ("发布导出", 0)]),
        ("heart-pulse", "商户预警", [("每周评分", 0), ("分级", 0), ("推送责任人", 0), ("走访核实", 1), ("跟进处理", 1)]),
        ("handshake", "招商", [("铺位档案", 0), ("业态分析", 0), ("线索带看", 1), ("合同比对", 0), ("签约确认", 1)]),
        ("clipboard-check", "营运巡查", [("排班派单", 0), ("巡查拍照", 1), ("问题登记", 1), ("商户整改", 1), ("复查闭环", 1)]),
        ("flame", "厨房安全", [("设备监测", 0), ("无人超时", 0), ("现场报警", 0), ("推送通知", 0), ("处置记录", 1)]),
        ("gauge", "能耗管理", [("电表采集", 0), ("用电统计", 0), ("异常提醒", 0), ("现场核查", 1), ("处理记录", 1)]),
    ]
    rows = ""
    for ic, name, steps in lanes:
        cells = ""
        for i, (t, human) in enumerate(steps):
            badge = f'<em>{icon("user-check", "#7A5F38", 14)}</em>' if human else f"<em>{i + 1}</em>"
            cells += f'<div class="sp {"hm" if human else ""}">{badge}<span>{t}</span></div>'
            if i < len(steps) - 1:
                cells += '<div class="ar">›</div>'
        rows += f'<div class="lane"><div class="ln">{icon(ic, "#fff", 22)}<span>{name}</span></div><div class="steps">{cells}</div></div>'
    css = """
    .lane{display:flex;gap:14px;margin-bottom:12px;align-items:stretch}.lane:last-child{margin-bottom:0}
    .ln{width:136px;flex:none;background:var(--navy);color:#fff;border-radius:10px;display:flex;align-items:center;justify-content:center;gap:8px;font-size:17px;font-weight:600}
    .steps{flex:1;display:flex;align-items:center;background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
    .sp{flex:1;height:52px;white-space:nowrap;background:#fff;border:1px solid var(--line);border-radius:8px;display:flex;align-items:center;gap:8px;padding:0 8px;font-size:16px}
    .sp em{font-style:normal;width:22px;height:22px;border-radius:50%;background:var(--mist);color:var(--slate);font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:none}
    .sp.hm{border-color:#D9C6A6;background:var(--goldbg)}.sp.hm em{background:#EADFCB;color:#7A5F38}
    
    .ar{width:14px;text-align:center;color:var(--steel);font-size:20px;flex:none}
    """
    legend = '<div class="legend"><span><i style="background:#fff;border:1px solid #D5DDE6"></i>系统自动完成</span><span><i style="background:#F7F2EA;border:1px solid #D9C6A6"></i>人工操作或确认</span></div>'
    return page(legend + rows, css)


# ---------------------------------------------------------------- 图：租户健康度
def fig_health():
    dims = [("经营能力", 40, "#1F3A5F", "租售比 · 坪效 · 销售趋势"), ("客流吸引", 20, "#3E5C76", "进店客流 · 进店率"),
            ("履约状况", 25, "#5E7896", "欠费 · 报送及时性"), ("经营规范", 15, "#8EA1B8", "巡查 · 安全报警 · 营业时长")]
    bar = "".join(f'<div class="seg" style="flex:{w};background:{c}"><b>{n}</b><span>{w} 分</span></div>' for n, w, c, _ in dims)
    desc = "".join(f'<div style="flex:{w}" class="sd">{d}</div>' for _, w, _, d in dims)
    lv = [("健康", "80–100", "#1F3A5F", "正常经营，例行关注"), ("关注", "60–79", "#7489A3", "营运人员重点留意"),
          ("预警", "40–59", "#B49A72", "推送营运和招商跟进"), ("高危", "0–39", "#8A6A4F", "走访帮扶，储备替换品牌")]
    lvs = "".join(f'<div class="lv"><div class="lt" style="background:{c}"><b>{n}</b><span>{r} 分</span></div><p>{d}</p></div>' for n, r, c, d in lv)
    reds = ["租管费连续欠缴超过 60 天", "连续 2 个月租售比超过本业态预警线", "连续 2 个月无销售数据", "连续 7 天无营业迹象且未报备"]
    rl = "".join(f"<li>{x}</li>" for x in reds)
    css = """
    .t{font-size:16px;color:var(--sub);margin:0 0 10px}
    .bar{display:flex;height:66px;border-radius:10px;overflow:hidden}
    .seg{color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;border-right:2px solid #fff}
    .seg:last-child{border-right:none}.seg b{font-size:17px}.seg span{font-size:14px;opacity:.85}
    .sds{display:flex;margin-top:6px}.sd{font-size:13.5px;color:var(--sub);text-align:center}
    .lvs{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:22px}
    .lv{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}
    .lt{color:#fff;padding:12px;text-align:center}.lt b{font-size:20px;display:block}.lt span{font-size:14px;opacity:.9}
    .lv p{font-size:14.5px;padding:10px;text-align:center;color:var(--ink)}
    .red{margin-top:18px;background:var(--goldbg);border:1px solid #E2D3BC;border-radius:10px;padding:14px 18px;display:flex;gap:14px}
    .red h5{font-size:16px;color:#7A5F38;white-space:nowrap;display:flex;gap:6px;align-items:flex-start}
    .red ul{list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:6px 24px;font-size:15px}
    .red li::before{content:"·";color:#A8875A;margin-right:8px;font-weight:700}
    """
    body = f"""<div class="t">打分维度与权重（满分 100 分）</div><div class="bar">{bar}</div><div class="sds">{desc}</div>
    <div class="lvs">{lvs}</div>
    <div class="red"><h5>{icon("triangle-alert", "#A8875A", 20)}红线规则<br></h5><ul>{rl}</ul></div>
    <div style="font-size:13.5px;color:var(--sub);margin-top:8px">命中任一红线，无论得分直接列为“预警”及以上；“营业迹象”结合用电和进店客流判断。</div>"""
    return page(body, css)


# ---------------------------------------------------------------- 图：合同建档
def fig_contract():
    steps = [("cloud-upload", "上传合同", "扫描件 / PDF", 0), ("scan-line", "AI 抽取条款", "租期、租金等", 0),
             ("search", "交叉核对", "与明源台账比对", 0), ("user-check", "人工确认", "只看差异字段", 1),
             ("database", "回填档案", "写入门店档案", 0), ("bell", "自动提醒", "到期递增提醒", 0)]
    items = ""
    for i, (ic, t, d, h) in enumerate(steps):
        items += f'<div class="st {"hm" if h else ""}"><div class="cir">{icon(ic, "#7A5F38" if h else "#fff", 26)}</div><b>{t}</b><span>{d}</span></div>'
        if i < len(steps) - 1:
            items += '<div class="ln"></div>'
    css = """
    .flow{display:flex;align-items:flex-start}
    .st{width:128px;flex:none;text-align:center}
    .cir{width:64px;height:64px;border-radius:50%;background:var(--navy);margin:0 auto 10px;display:flex;align-items:center;justify-content:center}
    .st.hm .cir{background:var(--goldbg);border:2px solid #C9B08A}
    .st b{display:block;font-size:17px}.st span{display:block;font-size:13.5px;color:var(--sub);margin-top:3px}
    .ln{flex:1;height:2px;background:var(--line);margin-top:32px;position:relative}
    .ln::after{content:"";position:absolute;right:-1px;top:-4px;border:5px solid transparent;border-left:7px solid #B8C4D1}
    .foot{display:flex;gap:14px;margin-top:20px}
    .fbx{flex:1;background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:12px 16px;font-size:14.5px;color:var(--ink)}
    .fbx b{color:var(--navy)}
    """
    body = f"""<div class="flow">{items}</div><div class="foot">
    <div class="fbx"><b>抽取字段：</b>租期、起租日、到期日、免租期、租金及递增、管理费、保证金、扣点、经营范围、撤场条款、违约条款</div>
    <div class="fbx"><b>风险提示：</b>偏离标准合同模板的条款自动标出，由招商或法务确认</div></div>"""
    return page(body, css)


# ---------------------------------------------------------------- 图：AI 可控五道防线
def fig_guard():
    g = [("target", "只用既定指标", "只从统一指标库取数，不自己编查询"),
         ("circle-check", "数字程序回填", "报告数字由程序填入，发布前核对"),
         ("quote", "回答注明出处", "附原文出处，合同可定位到页码"),
         ("ban", "无依据不回答", "没有依据明确拒答，不编造"),
         ("user-check", "人工确认生效", "合同、巡检、月报由人确认")]
    cards = "".join(f'<div class="g"><div class="n">0{i + 1}</div>{icon(ic, "var(--navy)", 30)}<b>{t}</b><p>{d}</p></div>' for i, (ic, t, d) in enumerate(g))
    css = """
    .top{display:flex;justify-content:center;gap:0;margin-bottom:18px}
    .role{padding:10px 26px;font-size:16px;background:var(--mist);color:var(--navy)}
    .role:first-child{border-radius:24px 0 0 24px}.role:last-child{border-radius:0 24px 24px 0}
    .role.mid{background:var(--navy);color:#fff}
    .gs{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
    .g{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:16px 14px;position:relative;text-align:center}
    .g .n{position:absolute;top:10px;left:12px;font-size:13px;color:var(--steel);font-weight:700}
    .g .ic{margin:8px auto 10px}.g b{display:block;font-size:16.5px;margin-bottom:6px}.g p{font-size:13.5px;color:var(--sub);line-height:1.55}
    """
    body = f"""<div class="top"><div class="role">AI 负责听懂问题、写文字</div><div class="role mid">程序负责计算数字</div><div class="role">人负责确认和决定</div></div>
    <div class="gs">{cards}</div>"""
    return page(body, css)


# ---------------------------------------------------------------- 图：系统架构
def fig_arch():
    layers = [
        ("使用端", "monitor", ["电脑端 Web", "运营端小程序", "商户端小程序"], False),
        ("AI 能力层", "sparkles", ["经营问答", "知识库", "合同提取", "运营月报", "健康预警", "数据检查"], True),
        ("平台应用层", "layers", ["驾驶舱", "多维分析", "招商招调", "营运管理", "门店管理", "空间设备", "能耗分析"], False),
        ("数据层", "database", ["客流", "销售", "能耗", "安全报警", "租赁与合同", "统一指标库"], False),
        ("数据接入层", "cloud-upload", ["设备直连上传", "电表采集平台接口", "小程序报送", "明源文件导入"], False),
        ("硬件层", "cpu", ["客流计数器 92 台", "小票打印机", "智能电表", "动火离人监测"], False),
    ]
    rows = ""
    for name, ic, items, ai in layers:
        chips = "".join(f'<div class="c">{x}</div>' for x in items)
        extra = '<div class="gw">模型网关：统一调用本地或经批准的国产大模型，可更换，故障自动切换</div>' if ai else ""
        rows += f'<div class="ly {"ai" if ai else ""}"><div class="lb">{icon(ic, "#fff", 20)}<span>{name}</span></div><div class="bd"><div class="cs">{chips}</div>{extra}</div></div>'
    css = """
    .wrap{display:flex;gap:12px}.main{flex:1}
    .ly{display:flex;gap:10px;margin-bottom:9px}.ly:last-child{margin-bottom:0}
    .lb{width:138px;flex:none;background:var(--slate);color:#fff;border-radius:8px;display:flex;align-items:center;justify-content:center;gap:8px;font-size:16px;font-weight:600}
    .ly.ai .lb{background:var(--navy)}
    .bd{flex:1;background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:8px}
    .ly.ai .bd{background:var(--mist);border-color:#BFCCDA}
    .cs{display:flex;gap:8px}.c{flex:1;background:#fff;border:1px solid var(--line);border-radius:6px;text-align:center;padding:11px 4px;font-size:15px}
    .gw{margin-top:8px;background:var(--navy);color:#fff;border-radius:6px;text-align:center;font-size:14px;padding:7px}
    .side{width:64px;flex:none;background:var(--paper);border:1px solid var(--line);border-radius:8px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;color:var(--slate)}
    .side b{writing-mode:vertical-rl;font-size:15px;letter-spacing:6px;color:var(--navy);margin-bottom:8px}
    .side .si{font-size:14px;color:var(--ink);background:#fff;border:1px solid var(--line);border-radius:6px;padding:6px 0;width:42px;text-align:center}
    """
    body = f'<div class="wrap"><div class="main">{rows}</div><div class="side">{icon("lock", "var(--slate)", 22)}<b>安全保障</b><span class="si">权限</span><span class="si">加密</span><span class="si">审计</span><span class="si">备份</span></div></div>'
    return page(body, css)


# ---------------------------------------------------------------- 图：实施计划
def fig_gantt():
    weeks = 14
    cols = weeks + 1  # 准备 + 第 1..14 周
    streams = {"调研": "#8EA1B8", "硬件": "#5E7896", "软件": "#1F3A5F", "测试": "#B49A72"}
    tasks = [
        ("启动准备", 0, 0, "调研"),
        ("现场调研与设备勘察", 1, 2, "调研"),
        ("平台部署与基础数据", 1, 3, "软件"),
        ("客流计数器安装", 3, 5, "硬件"),
        ("动火离人试装与安装", 4, 7, "硬件"),
        ("智能电表安装与接入", 4, 8, "硬件"),
        ("小票打印机安装与配置", 5, 9, "硬件"),
        ("建模、合同建档、知识库", 3, 6, "软件"),
        ("AI 功能开发与配置", 6, 10, "软件"),
        ("联合测试", 10, 11, "测试"),
        ("培训与试用", 12, 12, "测试"),
        ("试运行与验收", 13, 14, "测试"),
    ]
    ms = {2: "勘察方案确认", 9: "硬件全部接入", 11: "测试完成", 14: "项目验收"}
    head = '<div class="lbl wkh">周次</div>' + '<div class="wk">准备</div>' + "".join(f'<div class="wk">{i}</div>' for i in range(1, weeks + 1))
    grid = "".join('<div class="cell"></div>' for _ in range(cols))
    body_rows = ""
    for name, s_, e, k in tasks:
        span = e - s_ + 1
        body_rows += (f'<div class="lbl">{name}</div><div class="track" style="grid-column:2 / span {cols}">{grid}'
                      f'<div class="bar" style="left:calc({s_} * 100% / {cols} + 3px);width:calc({span} * 100% / {cols} - 6px);background:{streams[k]}"></div></div>')
    mrow = f'<div class="lbl ms-l">里程碑</div><div class="track" style="grid-column:2 / span {cols}">{grid}'
    for w, t in ms.items():
        mrow += f'<div class="ms" style="left:calc({w + 0.5} * 100% / {cols})"><i></i><span>{t}</span></div>'
    mrow += "</div>"
    legend = "".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in
                     (("调研与勘察", streams["调研"]), ("硬件安装", streams["硬件"]), ("软件与 AI", streams["软件"]), ("测试 · 培训 · 验收", streams["测试"])))
    css = """
    .g{display:grid;grid-template-columns:230px repeat(COLS,1fr);row-gap:8px}
    .wk{font-size:13px;color:var(--sub);text-align:center;padding-bottom:4px;border-bottom:1px solid var(--line)}
    .lbl{font-size:15px;display:flex;align-items:center;justify-content:flex-end;padding-right:14px;white-space:nowrap}
    .track{position:relative;display:grid;grid-template-columns:repeat(COLS,1fr);height:28px}
    .cell{border-left:1px dashed #E3E8EE}
    .bar{position:absolute;top:4px;height:20px;border-radius:5px}
    .ms-l{color:var(--sub)}.wkh{font-size:13px;color:var(--sub);border-bottom:1px solid var(--line);padding-bottom:4px}
    .ms{position:absolute;top:0;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center}
    .ms i{width:14px;height:14px;background:var(--gold);transform:rotate(45deg);margin-top:3px}
    .ms span{font-size:12.5px;color:#7A5F38;margin-top:6px;white-space:nowrap}
    .legend{margin-bottom:12px}
    .after{margin-top:34px;display:flex;align-items:center;gap:12px;font-size:14.5px;color:var(--sub)}
    .after b{background:var(--mist);color:var(--navy);padding:6px 14px;border-radius:6px;font-weight:600}
    """.replace("COLS", str(cols))
    body = (f'<div class="legend">{legend}</div><div class="g">{head}{body_rows}{mrow}</div>'
            '<div class="after"><b>验收后 3 个月</b>运营陪跑：每月数据复盘 · 预警规则校准 · 使用问题处理</div>')
    return page(body, css)


# ---------------------------------------------------------------- 图：硬件布置示意
def fig_hw_layout():
    zones = [
        ("door-open", "出入口与楼层通道", "双目型 / 半球型计数器", "进出人次", False),
        ("store", "商铺门口", "直筒型计数器", "门前、进店人次", False),
        ("printer", "商户收银台", "小票打印机", "每笔交易金额", False),
        ("gauge", "商户配电箱", "智能电表", "用电量、功率", False),
        ("flame", "餐饮厨房", "动火离人监测", "有火无人报警", True),
    ]
    cards = ""
    for ic, zone, dev, out, warm in zones:
        cards += (f'<div class="z {"warm" if warm else ""}"><div class="zh">{icon(ic, "#7A5F38" if warm else "var(--navy)", 26)}<span>{zone}</span></div>'
                  f'<div class="dv"><b>{dev}</b><span>{out}</span></div></div>')
    css = """
    .zs{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
    .z{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:16px 10px;text-align:center}
    .z.warm{background:var(--goldbg);border-color:#E2D3BC}
    .zh{display:flex;flex-direction:column;align-items:center;gap:8px;font-size:16px;font-weight:600;margin-bottom:12px;white-space:nowrap}
    .dv{background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 4px}
    .dv b{display:block;font-size:14.5px;color:var(--navy);white-space:nowrap}.dv span{display:block;font-size:13px;color:var(--sub);margin-top:3px}
    .down{display:grid;grid-template-columns:repeat(5,1fr);text-align:center;color:var(--steel);font-size:22px;margin:4px 0}
    .net{background:var(--mist);border-radius:10px;text-align:center;padding:12px;font-size:15px;color:var(--navy);display:flex;align-items:center;justify-content:center;gap:10px}
    .plat{margin-top:12px;background:var(--navy);color:#fff;border-radius:10px;text-align:center;padding:14px;font-size:17px;font-weight:600}
    .plat span{display:block;font-size:13.5px;font-weight:400;opacity:.85;margin-top:4px}
    """
    body = (f'<div class="zs">{cards}</div><div class="down"><span>↓</span><span>↓</span><span>↓</span><span>↓</span><span>↓</span></div>'
            f'<div class="net">{icon("wifi", "var(--navy)", 22)}供电与网络：每个点位需供电；园区有线网络或 4G 上传</div>'
            '<div class="plat">统一接入数据底座<span>设备与铺位绑定 · 在线状态监测 · 数据入库 · 报警记录</span></div>')
    return page(body, css)


FIGURES = {
    "项目概况.png": fig_overview,
    "餐饮结构.png": fig_dining,
    "数据底座.png": fig_hub,
    "业务线.png": fig_lanes,
    "租户健康度.png": fig_health,
    "合同建档流程.png": fig_contract,
    "硬件布置示意.png": fig_hw_layout,
    "AI可控五道防线.png": fig_guard,
    "系统架构.png": fig_arch,
    "实施计划.png": fig_gantt,
}


def render(names=None):
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("图*_*.png"):
        old.unlink()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        pg = browser.new_page(viewport={"width": 1000, "height": 800}, device_scale_factor=3)
        for name, fn in FIGURES.items():
            if names and name not in names:
                continue
            pg.set_content(fn(), wait_until="load")
            pg.locator("#fig").screenshot(path=str(OUT / name))
        browser.close()


if __name__ == "__main__":
    render()
    print("done")
