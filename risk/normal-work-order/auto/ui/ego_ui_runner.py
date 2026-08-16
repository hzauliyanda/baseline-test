#!/usr/bin/env python3
"""ego_ui_runner：纯 ego-browser 驱动的 UI 全量回归执行器（无 9333 Chrome、无 Playwright）。

通道协议（2026-08-16 实测定型，背景与坑见 RUNNER.md）：
  - ego CLI 动作型调用回包概率性丢失 → 动作一律 fire-and-forget 注入 + 独立微读取轮询
  - useOrCreateTaskSpace/js() 会挂死     → claimTaskSpace(<已有id>) + cdp()
  - CLI 挂死                            → 看门狗超时 + killpg + pkill 残留
  - 中文注入脚本                        → base64(ascii backslashreplace)，页面侧 eval(atob())
  - antd 填值                           → cdp('Input.insertText') 原生管道（antd Form 认值）
  - tags 回车                           → 页面内合成 KeyboardEvent（CDP dispatchKeyEvent 不被 rc-select 认）
  - antd Select                         → mousedown 开启 + React native setter 搜索 + 全名精确匹配

场景（对齐 Playwright 版语义；S21 原版即缺号）：
  S1–S9   ← runner.spec.ts
  S10–S23 ← runner-augment.spec.ts
  全部实现在 ego_scenarios.py，本文件只做驱动 + 页面原语 + 入口。

产出：
  auto/screenshots/ui/{Sx}-ego-{NN}-{步骤}.png
  auto/ui-ego-exec-result.json

用法：
  python3 ego_ui_runner.py              # 全量 22 场景
  python3 ego_ui_runner.py S2 S15       # 指定场景
  EGO_DEBUG=1 python3 ego_ui_runner.py  # 打印 CLI 原始输出
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(BASE_DIR, "..", "..")
SHOT_DIR = os.path.join(PROJECT, "auto", "screenshots", "ui")
RESULT_FILE = os.path.join(PROJECT, "auto", "ui-ego-exec-result.json")
BASE_URL = "https://test-risk.inshopline.com"
LIST_URL = f"{BASE_URL}/risk-cooperation/cs/normal-work-order/list"
TPL_LIST_URL = f"{BASE_URL}/risk-cooperation/cs/normal-work-order/template"
TPL_ADD_URL = f"{BASE_URL}/risk-cooperation/cs/normal-work-order/template/add"
APPROVED_URL = f"{BASE_URL}/risk-cooperation/cs/normal-work-order/approved-list"

RECORDS = []
SCENE_MS = {}  # 场景 → 耗时 ms（main 循环里填充，供报告用）


# ── 记录与截图产物 ───────────────────────────────────────────────────────────
def rec(scene, step, status, detail, shot=None):
    RECORDS.append({"scene": scene, "step": step, "status": status, "detail": detail, "shot": shot})
    mark = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(status, "·")
    print(f"  {mark} {step} — {detail}" + (f"  [{os.path.basename(shot)}]" if shot else ""))


def shot_step(d, scene, n, desc):
    """按 {Sx}-ego-{NN}-{步骤} 命名截图，失败返回 None（不中断场景）。"""
    return d.shot(f"{scene}-ego-{n:02d}-{desc}")


def save_results():
    from ego_scenarios import TITLES  # 延迟导入避免环
    scenes = {}
    for r in RECORDS:
        s = scenes.setdefault(r["scene"], {"pass": 0, "fail": 0, "skip": 0})
        key = r["status"].lower()
        s[key] = s.get(key, 0) + 1
    for name, s in scenes.items():
        s["title"] = TITLES.get(name, name)
        s["ms"] = SCENE_MS.get(name, 0)
    out = {"runner": "ego", "started": time.strftime("%Y-%m-%d %H:%M:%S"), "records": RECORDS,
           "scenes": scenes,
           "summary": {"pass": sum(1 for r in RECORDS if r["status"] == "PASS"),
                       "fail": sum(1 for r in RECORDS if r["status"] == "FAIL"),
                       "skip": sum(1 for r in RECORDS if r["status"] == "SKIP")}}
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n结果落盘 {RESULT_FILE}（{out['summary']['pass']} PASS / {out['summary']['fail']} FAIL / {out['summary']['skip']} SKIP）")


def ego_log(d):
    try:
        return d.read("return window.__ego || []") or []
    except Exception:
        return []


def wait_log(d, token, timeout=30, interval=3):
    """轮询 window.__ego 直到出现 token（长脚本用，替代盲目 settle）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        logs = ego_log(d)
        if any(token in x for x in logs):
            return logs
        time.sleep(interval)
    return ego_log(d)


# ── ego 通道 driver ─────────────────────────────────────────────────────────
class EgoStuck(Exception):
    pass


class EgoDriver:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.space_id = None

    # -- 底层：带看门狗跑一段 ego CLI 脚本 ------------------------------------
    def _cli(self, script, timeout=25):
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write("ego-browser nodejs 2>&1 <<'EOF'\n" + script + "\nEOF\n")
            sh = f.name
        try:
            # 独立进程组：超时 killpg 才能连孙进程(ego-browser)一起杀掉、释放 stdout 管道
            p = subprocess.Popen(["bash", sh], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, start_new_session=True)
            try:
                out, _ = p.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(p.pid), 9)
                except ProcessLookupError:
                    pass
                out, _ = p.communicate(timeout=5)
                self._unstuck()
                raise EgoStuck(f"ego CLI 挂死（>{timeout}s），已 killpg 恢复")
            if self.verbose:
                print("    [ego-cli]", (out or "").strip()[:200])
            return out or ""
        finally:
            os.unlink(sh)

    @staticmethod
    def _unstuck():
        subprocess.run(["pkill", "-9", "-f", "ego-browser nodejs"], capture_output=True)
        time.sleep(1.5)

    def _space_prefix(self):
        return f"await claimTaskSpace({self.space_id})\n"

    # -- 初始化：发现任务空间 --------------------------------------------------
    def boot(self):
        for attempt in range(3):
            try:
                out = self._cli(
                    "const spaces = await listTaskSpaces()\n"
                    "cliLog('SPACES:' + JSON.stringify(spaces.map(s => ({id: s.id, name: s.name}))))\n",
                    timeout=15)
                m = re.search(r"SPACES:(\[.*\])", out)
                spaces = json.loads(m.group(1)) if m else []
                if not spaces:
                    raise EgoStuck("无任务空间（ego lite 未开或未建过空间）")
                self.space_id = spaces[0]["id"]
                print(f"✅ ego 任务空间: #{self.space_id} {spaces[0].get('name', '')}")
                return self
            except EgoStuck as e:
                print(f"    boot 重试 {attempt + 1}/3：{e}")
                time.sleep(2)
        raise SystemExit("❌ ego 通道不可用：请确认 ego lite 已打开")

    # -- 读取型 evaluate（带回包，用于状态确认；通道级无回包自动重试一次） ------
    def read(self, js, timeout=15):
        """页面内同步语句块（自动包成 IIFE），返回值 JSON 化带出。"""
        body = js.strip()
        if not body.startswith("(") and not body.startswith("JSON.stringify"):
            body = f"JSON.stringify((() => {{ {body} }})())"
        out = None
        m = None
        for attempt in range(2):
            out = self._cli(
                self._space_prefix() +
                "const r = await cdp('Runtime.evaluate', "
                f"{{ expression: {json.dumps(body)}, returnByValue: true }})\n"
                "cliLog('EVAL_OUT:' + String(r.result && r.result.value))\n", timeout=timeout)
            m = re.search(r"EVAL_OUT:(.*)", out)
            if m:
                break
            time.sleep(1.5)
        if not m:
            raise EgoStuck("read 无回包")
        raw = m.group(1).strip()
        if raw == "undefined":
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    # -- 动作型注入（fire-and-forget，副作用落地即算成功） ----------------------
    def fire(self, page_js, settle=3.0, timeout=20):
        """注入一段异步自跑脚本（中文自动转 \\u 转义）。settle 在 python 侧等——
        CLI 脚本本身秒回（长 await wait() 在 ego CLI 里会拖挂调用）。"""
        ascii_js = page_js.encode("ascii", "backslashreplace").decode()
        b64 = base64.b64encode(ascii_js.encode()).decode()
        self._cli(
            self._space_prefix() +
            f"cdp('Runtime.evaluate', {{ expression: \"eval(atob('{b64}'))\" }}).catch(() => {{}})\n",
            timeout=timeout)
        if settle > 0:
            time.sleep(settle)

    # -- 原生输入 / 回车 -------------------------------------------------------
    def type_text(self, text, timeout=15):
        self._cli(
            self._space_prefix() +
            f"cdp('Input.insertText', {{ text: {json.dumps(text)} }}).catch(() => {{}})\n",
            timeout=timeout)
        time.sleep(0.8)

    @staticmethod
    def enter_js():
        """页面内合成 Enter（rc-select tokenizer 只认 DOM keydown；CDP dispatchKeyEvent 无效）。"""
        return ("const i = document.activeElement;"
                "i.dispatchEvent(new KeyboardEvent('keydown',"
                "{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));"
                "i.dispatchEvent(new KeyboardEvent('keyup',"
                "{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));")

    # -- 截图 -------------------------------------------------------------------
    def shot(self, name):
        os.makedirs(SHOT_DIR, exist_ok=True)
        path = os.path.join(SHOT_DIR, f"{name}.png")
        out = self._cli(
            self._space_prefix() +
            "const r = await cdp('Page.captureScreenshot', { format: 'png' })\n"
            "cliLog('SHOT:' + (r && r.data ? r.data.length : 0) + ':' + ((r && r.data) || ''))\n",
            timeout=25)
        m = re.search(r"SHOT:(\d+):([A-Za-z0-9+/=]+)", out)
        if not m or not int(m.group(1)):
            print(f"    ⚠️ 截图失败: {name}")
            return None
        with open(path, "wb") as f:
            f.write(base64.b64decode(m.group(2)))
        return path


# ── 页面注入脚本原语（antd 适配；全部 fire-and-forget + __ego 日志回读） ─────
HELPERS = """
const sleep = ms => new Promise(r => setTimeout(r, ms));
const norm = t => (t || '').replace(/\\s+/g, '');
const log = (...a) => (window.__ego = window.__ego || []).push(a.join(' '));
const btn = t => Array.from(document.querySelectorAll('button,a,[role=button]')).find(e => norm(e.textContent) === norm(t));
const fireClick = el => { if (el) { el.click(); return true; } return false; };
const mdown = el => ['mousedown','mouseup','click'].forEach(t => el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window})));
const visibleDd = () => document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)');
const nativeSet = (inp, v) => {
  const proto = inp instanceof HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  const s = Object.getOwnPropertyDescriptor(proto, 'value').set;
  s.call(inp, v); inp.dispatchEvent(new Event('input', {bubbles:true}));
};
const findItem = labelText => Array.from(document.querySelectorAll('.ant-modal .ant-form-item'))
  .find(it => norm(((it.querySelector('.ant-form-item-label label') || {}).textContent || '')).includes(norm(labelText)));
"""


def _wrap(body):
    """JS 语句块 → async IIFE（带 __ego 日志与异常兜底）。"""
    return "(async () => {" + HELPERS + "\n  try {\n" + body + "\n  } catch (e) { log('ERR ' + e.message); }\n})();"


def js_goto(url):
    return f"location.href = '{url}'"


def js_click_text(text):
    return _wrap(f"log(fireClick(btn('{text}')) ? 'clicked:{text}' : 'NO-btn:{text}');")


def js_open_create_modal():
    """点「新建工单」→ 等弹窗（内置 24×500ms 按钮轮询 + 弹窗轮询）。"""
    return _wrap("""
    if (!document.querySelector('.ant-modal-content')) {
      let b = null;
      for (let i = 0; i < 24 && !b; i++) { b = btn('新建工单'); if (!b) await sleep(500); }
      if (!b) { log('NO-open-btn'); return; }
      b.click();
      for (let i = 0; i < 12 && !document.querySelector('.ant-modal-content'); i++) await sleep(300);
    }
    const m = document.querySelector('.ant-modal');
    log('modal-open width=' + (m && m.style ? m.style.width : ''));""")


def js_pick_radio_and_template(radio, tpl, focus_after=None):
    """选类型 radio + 工单模板（全名搜索精确匹配，防「多人」变体误选）。
    focus_after：选完后聚焦该 label 的 input（如 工单名称）。"""
    focus_js = ""
    if focus_after:
        focus_js = f"""
    const fi = findItem('{focus_after}');
    const ni = fi && fi.querySelector('input');
    if (ni) {{ ni.scrollIntoView({{ block: 'center' }}); ni.focus(); ni.click(); log('focused:{focus_after}'); }}"""
    return _wrap(f"""
    const r = Array.from(document.querySelectorAll('.ant-modal .ant-radio-wrapper'))
      .find(x => norm(x.textContent) === norm('{radio}'));
    if (!r) {{ log('NO-radio:{radio}'); return; }}
    (r.querySelector('input[type=radio]') || r).click();
    await sleep(900);
    const sel = document.querySelector('.ant-modal .ant-select-selector');
    if (!sel) {{ log('NO-select'); return; }}
    sel.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true }}));
    await sleep(500);
    const sIn = document.querySelector('.ant-modal .ant-select-selection-search-input');
    if (sIn) {{ sIn.focus(); nativeSet(sIn, '{tpl}'); }}
    let exact = null;
    for (let i = 0; i < 14; i++) {{
      await sleep(300);
      exact = Array.from((visibleDd() || {{ querySelectorAll: () => [] }}).querySelectorAll('.ant-select-item'))
        .find(o => norm(o.textContent) === norm('{tpl}'));
      if (exact) break;
    }}
    if (!exact) {{ log('NO-tpl:{tpl}'); return; }}
    exact.click();
    await sleep(1200);
    log('tpl-picked:{tpl}');
    log('fields:' + Array.from(document.querySelectorAll('.ant-modal .ant-form-item label')).map(l => norm(l.textContent)).join('|'));""" + focus_js)


def js_focus_modal_field(label):
    return _wrap(f"""
    const fi = findItem('{label}');
    const inp = fi && fi.querySelector('input');
    if (!inp) {{ log('NO-input:{label}'); return; }}
    inp.scrollIntoView({{ block: 'center' }}); inp.focus(); inp.click();
    log('focused:{label}');""")


def js_focus_expr(expr):
    """聚焦任意 JS 表达式选出的 input/textarea（会 select() 全选，便于覆盖输入）。"""
    return _wrap(f"""
    const el = {expr};
    if (!el) {{ log('NO-focus'); return; }}
    el.scrollIntoView({{ block: 'center' }}); el.focus(); el.click();
    if (el.select) el.select();
    log('focused');""")


def js_select_by_label(label, option, scope="body", placeholder=None):
    """从「指定 label 的 form-item」里的 Select 选一项（不搜索，直接精确点选项）。
    label 找不到时可按 placeholder 定位（S16 主键的兜底）。"""
    root = 'document.querySelector(".ant-modal") || document' if scope == "modal" else "document"
    fallback = ""
    if placeholder:
        fallback = f"""
    if (!sel) {{
      const s = Array.from(root.querySelectorAll('.ant-select')).find(x => /{placeholder}/.test((x.querySelector('.ant-select-selection-placeholder') || {{}}).textContent || ''));
      sel = s && s.querySelector('.ant-select-selector');
    }}"""
    return _wrap(f"""
    const root = {root};
    let fi = Array.from(root.querySelectorAll('.ant-form-item'))
      .find(it => norm((it.querySelector('.ant-form-item-label label') || {{}}).textContent || '') === norm('{label}'));
    let sel = fi && fi.querySelector('.ant-select-selector');""" + fallback + f"""
    if (!sel) {{ log('NO-label:{label}'); return; }}
    mdown(sel);
    let dd = null;
    for (let i = 0; i < 14; i++) {{ dd = visibleDd(); if (dd && dd.offsetHeight > 0) break; await sleep(250); }}
    if (!dd) {{ log('NO-dd:{label}'); return; }}
    await sleep(300);
    const opt = Array.from(dd.querySelectorAll('.ant-select-item-option')).find(o => norm(o.textContent) === norm('{option}'));
    if (!opt) {{ log('NO-opt:{option}@{label}'); return; }}
    mdown(opt);
    await sleep(800);
    log('picked:{label}={option}');""")


def js_row_action(action, row_contains=None):
    """表格行操作：等含该操作的行出现（16×500ms）再点。row_contains 可按行文本过滤（S6）。"""
    cond = (f"r.textContent.includes('{row_contains}') && " if row_contains else "") + \
           f"Array.from(r.querySelectorAll('a,button')).some(e => e.textContent.trim() === '{action}')"
    return _wrap(f"""
    let row = null;
    for (let i = 0; i < 16 && !row; i++) {{
      row = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row')).find(r => {cond});
      if (!row) await sleep(500);
    }}
    if (!row) {{ log('NO-row:{action}'); return; }}
    const b = Array.from(row.querySelectorAll('a,button')).find(e => e.textContent.trim() === '{action}');
    b.click();
    log('acted:{action}');""")


def js_row_action_td(action, td_conds):
    """按列值找行再点操作。td_conds: [(列号, 值), ...]（S19 待审批/liyanda、S20 已完结）。"""
    conds = " && ".join(f"c[{i}] === '{v}'" for i, v in td_conds)
    return _wrap(f"""
    let row = null;
    for (let i = 0; i < 10 && !row; i++) {{
      row = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
        .find(r => {{ const c = Array.from(r.querySelectorAll('td')).map(td => td.textContent.trim()); return {conds}; }});
      if (!row) await sleep(500);
    }}
    if (!row) {{ log('NO-row'); return; }}
    const v = Array.from(row.querySelectorAll('a,button')).find(a => a.textContent.trim() === '{action}');
    if (!v) {{ log('NO-view-btn'); return; }}
    v.click();
    log('acted:{action}');""")


def js_submit():
    """弹窗提交：预检校验错误 → 点确定 → 轮询弹窗关闭。"""
    return _wrap("""
    const errs = Array.from(document.querySelectorAll('.ant-modal .ant-form-item-explain-error')).map(e => e.textContent.trim());
    if (errs.length) { log('pre-errs:' + JSON.stringify(errs)); return; }
    const btn2 = document.querySelector('.ant-modal-footer .ant-btn-primary');
    if (!btn2) { log('NO-submit-btn'); return; }
    btn2.click();
    log('submitted');
    for (let i = 0; i < 16; i++) {
      await sleep(500);
      if (!document.querySelector('.ant-modal-content')) { log('modal-closed'); return; }
    }
    const errs2 = Array.from(document.querySelectorAll('.ant-modal .ant-form-item-explain-error')).map(e => e.textContent.trim());
    log('still-open:' + JSON.stringify(errs2));""")


def js_cancel_modal():
    """新建弹窗取消 = 右上角 X（底部只有 保存/完成）。"""
    return _wrap("""
    const x = document.querySelector('.ant-modal-close');
    if (x) { x.click(); log('cancelled'); return; }
    const c = Array.from(document.querySelectorAll('.ant-modal button')).find(b => norm(b.textContent) === '取消');
    if (c) { c.click(); log('cancelled'); return; }
    log('NO-close');""")


def js_remark_and_click(remark, label):
    """详情页审批：填备注（React native setter）→ 点 通过/驳回。"""
    return _wrap(f"""
    const desc = document.getElementById('approveDesc');
    if (desc) nativeSet(desc, '{remark}');
    await sleep(300);
    const b = btn('{label}');
    if (!b) {{ log('NO-btn:{label}'); return; }}
    b.click();
    log('clicked:{label} remark={remark}');""")


def js_pagination_next():
    return _wrap("""
    const n = document.querySelector('.ant-pagination-next:not(.ant-pagination-disabled) button')
      || document.querySelector('.ant-pagination-next:not(.ant-pagination-disabled)');
    if (n) { n.click(); log('next-clicked'); } else { log('next-disabled'); }""")


def js_delete_sweep(prefix):
    """循环删除含 prefix 的行（行内删除 → popconfirm 确认），最多 10 轮。"""
    return _wrap(f"""
    let deleted = 0;
    for (let round = 0; round < 10; round++) {{
      const row = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
        .find(r => r.textContent.includes('{prefix}'));
      if (!row) break;
      const del = Array.from(row.querySelectorAll('a,button')).find(e => e.textContent.trim() === '删除');
      if (!del) {{ log('NO-del-btn'); break; }}
      del.click();
      await sleep(800);
      const pop = document.querySelector('.ant-popconfirm,.ant-popover,.ant-modal');
      const ok = pop && Array.from(pop.querySelectorAll('button')).find(b => ['删除','确定','确认','OK'].includes(norm(b.textContent)));
      if (!ok) {{ log('NO-confirm'); break; }}
      ok.click();
      await sleep(1600);
      deleted++;
    }}
    const left = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
      .filter(r => r.textContent.includes('{prefix}')).length;
    log('sweep-done deleted:' + deleted + ' left:' + left);""")


# ── 常用读取表达式（read() 会自动包 IIFE + JSON 化） ──────────────────────────
R_ROWS = "return document.querySelectorAll('.ant-table-tbody tr.ant-table-row').length"
R_LABELS = ("return Array.from(document.querySelectorAll('.ant-form-item-label label'))"
            ".map(l => l.textContent.trim()).filter(Boolean)")


def r_errors(scope="body"):
    sel = "document.querySelector('.ant-modal')" if scope == "modal" else "document"
    return (f"const root = {sel}; "
            "return [...new Set(Array.from(root ? root.querySelectorAll('.ant-form-item-explain-error') : [])"
            ".map(e => e.textContent.trim()))]")


R_TOASTS = ("return Array.from(document.querySelectorAll('.ant-message-notice-content'))"
            ".map(e => e.textContent.trim())")

R_FOOTER_WIDTH = ("const foot = Array.from(document.querySelectorAll('.ant-modal-footer button'))"
                  ".map(b => ({ t: (b.textContent || '').replace(/\\s+/g, ''), d: b.disabled }));"
                  "const m = document.querySelector('.ant-modal');"
                  "return { foot, width: m && m.style ? m.style.width : null };")

R_MODAL_HIDDEN = ("const wrap = document.querySelector('.ant-modal-wrap');"
                  "const title = document.querySelector('.ant-modal-title');"
                  "const wrapHidden = !wrap || wrap.style.display === 'none' || wrap.offsetParent === null;"
                  "const titleHidden = !title || title.offsetParent === null;"
                  "return wrapHidden && titleHidden;")


def r_has_btn(text):
    return ("return Array.from(document.querySelectorAll('button,a'))"
            f".some(e => (e.textContent || '').replace(/\\s+/g, '') === '{text}')")


def r_input_value(expr):
    return f"const el = {expr}; return el ? el.value : null;"


# ── 主入口 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 注意：以库模块实例为准（ego_scenarios 里 rec/save_results 落在库实例的 RECORDS 上，
    # 直接用 __main__ 的同名对象会拿到空副本——python 双导入陷阱）
    import ego_ui_runner as lib
    from ego_scenarios import SCENARIOS

    wanted = sys.argv[1:] or list(SCENARIOS)
    unknown = [s for s in wanted if s not in SCENARIOS]
    if unknown:
        raise SystemExit(f"❌ 未知场景：{unknown}（可用：{list(SCENARIOS)}）")

    driver = lib.EgoDriver(verbose=os.environ.get("EGO_DEBUG")).boot()
    t0 = time.time()
    for name in wanted:
        t_scene = time.time()
        try:
            SCENARIOS[name](driver)
        except lib.EgoStuck as e:
            lib.rec(name, "场景执行", "FAIL", f"ego 通道挂死：{e}")
        except Exception as e:  # 单场景失败不拖垮整轮
            lib.rec(name, "场景执行", "FAIL", f"{type(e).__name__}: {str(e)[:150]}")
        finally:
            lib.SCENE_MS[name] = int((time.time() - t_scene) * 1000)
    lib.save_results()
    print(f"⏱️ 总耗时 {int(time.time() - t0)}s")
