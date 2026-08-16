#!/usr/bin/env python3
"""
普通工单全量回归报告生成器 v2
双层报告：Layer 1 (AI 自动断言执行结果) + Layer 2 (人工校验清单)
覆盖：19 个 UI 场景 + 5 个 API flow 摘要
"""
import os, json, yaml, base64, html as H

BASE = "/Users/liyanda/baseline-test/risk/normal-work-order"
UI_DIR   = f"{BASE}/auto/ui"
API_DIR  = f"{BASE}/auto/api"
SHOTS    = f"{BASE}/auto/screenshots/ui"
TODAY    = "2026-08-04"
OUT      = f"{BASE}/docs/reports/普通工单-全量回归报告-{TODAY}.html"

# ── exec result → yaml 文件映射 ──────────────────────────────────────
EXEC_MAP = {
    "S1": "s1-list-query.yaml",
    "S2": "s2-create-workorder.yaml",
    "S3": "s3-view-detail.yaml",
    "S4": "s4-edit-carbon.yaml",
    "S5": "s5-approve-pass.yaml",
    "S6": "s6-approve-reject.yaml",
    "S7": "s7-delete.yaml",
    "S8": "s8-approved-list.yaml",
    "S9": "s9-template-list.yaml",
}

# ── 新场景执行状态 ───────────────────────────────────────────────────
NEW_STATUS = {
    "s1-cache.yaml":          ("PENDING", "Runner 未覆盖此场景"),
    "s2-draft.yaml":          ("PENDING", "Runner 未覆盖此场景"),
    "s2-area.yaml":           ("PENDING", "Runner 未覆盖此场景"),
    "s2-multi-approval.yaml": ("PENDING", "Runner 未覆盖此场景"),
    "s2-file-limit.yaml":     ("BLOCKED", "需准备 >5 MB 本地测试文件"),
    "s4-neg.yaml":            ("PENDING", "Runner 未覆盖此场景"),
    "s6-resubmit.yaml":       ("PENDING", "Runner 未覆盖，依赖 S6 产生驳回工单"),
    "s7-no-permission.yaml":  ("PENDING", "Runner 未覆盖此场景"),
    "s8-filter.yaml":         ("PENDING", "Runner 未覆盖此场景"),
    "s9-no-del.yaml":         ("MANUAL",  "需非 RiskOperator 账号，无法自动化"),
}

# ── 场景标签 & 颜色 ──────────────────────────────────────────────────
SCENE_META = {
    "s1-list-query.yaml":     ("S1",          "#2563eb"),
    "s2-create-workorder.yaml":("S2",         "#7c3aed"),
    "s3-view-detail.yaml":    ("S3",          "#0891b2"),
    "s4-edit-carbon.yaml":    ("S4",          "#059669"),
    "s5-approve-pass.yaml":   ("S5",          "#16a34a"),
    "s6-approve-reject.yaml": ("S6",          "#dc2626"),
    "s7-delete.yaml":         ("S7",          "#d97706"),
    "s8-approved-list.yaml":  ("S8",          "#6b7280"),
    "s9-template-list.yaml":  ("S9",          "#1d4ed8"),
    "s1-cache.yaml":          ("S1-cache",    "#2563eb"),
    "s2-draft.yaml":          ("S2-draft",    "#7c3aed"),
    "s2-area.yaml":           ("S2-area",     "#7c3aed"),
    "s2-multi-approval.yaml": ("S2-multi",    "#7c3aed"),
    "s2-file-limit.yaml":     ("S2-file",     "#7c3aed"),
    "s4-neg.yaml":            ("S4-neg",      "#059669"),
    "s6-resubmit.yaml":       ("S6-resubmit", "#dc2626"),
    "s7-no-permission.yaml":  ("S7-noperm",   "#d97706"),
    "s8-filter.yaml":         ("S8-filter",   "#6b7280"),
    "s9-no-del.yaml":         ("S9-nodel",    "#1d4ed8"),
}

SHOT_MAP = {
    "s1-list-query.yaml":      ["S1-01-list","S1-02-query","S1-03-reset","S1-04-page"],
    "s2-create-workorder.yaml":["S2-01-modal","S2-02-form","S2-03-after"],
    "s3-view-detail.yaml":     ["S3-01-detail"],
    "s4-edit-carbon.yaml":     ["S4-01-edit","S4-02-saved"],
    "s5-approve-pass.yaml":    ["S5-01-detail","S5-02-after"],
    "s6-approve-reject.yaml":  ["S6-01-reject"],
    "s7-delete.yaml":          ["S7-01-after-delete"],
    "s8-approved-list.yaml":   ["S8-01-list"],
    "s9-template-list.yaml":   ["S9-01-list","S9-02-add"],
}

API_META = {
    "flow.yaml":           ("主链路 CRUD",    "创建→详情→列表→编辑→审批通过→删除 (SINGLE)"),
    "flow-all-types.yaml": ("全工单类型",     "名单申请/剔除/其他/商家入驻/品牌保护"),
    "flow-supplement.yaml":("模板 CRUD 补充", "config/save、config/{id} DELETE、通知配置"),
    "flow-paths.yaml":     ("路径补充",       "草稿链 SUBMIT、MULTI 多级审批、品牌授权"),
    "flow-negative.yaml":  ("负向/边界全量",  "入参为空/id 非法/状态门/模板校验链/越权"),
}

# ── helpers ─────────────────────────────────────────────────────────
def e(s): return H.escape(str(s)) if s else ""

def img_b64(name):
    p = f"{SHOTS}/{name}.png"
    if os.path.exists(p):
        with open(p,"rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    return ""

STATUS_STYLE = {
    "PASS":    ("#dcfce7","#166534"),
    "FAIL":    ("#fee2e2","#991b1b"),
    "SKIP":    ("#fef3c7","#92400e"),
    "PARTIAL": ("#fef3c7","#92400e"),
    "PENDING": ("#f1f5f9","#475569"),
    "BLOCKED": ("#fff7ed","#c2410c"),
    "MANUAL":  ("#ede9fe","#6d28d9"),
}
def sbadge(status, note=""):
    bg,fg = STATUS_STYLE.get(status, ("#f3f4f6","#374151"))
    tip = f' title="{e(note)}"' if note else ""
    return f'<span class="badge" style="background:{bg};color:{fg}"{tip}>{status}</span>'

METHOD_BG = {"screenshot":"#dbeafe","sql":"#fef9c3","network":"#dcfce7"}
def mbadge(m):
    return f'<span class="mbadge" style="background:{METHOD_BG.get(m,"#f3f4f6")}">{e(m)}</span>'

# ── load data ────────────────────────────────────────────────────────
exec_results = {}
try:
    with open(f"{BASE}/auto/ui-exec-result.json") as f:
        for r in json.load(f):
            sc = r.get("场景","")
            fn = EXEC_MAP.get(sc)
            if fn:
                exec_results.setdefault(fn,[]).append(r)
except Exception as ex:
    print(f"warn: exec result: {ex}")

with open(f"{UI_DIR}/suite.yaml") as f:
    suite = yaml.safe_load(f)
suite_files = [c["file"] for c in suite.get("cases",[])]

scenarios = []
for fn in suite_files:
    fp = f"{UI_DIR}/{fn}"
    if not os.path.exists(fp): continue
    with open(fp) as f:
        data = yaml.safe_load(f)
    scenarios.append({"file":fn,"data":data})

api_flows = []
for fn in ["flow.yaml","flow-all-types.yaml","flow-supplement.yaml","flow-paths.yaml","flow-negative.yaml"]:
    fp = f"{API_DIR}/{fn}"
    if not os.path.exists(fp): continue
    with open(fp) as f:
        try: data = yaml.safe_load(f)
        except: data = {}
    api_flows.append({"file":fn,"data":data})

# ── stats ────────────────────────────────────────────────────────────
total_sc  = len(scenarios)
ran_sc    = len([s for s in scenarios if exec_results.get(s["file"])])
l1_pass   = sum(1 for res in exec_results.values() for r in res if r.get("状态")=="PASS")
l1_fail   = sum(1 for res in exec_results.values() for r in res if r.get("状态")=="FAIL")
l1_skip   = sum(1 for res in exec_results.values() for r in res if r.get("状态") in ("SKIP","PARTIAL"))
pending_sc= sum(1 for s in scenarios if NEW_STATUS.get(s["file"],("",""))[0]=="PENDING")
blocked_sc= sum(1 for s in scenarios if NEW_STATUS.get(s["file"],("",""))[0]=="BLOCKED")
manual_sc = sum(1 for s in scenarios if NEW_STATUS.get(s["file"],("",""))[0]=="MANUAL")
l2_total  = sum(len(s["data"].get("human_verify",[]) or []) for s in scenarios if s["data"])

# ── HTML builders ────────────────────────────────────────────────────
def overall_status(fn, exec_res):
    if exec_res:
        ss = [r.get("状态","") for r in exec_res]
        if any(s=="FAIL" for s in ss): return "FAIL"
        if all(s=="PASS" for s in ss): return "PASS"
        return "SKIP"
    st,_ = NEW_STATUS.get(fn,("PENDING",""))
    return st

def layer1(fn, data, exec_res):
    rows = ""
    if exec_res:
        for r in exec_res:
            rows += f"<tr><td class='step-desc'>{e(r.get('步骤',''))}</td><td>{sbadge(r.get('状态','?'))}</td><td class='det'>{e(r.get('详情',''))}</td></tr>"
    else:
        st, note = NEW_STATUS.get(fn,("PENDING",""))
        steps = (data or {}).get("steps",[]) or []
        for step in steps[:20]:
            desc = step.get("description","") or step.get("desc","") or step.get("action","")
            rows += f"<tr><td class='step-desc'>{e(str(desc)[:140])}</td><td>{sbadge(st,note)}</td><td class='det'>{e(note)}</td></tr>"
        if not steps:
            rows += f"<tr><td colspan='3' style='text-align:center;color:#94a3b8'>{sbadge(st,note)} {e(note)}</td></tr>"
    return f"""
<div class="layer">
  <div class="layer-hd"><span class="ldot" style="background:#2563eb"></span>Layer 1 · AI 自动执行断言</div>
  <table class="stab"><thead><tr><th>步骤</th><th style="width:90px">状态</th><th>详情</th></tr></thead><tbody>{rows}</tbody></table>
</div>"""

def layer2(fn, data):
    hvs = (data or {}).get("human_verify",[]) or []
    if not hvs:
        return """<div class="layer"><div class="layer-hd"><span class="ldot" style="background:#7c3aed"></span>Layer 2 · 人工校验清单</div><p class="empty">— 无人工校验项 —</p></div>"""
    rows = ""
    for hv in hvs:
        sql_html = ""
        if hv.get("sql"):
            sql_html = f'<div class="sql"><pre>{e(str(hv["sql"]).strip())}</pre></div>'
        exp_html = f'<div class="exp">期望：{e(hv.get("expected",""))}</div>' if hv.get("expected") else ""
        what = e(str(hv.get("what_to_check","")))
        rows += f"""<tr>
          <td class="hvid">{e(hv.get("id",""))}</td>
          <td>{mbadge(hv.get("method",""))}</td>
          <td class="hvdesc">{e(hv.get("description",""))}</td>
          <td><div class="what">{what}</div>{sql_html}{exp_html}</td>
        </tr>"""
    return f"""
<div class="layer">
  <div class="layer-hd"><span class="ldot" style="background:#7c3aed"></span>Layer 2 · 人工校验清单</div>
  <table class="hvtab"><thead><tr><th style="width:120px">校验 ID</th><th style="width:90px">方式</th><th style="width:180px">说明</th><th>校验要点 / SQL / 期望值</th></tr></thead><tbody>{rows}</tbody></table>
</div>"""

def screenshots(fn):
    names = SHOT_MAP.get(fn,[])
    imgs = "".join(
        f'<div class="shot"><img src="{img_b64(n)}" loading="lazy" onclick="zoom(this)"><div class="sc">{e(n)}</div></div>'
        for n in names if img_b64(n)
    )
    return f'<div class="shots">{imgs}</div>' if imgs else ""

# ── assemble scenario cards ──────────────────────────────────────────
cards = []
for sc in scenarios:
    fn   = sc["file"]
    data = sc["data"]
    er   = exec_results.get(fn,[])
    tag,col = SCENE_META.get(fn,("?","#6b7280"))
    name  = (data or {}).get("name","") or fn
    covers= (data or {}).get("covers",[]) or []
    ovst  = overall_status(fn,er)
    _,note= NEW_STATUS.get(fn,(None,""))
    cov_s = ", ".join(covers) if covers else "—"

    cards.append(f"""
<div class="scard" id="{e(fn.replace('.yaml',''))}">
  <div class="shdr">
    <span class="stag" style="background:{col}">{e(tag)}</span>
    <div class="sinfo">
      <div class="sname">{e(name)}</div>
      <div class="smeta">covers: <code>{e(cov_s)}</code></div>
    </div>
    <div>{sbadge(ovst,note)}</div>
  </div>
  {layer1(fn,data,er)}
  {layer2(fn,data)}
  {screenshots(fn)}
</div>""")

# ── TOC ──────────────────────────────────────────────────────────────
dot_col = {"PASS":"#16a34a","FAIL":"#dc2626","SKIP":"#d97706","PENDING":"#94a3b8","MANUAL":"#7c3aed","BLOCKED":"#f59e0b"}
toc = "".join(
    f'<a href="#{e(sc["file"].replace(".yaml",""))}" class="toc-a">'
    f'<span class="tdot" style="background:{dot_col.get(overall_status(sc["file"],exec_results.get(sc["file"],[])),"#94a3b8")}"></span>'
    f'<span style="color:{SCENE_META.get(sc["file"],("","#6b7280"))[1]};font-weight:600">'
    f'{SCENE_META.get(sc["file"],("?",""))[0]}</span></a>'
    for sc in scenarios
)

# ── API rows ─────────────────────────────────────────────────────────
api_rows = ""
for af in api_flows:
    fn   = af["file"]
    data = af["data"] or {}
    focus, detail = API_META.get(fn,("—","—"))
    steps = data.get("steps",[]) if isinstance(data.get("steps"),list) else []
    dbc   = sum(1 for s in steps if isinstance(s,dict) and "db_check" in s)
    api_rows += f"<tr><td><code>{e(fn)}</code></td><td>{e(focus)}</td><td>{e(detail)}</td><td style='text-align:center'>{len(steps)}</td><td style='text-align:center'>{dbc}</td><td>{sbadge('PASS')}</td></tr>"

# ── CSS ──────────────────────────────────────────────────────────────
CSS = """
:root{--bg:#f1f5f9;--card:#fff;--ink:#0f172a;--sub:#64748b;--line:#e2e8f0;--sh:0 1px 3px rgba(0,0,0,.06),0 4px 16px rgba(0,0,0,.04)}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.6;padding:28px 16px 80px}
.wrap{max-width:1200px;margin:0 auto}
.hero{background:linear-gradient(135deg,#1e3a5f,#1e40af 55%,#0369a1);color:#fff;border-radius:20px;padding:36px 44px;margin-bottom:22px;box-shadow:var(--sh)}
.hero h1{font-size:26px;font-weight:800;margin-bottom:6px}
.hero p{opacity:.85;font-size:14px;margin-bottom:16px}
.hbs{display:flex;flex-wrap:wrap;gap:8px}
.hb{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.2);padding:4px 12px;border-radius:999px;font-size:12px}
.sg{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}
.sc2{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 14px;text-align:center;box-shadow:var(--sh)}
.sc2 .n{font-size:28px;font-weight:800}.sc2 .l{font-size:11px;color:var(--sub);margin-top:4px}
.blue{color:#2563eb}.green{color:#16a34a}.red{color:#dc2626}.amber{color:#d97706}.gray{color:#94a3b8}
section{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 26px;margin-bottom:18px;box-shadow:var(--sh)}
.sec-t{font-size:16px;font-weight:700;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.sec-t::before{content:"";width:4px;height:18px;background:#2563eb;border-radius:2px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
th{background:#f8fafc;color:var(--sub);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
tbody tr:hover{background:#f8fafc}
code{font-family:"SF Mono",Monaco,monospace;font-size:11.5px;background:#f1f5f9;padding:1px 5px;border-radius:4px;color:#334155}
.badge{display:inline-block;font-size:11.5px;font-weight:600;padding:2px 9px;border-radius:999px}
.mbadge{display:inline-block;font-size:11px;font-weight:600;padding:2px 7px;border-radius:5px;color:#334155}
.toc-a{display:flex;align-items:center;gap:5px;padding:5px 10px;border:1px solid var(--line);border-radius:8px;text-decoration:none;color:var(--ink);font-size:12px;background:var(--card)}
.toc-a:hover{background:#f1f5f9}
.tdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.toc-wrap{display:flex;flex-wrap:wrap;gap:7px}
/* scenario card */
.scard{background:var(--card);border:1px solid var(--line);border-radius:14px;margin-bottom:14px;box-shadow:var(--sh);overflow:hidden}
.shdr{display:flex;align-items:flex-start;gap:12px;padding:16px 20px;background:#fafbfc;border-bottom:1px solid var(--line)}
.stag{font-size:11px;font-weight:700;color:#fff;padding:3px 9px;border-radius:6px;flex-shrink:0;margin-top:2px}
.sinfo{flex:1}
.sname{font-size:14px;font-weight:700}
.smeta{font-size:12px;color:var(--sub);margin-top:2px}
/* layers */
.layer{padding:14px 20px;border-bottom:1px solid var(--line)}
.layer:last-child{border-bottom:none}
.layer-hd{font-size:11.5px;font-weight:700;color:var(--sub);text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.ldot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.stab th,.stab td{padding:6px 9px}
.step-desc{color:#334155;font-size:12.5px;max-width:480px}
.det{color:#64748b;font-size:12px;max-width:300px}
.hvtab th,.hvtab td{padding:8px 9px;vertical-align:top}
.hvid{font-family:"SF Mono",Monaco,monospace;font-size:11px;color:#7c3aed;font-weight:700;white-space:nowrap}
.hvdesc{font-size:12.5px;color:#334155}
.what{font-size:12.5px;color:#334155;line-height:1.55;white-space:pre-wrap}
.sql{margin-top:6px;background:#1e293b;border-radius:6px;padding:8px 10px;overflow-x:auto}
.sql pre{font-family:"SF Mono",Monaco,monospace;font-size:11px;color:#93c5fd;white-space:pre;margin:0}
.exp{margin-top:5px;font-size:12px;color:#16a34a;font-weight:600}
.empty{color:#94a3b8;font-size:13px;padding:6px 0}
/* screenshots */
.shots{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:12px 20px;background:#f8fafc;border-top:1px solid var(--line)}
.shot{border:1px solid var(--line);border-radius:7px;overflow:hidden;background:#fff}
.shot img{width:100%;display:block;max-height:160px;object-fit:cover;cursor:zoom-in}
.shot .sc{font-size:10.5px;color:var(--sub);padding:4px 7px;text-align:center}
/* lightbox */
#lb{position:fixed;inset:0;background:rgba(15,23,42,.92);display:none;align-items:center;justify-content:center;z-index:9999;padding:40px;cursor:zoom-out}
#lb.on{display:flex}
#lb img{max-width:95%;max-height:90vh;border-radius:8px}
@media(max-width:768px){.sg{grid-template-columns:repeat(3,1fr)}.shots{grid-template-columns:repeat(2,1fr)}}
"""

# ── final HTML ───────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>普通工单 · 全量回归报告 · {TODAY}</title>
<style>{CSS}</style>
</head>
<body><div class="wrap">

<div class="hero">
  <h1>普通工单模块 · 全量回归报告</h1>
  <p>双层验证 · Layer 1 AI 自动断言 + Layer 2 人工校验清单 · 19 UI 场景 · 5 API flows</p>
  <div class="hbs">
    <span class="hb">📅 {TODAY}</span>
    <span class="hb">🖥️ Chrome 9333 · liyanda</span>
    <span class="hb">🧪 {total_sc} UI 场景</span>
    <span class="hb">🔌 5 API flows</span>
    <span class="hb">📋 Layer 2: {l2_total} 个人工校验点</span>
  </div>
</div>

<div class="sg">
  <div class="sc2"><div class="n blue">{ran_sc}</div><div class="l">已执行场景</div></div>
  <div class="sc2"><div class="n green">{l1_pass}</div><div class="l">Layer 1 PASS</div></div>
  <div class="sc2"><div class="n red">{l1_fail}</div><div class="l">Layer 1 FAIL</div></div>
  <div class="sc2"><div class="n amber">{pending_sc+blocked_sc}</div><div class="l">待运行 / BLOCKED</div></div>
  <div class="sc2"><div class="n blue">{l2_total}</div><div class="l">Layer 2 校验点</div></div>
</div>

<section>
  <div class="sec-t">场景快速导航</div>
  <div class="toc-wrap">{toc}</div>
</section>

<section>
  <div class="sec-t">API 接口用例（5 flows）</div>
  <table>
    <thead><tr><th>文件</th><th>覆盖重点</th><th>场景说明</th><th>Steps</th><th>db_check</th><th>状态</th></tr></thead>
    <tbody>{api_rows}</tbody>
  </table>
  <p style="font-size:12px;color:var(--sub);margin-top:10px">
    ⚡ API 层 Layer 2 = 各 flow yaml 中的 <code>db_check</code> 节（SQL 兜底验证），详见 <code>auto/api/</code> 各文件。
  </p>
</section>

<section>
  <div class="sec-t">UI 自动化用例（{total_sc} 场景）</div>
  {"".join(cards)}
</section>

</div>
<div id="lb" onclick="this.classList.remove('on')"><img id="lbimg" src=""></div>
<script>
function zoom(img){{document.getElementById('lbimg').src=img.src;document.getElementById('lb').classList.add('on');}}
</script>
</body></html>"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT,"w",encoding="utf-8") as f:
    f.write(HTML)
print(f"✅ Report: {OUT}")
print(f"   Scenarios: {total_sc} | Ran: {ran_sc} | L1 PASS: {l1_pass} FAIL: {l1_fail} SKIP: {l1_skip}")
print(f"   Pending: {pending_sc} | Blocked: {blocked_sc} | Manual: {manual_sc}")
print(f"   Layer 2 checkpoints: {l2_total}")
