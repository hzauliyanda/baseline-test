#!/usr/bin/env python3
"""
全量回归总览报告生成器（2026-08-16 起 UI 段数据源 = 纯 ego runner）
读取:
  auto/ui-ego-exec-result.json — ego_ui_runner.py 输出（22 场景）
  auto/api-exec-result.json — API runner 输出
  docs/checklists/普通工单-人工校验清单.md — L2 人工清单
输出:
  docs/reports/普通工单-全量回归-<date>.html
"""
import json, os, re, base64, datetime, subprocess

ROOT  = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(ROOT, "auto", "screenshots", "ui")

# ── 模块参数：优先读 baseline.yaml（kit 标准），缺失时回退默认 ────────────────
import glob as _glob
try:
    import yaml as _yaml
    _bl = _yaml.safe_load(open(os.path.join(ROOT, "baseline.yaml"), encoding="utf-8")) or {}
except Exception:
    _bl = {}
MODULE_TITLE = _bl.get("title") or _bl.get("module") or os.path.basename(ROOT)
_report_pat = ((_bl.get("regression") or {}).get("report")) or f"{MODULE_TITLE}-全量回归总览-YYYY-MM-DD.html"
if not os.path.dirname(_report_pat):          # 裸文件名 → 默认进 docs/reports/
    _report_pat = os.path.join("docs", "reports", _report_pat)
_checklists = sorted(_glob.glob(os.path.join(ROOT, "docs", "checklists", "*.md")))
CHECKLIST_DEFAULT = os.path.basename(_checklists[0]) if _checklists else f"{MODULE_TITLE}-人工校验清单.md"

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def b64(path):
    if not os.path.exists(path): return ""
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

# ── 读数据 ────────────────────────────────────────────────────────────────────
ego  = load(os.path.join(ROOT, "auto", "ui-ego-exec-result.json"))
api  = load(os.path.join(ROOT, "auto", "api-exec-result.json"))

checklist_path = os.path.join(ROOT, "docs", "checklists", CHECKLIST_DEFAULT)
checklist_md = open(checklist_path, encoding="utf-8").read() if os.path.exists(checklist_path) else ""

# ── 解析 ego 结果 JSON ────────────────────────────────────────────────────────
def parse_ego(e):
    """records → 场景聚合：状态 = 任一 FAIL→failed；否则全 SKIP→skipped；否则 passed"""
    order, by_scene = [], {}
    for r in e.get("records", []):
        sc = r["scene"]
        if sc not in by_scene:
            by_scene[sc] = {"title": sc, "status": None, "steps": [], "shots": [], "duration_ms": 0}
            order.append(sc)
        s = by_scene[sc]
        s["steps"].append(r)
        if r.get("shot") and r["shot"] not in s["shots"]:
            s["shots"].append(r["shot"])
    for sc, s in by_scene.items():
        st_map = {r["status"] for r in s["steps"]}
        s["status"] = ("failed" if "FAIL" in st_map
                       else "skipped" if st_map == {"SKIP"}
                       else "passed")
        meta = (e.get("scenes") or {}).get(sc) or {}
        s["title"] = meta.get("title", sc)
        s["duration_ms"] = meta.get("ms", 0)
    return [by_scene[sc] for sc in order]

ui_tests = parse_ego(ego)

ui_pass  = sum(1 for t in ui_tests if t["status"] == "passed")
ui_fail  = sum(1 for t in ui_tests if t["status"] == "failed")
ui_skip  = sum(1 for t in ui_tests if t["status"] == "skipped")
ui_total_ms = sum(t["duration_ms"] for t in ui_tests)

# ── 解析 API JSON ─────────────────────────────────────────────────────────────
api_pass = api_fail = api_steps = 0
api_db_checks = 0
for flow in api:
    for s in flow["steps"]:
        api_steps += 1
        if s["pass"]: api_pass += 1
        else: api_fail += 1
        if s.get("db_check"): api_db_checks += 1

# ── 解析人工清单 L2/L3 ────────────────────────────────────────────────────────
l2_items = re.findall(r'- \[ \] \*\*#\d+.*?\n(?:  - .*?\n)*', checklist_md)
l3_section = ""
m = re.search(r'## 🔴 人工覆盖清单.*', checklist_md, re.DOTALL)
if m:
    l3_section = m.group(0)[:3000]

# ── HTML 组件 ─────────────────────────────────────────────────────────────────
def status_badge(status):
    cfg = {
        "passed":  ("#52c41a", "#f6ffed", "PASS"),
        "failed":  ("#f5222d", "#fff1f0", "FAIL"),
        "skipped": ("#fa8c16", "#fff7e6", "SKIP"),
        "timedOut":("#f5222d", "#fff1f0", "TIMEOUT"),
    }
    c, bg, label = cfg.get(status, ("#888", "#fafafa", status.upper()))
    return f'<span style="background:{bg};color:{c};border:1px solid {c};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{label}</span>'

def api_status_badge(ok):
    return status_badge("passed" if ok else "failed")

def fmt_ms(ms):
    return f"{ms/1000:.1f}s" if ms >= 1000 else f"{ms}ms"

# ── UI 测试块 ─────────────────────────────────────────────────────────────────
def ui_test_rows():
    rows = []
    for t in ui_tests:
        sid = t["title"].split()[0]  # S1, S2, ...
        badge = status_badge(t["status"])
        dur   = fmt_ms(t["duration_ms"])

        steps_html = ""
        for st in t["steps"]:
            icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(st["status"], "·")
            detail = str(st.get("detail", ""))[:160].replace("<", "&lt;")
            shots_note = f' <span style="color:#1677ff;font-size:11px">📷</span>' if st.get("shot") else ""
            steps_html += (f'<div style="padding:3px 0;font-size:12px;border-bottom:1px dashed #eee">'
                           f'{icon} <strong>{st["step"]}</strong>{shots_note}'
                           f' — <span style="color:#666">{detail}</span></div>')

        shots_html = ""
        for shot_path in t["shots"]:
            src = b64(shot_path)
            if src:
                name = os.path.basename(shot_path)
                shots_html += (f'<div style="display:inline-block;vertical-align:top;margin:6px 8px 6px 0">'
                               f'<div style="font-size:11px;color:#888;margin-bottom:2px">{name}</div>'
                               f'<img src="{src}" style="max-width:480px;max-height:280px;border-radius:6px;'
                               f'border:1px solid #e8e8e8"></div>')

        detail_id = f"ui_{sid}"
        rows.append(f"""
<div style="border-bottom:1px solid #f0f0f0">
  <div onclick="toggle('{detail_id}')" style="padding:10px 16px;cursor:pointer;display:flex;align-items:center;gap:12px;user-select:none">
    <span style="font-size:12px;color:#aaa">▶</span>
    <strong style="min-width:200px">{t['title']}</strong>
    {badge}
    <span style="margin-left:auto;color:#aaa;font-size:12px">{dur}</span>
  </div>
  <div id="{detail_id}" style="display:none;padding:8px 40px 16px;background:#fafafa">
    {steps_html}
    <div style="margin-top:8px">{shots_html if shots_html else '<span style="color:#aaa;font-size:12px">无截图</span>'}</div>
  </div>
</div>""")
    return "\n".join(rows)

# ── API flow 块 ───────────────────────────────────────────────────────────────
def assert_rows(asserts):
    if not asserts: return '<tr><td colspan="4" style="padding:6px 12px;color:#aaa;font-size:12px">无断言</td></tr>'
    rows = []
    for a in asserts:
        ok    = a.get("pass", False)
        color = "#52c41a" if ok else "#f5222d"
        icon  = "✅" if ok else "❌"
        atype = a.get("type", "")
        path  = a.get("path", "—")
        exp   = str(a.get("expected", a.get("equals", a.get("contains", "—"))))[:80]
        act   = str(a.get("actual", "—"))[:80]
        rows.append(f"""<tr style="font-size:12px">
          <td style="padding:4px 10px;color:{color}">{icon}</td>
          <td style="padding:4px 10px;color:#555">{atype}</td>
          <td style="padding:4px 10px;font-family:monospace;color:#333">{path}</td>
          <td style="padding:4px 10px;color:#389e0d">{exp}</td>
          <td style="padding:4px 10px;color:{'#333' if ok else '#f5222d'}">{act}</td>
        </tr>""")
    return "\n".join(rows)

def api_flow_blocks():
    blocks = []
    for fi, flow in enumerate(api):
        fname = flow["file"]
        steps = flow["steps"]
        fp = sum(1 for s in steps if s["pass"])
        ff = len(steps) - fp
        flow_ok = flow["pass"]
        badge = api_status_badge(flow_ok)
        fid = f"flow_{fi}"

        step_rows = []
        for si, s in enumerate(steps):
            sid2 = f"step_{fi}_{si}"
            ok   = s["pass"]
            color = "#f6ffed" if ok else "#fff1f0"
            icon  = "✅" if ok else "❌"
            method = s.get("method","?")
            url    = s.get("url","")
            url_short = re.sub(r'https?://[^/]+', '', url)
            status = s.get("status", "?")
            elapsed = s.get("elapsed_ms", 0)
            desc   = s.get("desc","")
            preview  = (s.get("resp_preview","") or "")[:300]
            req_body = (s.get("req_body","") or "")
            db_check = s.get("db_check")

            db_html = ""
            if db_check:
                sql_items = db_check if isinstance(db_check, list) else [db_check]
                for item in sql_items:
                    sql  = item.get("sql","") if isinstance(item,dict) else str(item)
                    exp  = item.get("expect","") if isinstance(item,dict) else ""
                    reason = item.get("reason","") if isinstance(item,dict) else ""
                    db_html += f'<div style="margin-top:8px;padding:8px;background:#fffbe6;border-left:3px solid #faad14;font-size:11px"><strong>🟡 DB校验</strong> {reason}<br><code style="display:block;margin-top:4px;white-space:pre-wrap;color:#333">{sql}</code><span style="color:#666">期望：{exp}</span></div>'

            asserts_html = f"""<table style="width:100%;border-collapse:collapse;margin-top:8px">
              <thead><tr style="background:#f5f5f5;font-size:11px;color:#888">
                <th style="padding:4px 10px;width:28px"></th>
                <th style="padding:4px 10px;text-align:left">类型</th>
                <th style="padding:4px 10px;text-align:left">路径</th>
                <th style="padding:4px 10px;text-align:left">期望</th>
                <th style="padding:4px 10px;text-align:left">实际</th>
              </tr></thead>
              <tbody>{assert_rows(s.get('asserts',[]))}</tbody>
            </table>"""

            step_rows.append(f"""
<div style="border-bottom:1px solid #f0f0f0;background:{color}">
  <div onclick="toggle('{sid2}')" style="padding:8px 16px;cursor:pointer;display:flex;align-items:center;gap:10px;user-select:none;font-size:13px">
    <span style="font-size:11px;color:#aaa">▶</span>
    <code style="color:#333;min-width:40px">{method}</code>
    <span style="color:#555;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{url_short}</span>
    <span style="color:#888;font-size:11px">{desc}</span>
    <span style="color:#888;font-size:11px">{status} · {elapsed}ms</span>
  </div>
  <div id="{sid2}" style="display:none;padding:8px 32px 12px">
    {asserts_html}
    {db_html}
    {f'''<details style="margin-top:8px"><summary style="font-size:11px;color:#888;cursor:pointer">Request Body</summary>
      <pre style="font-size:11px;background:#f0f5ff;padding:8px;border-radius:4px;overflow-x:auto;max-height:200px;margin-top:4px">{req_body}</pre>
    </details>''' if req_body else ''}
    <details style="margin-top:8px"><summary style="font-size:11px;color:#888;cursor:pointer">Response Preview</summary>
      <pre style="font-size:11px;background:#f5f5f5;padding:8px;border-radius:4px;overflow-x:auto;max-height:200px;margin-top:4px">{preview}</pre>
    </details>
  </div>
</div>""")

        blocks.append(f"""
<div style="margin-bottom:20px;border:1px solid #e8e8e8;border-radius:8px;overflow:hidden">
  <div onclick="toggle('{fid}')" style="padding:12px 18px;background:#fafafa;border-bottom:1px solid #e8e8e8;cursor:pointer;display:flex;align-items:center;gap:12px;user-select:none">
    <span style="font-size:12px;color:#aaa">▶</span>
    <strong style="flex:1">{fname}</strong>
    {badge}
    <span style="font-size:12px;color:#888">PASS {fp} / {len(steps)}</span>
  </div>
  <div id="{fid}" style="display:none">{"".join(step_rows)}</div>
</div>""")
    return "\n".join(blocks)

# ── L3 人工覆盖清单块（只取 🔴 人工覆盖清单 段，L2 DB校验已内嵌在各 API step 里） ──
def _parse_l3_rows():
    """返回 (tier_label, [场景, step-id, 期望]) 列表"""
    m = re.search(r'## 🔴 人工覆盖清单(.*?)(?=\n## |\Z)', checklist_md, re.DOTALL)
    if not m:
        return []
    section = m.group(1)

    result = []
    current_tier = "Tier ?"
    for line in section.split('\n'):
        tier_m = re.match(r'### (Tier \S+)', line)
        if tier_m:
            current_tier = tier_m.group(1)
            continue
        # markdown table data row: starts with | , not a separator row (|---|)
        if line.startswith('|') and not re.match(r'\|[-:| ]+\|', line):
            cols = [c.strip() for c in line.strip('|').split('|')]
            # skip header rows (first col contains Chinese header keywords)
            if cols and cols[0] in ('场景', '链', ''):
                continue
            if len(cols) >= 1 and cols[0]:
                scene = re.sub(r'`', '', cols[0])
                step_id = re.sub(r'`', '', cols[1]) if len(cols) > 1 else ''
                expect = cols[-1] if len(cols) > 1 else ''
                result.append((current_tier, scene, step_id, expect))
    return result

def checklist_block():
    rows_data = _parse_l3_rows()
    if not rows_data:
        return "<p style='color:#aaa'>未找到🔴人工覆盖清单项</p>"

    # Group by tier
    tiers = {}
    for tier, scene, step_id, expect in rows_data:
        tiers.setdefault(tier, []).append((scene, step_id, expect))

    TIER_COLORS = {'Tier 1': '#ff4d4f', 'Tier 2': '#fa8c16', 'Tier 3': '#1677ff'}
    html_parts = []
    for tier, items in tiers.items():
        color = TIER_COLORS.get(tier, '#888')
        html_parts.append(f"""<div style="padding:8px 14px;background:#fafafa;border-bottom:1px solid #f0f0f0;font-size:12px;font-weight:600;color:{color}">{tier}</div>""")
        for scene, step_id, expect in items:
            step_html = f"<span style='font-size:11px;color:#888;margin-left:8px'>{step_id}</span>" if step_id else ""
            expect_html = f"<div style='font-size:11px;color:#555;margin-top:2px'>期望：{expect}</div>" if expect and expect != '期望' else ""
            html_parts.append(f"""<div style="padding:9px 14px;border-bottom:1px solid #f5f5f5;display:flex;gap:10px;align-items:flex-start">
  <input type="checkbox" style="margin-top:3px;flex-shrink:0">
  <div><div style="font-size:13px">{scene}{step_html}</div>{expect_html}</div>
</div>""")
    return "\n".join(html_parts)

def count_l3_items():
    return len(_parse_l3_rows())

# ── 组装 HTML ─────────────────────────────────────────────────────────────────
date_str = datetime.date.today().isoformat()
time_str = datetime.datetime.now().strftime("%H:%M")
ui_dur   = fmt_ms(ui_total_ms)

html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{MODULE_TITLE} 全量回归总览 {date_str}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;color:#1a1a1a;background:#f5f5f5;padding:20px}}
.wrap{{max-width:1100px;margin:0 auto}}
.card{{background:#fff;border-radius:10px;border:1px solid #e8e8e8;margin-bottom:20px;overflow:hidden}}
.card-header{{padding:14px 20px;border-bottom:1px solid #e8e8e8;display:flex;align-items:center;justify-content:space-between;background:#fafafa}}
.card-header h2{{font-size:15px;font-weight:600}}
.summary{{display:flex;gap:14px;flex-wrap:wrap;padding:18px 20px}}
.stat{{padding:12px 18px;border-radius:8px;text-align:center;min-width:80px}}
.stat .n{{font-size:24px;font-weight:700;line-height:1.1}}
.stat .l{{font-size:11px;margin-top:3px;color:#666}}
a.btn{{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;background:#1677ff;color:#fff;border-radius:6px;text-decoration:none;font-size:13px}}
a.btn:hover{{background:#0958d9}}
details summary{{cursor:pointer}}
</style>
<script>
function toggle(id){{
  var el=document.getElementById(id);
  var arrow=el.previousElementSibling.querySelector('span:first-child');
  if(el.style.display==='none'){{el.style.display='block';if(arrow)arrow.textContent='▼'}}
  else{{el.style.display='none';if(arrow)arrow.textContent='▶'}}
}}
</script>
</head>
<body>
<div class="wrap">

<!-- 标题 -->
<div class="card">
  <div style="padding:20px 24px">
    <h1 style="font-size:20px;font-weight:700;margin-bottom:4px">{MODULE_TITLE} 全量回归总览</h1>
    <p style="color:#888;font-size:13px">执行时间：{date_str} {time_str}</p>
    <div class="summary" style="padding:14px 0 0">
      <div>
        <p style="font-size:12px;color:#888;margin-bottom:8px;font-weight:500">UI 回归（{len(ui_tests)} 场景 · 纯 ego）</p>
        <div style="display:flex;gap:10px">
          <div class="stat" style="background:#f6ffed;border:1px solid #b7eb8f"><div class="n" style="color:#52c41a">{ui_pass}</div><div class="l">PASS</div></div>
          <div class="stat" style="background:#fff1f0;border:1px solid #ffa39e"><div class="n" style="color:#f5222d">{ui_fail}</div><div class="l">FAIL</div></div>
          <div class="stat" style="background:#fff7e6;border:1px solid #ffd591"><div class="n" style="color:#fa8c16">{ui_skip}</div><div class="l">SKIP</div></div>
          <div class="stat" style="background:#f5f5f5;border:1px solid #d9d9d9"><div class="n" style="color:#555">{ui_dur}</div><div class="l">耗时</div></div>
        </div>
      </div>
      <div style="width:1px;background:#e8e8e8;margin:0 4px"></div>
      <div>
        <p style="font-size:12px;color:#888;margin-bottom:8px;font-weight:500">API 回归（5 flows）</p>
        <div style="display:flex;gap:10px">
          <div class="stat" style="background:#f6ffed;border:1px solid #b7eb8f"><div class="n" style="color:#52c41a">{api_pass}</div><div class="l">PASS</div></div>
          <div class="stat" style="background:#fff1f0;border:1px solid #ffa39e"><div class="n" style="color:#f5222d">{api_fail}</div><div class="l">FAIL</div></div>
          <div class="stat" style="background:#f5f5f5;border:1px solid #d9d9d9"><div class="n" style="color:#555">{api_steps}</div><div class="l">总 step</div></div>
        </div>
      </div>
      <div style="width:1px;background:#e8e8e8;margin:0 4px"></div>
      <div>
        <p style="font-size:12px;color:#888;margin-bottom:8px;font-weight:500">人工待核对</p>
        <div style="display:flex;gap:10px">
          <div class="stat" style="background:#fffbe6;border:1px solid #ffe58f"><div class="n" style="color:#d48806">{api_db_checks}</div><div class="l">🟡 DB校验</div></div>
          <div class="stat" style="background:#fff1f0;border:1px solid #ffa39e"><div class="n" style="color:#cf1322">{count_l3_items()}</div><div class="l">🔴 人工项</div></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- UI 回归 -->
<div class="card">
  <div class="card-header">
    <h2>UI 回归（{len(ui_tests)} 场景 · ego-browser）</h2>
    <span style="font-size:12px;color:#888">截图目录 auto/screenshots/ui/ · 步骤明细 auto/ui-ego-exec-result.json</span>
  </div>
  <div style="padding:4px 0">
    {ui_test_rows()}
  </div>
</div>

<!-- API 回归 -->
<div class="card">
  <div class="card-header">
    <h2>API 回归（5 flows · {api_steps} steps）</h2>
    <span style="font-size:13px;color:#888">展开查看每步断言 + Response</span>
  </div>
  <div style="padding:16px">
    {api_flow_blocks()}
  </div>
</div>

<!-- 人工覆盖清单（L3）-->
<div class="card">
  <div class="card-header">
    <h2>🔴 人工覆盖清单（{count_l3_items()} 项）</h2>
    <span style="font-size:12px;color:#888">🟡 DB 校验 SQL 已内嵌在上方 API 回归各 step；此处仅列无法自动化的人工确认项</span>
  </div>
  <div>
    {checklist_block()}
  </div>
</div>

</div>
</body>
</html>"""

out = os.path.join(ROOT, _report_pat.replace("YYYY-MM-DD", date_str))
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ 报告已生成：{out}")
subprocess.Popen(["open", out])
