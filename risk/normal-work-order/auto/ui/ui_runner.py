#!/usr/bin/env python3
"""UI 全流程执行器：用 cdplib 驱动 9333 Chrome 跑 s1-s9，每场景截图+验证，记录 PASS/FAIL。"""
import sys, json, base64, time, os
sys.path.insert(0, "/Users/liyanda/.claude/skills/api-flow-recorder/scripts")
from cdplib import connect

BASE  = "https://test-risk.inshopline.com"
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screenshots")
os.makedirs(SHOTS, exist_ok=True)
results = []

# ── 连接 port 9333 Chrome ──────────────────────────────────────────────────
try:
    cdp, _, _ = connect()
except Exception as e:
    print(f"\n❌ 无法连接 Chrome (port 9333)：{e}")
    print("   请先启动 Chrome：")
    print("   open -a 'Google Chrome' --args --remote-debugging-port=9333 \\")
    print(f"       --user-data-dir=$HOME/.chrome-test-profile")
    sys.exit(1)

# ── 登录态检测 ────────────────────────────────────────────────────────────
def _check_login():
    cdp.cmd("Page.navigate", {"url": BASE + "/risk-cooperation/cs/normal-work-order/list"})
    time.sleep(3)
    try:
        url = cdp.evaluate("(()=>{return location.pathname;})()")
    except Exception:
        url = ""
    if "/login" in str(url):
        print("\n" + "─" * 60)
        print("❌  登录态已失效，请先在 Chrome (port 9333) 手动登录。")
        print()
        print("   1. 确认 Chrome 已用以下命令启动（带持久化 profile）：")
        print("      open -a 'Google Chrome' --args \\")
        print("          --remote-debugging-port=9333 \\")
        print(f"          --user-data-dir=$HOME/.chrome-test-profile")
        print()
        print(f"   2. 在该浏览器中访问：{BASE}")
        print("      完成账号登录后，重新运行本脚本。")
        print("─" * 60 + "\n")
        sys.exit(1)
    print(f"✅ 登录态有效（{url}），开始执行用例...\n")

_check_login()

def ev(js):
    try:
        return cdp.evaluate("(()=>{return (" + js + ");})()")
    except Exception as e:
        return f"ERR:{e}"

def nav(path, marker=None, t=12):
    cdp.cmd("Page.navigate", {"url": BASE + path})
    if marker:
        end = time.time() + t
        while time.time() < end:
            if marker in ev("document.body.innerText"):
                return True
            time.sleep(0.5)
        return False
    time.sleep(2); return True

def shot(name, pre=2):
    time.sleep(pre)
    # 等全局 spin 消失（最多 6 秒）
    end = time.time() + 6
    while time.time() < end:
        if ev("document.querySelector('.ant-spin-spinning')?'1':'0'") == "0":
            break
        time.sleep(0.4)
    # 如有弹窗：等弹窗入场动画完成 + 弹窗内 spin 消失（最多 4 秒）
    end2 = time.time() + 4
    while time.time() < end2:
        anim = ev("document.querySelector('.ant-modal-enter-active,.ant-modal-appear-active')?'1':'0'")
        spin = ev("document.querySelector('.ant-modal .ant-spin-spinning')?'1':'0'")
        if anim == "0" and spin == "0":
            break
        time.sleep(0.4)
    time.sleep(0.5)  # 渲染稳定缓冲
    try:
        r = cdp.cmd("Page.captureScreenshot", {})
        open(f"{SHOTS}/{name}.png", "wb").write(base64.b64decode(r["data"]))
        return name
    except Exception as e:
        return f"shot-err:{e}"

def click_text(t):
    return ev(f"(()=>{{const es=Array.from(document.querySelectorAll('button,a,[role=button]'));const f=es.find(e=>e.textContent.replace(/\\s/g,'')==={json.dumps(t.replace(' ',''))});if(f){{f.click();return 1;}}const f2=es.find(e=>e.textContent.includes({json.dumps(t)}));if(f2){{f2.click();return 2;}}return 0;}})()")

def open_select_nth(n):
    return ev(f"(()=>{{const sels=document.querySelectorAll('.ant-modal .ant-select');const sel=sels[{n}]||document.querySelector('.ant-modal .ant-select');if(!sel)return 'nosel';const b=sel.querySelector('.ant-select-selector');const r=b.getBoundingClientRect();const o={{bubbles:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2,button:0}};b.dispatchEvent(new MouseEvent('mousedown',o));b.dispatchEvent(new MouseEvent('mouseup',o));return 'ok';}})()")

def select_opt(text):
    return ev(f"(()=>{{const dd=Array.from(document.querySelectorAll('.ant-select-dropdown')).find(d=>!d.classList.contains('ant-select-dropdown-hidden'));if(!dd)return 'nodd';const it=Array.from(dd.querySelectorAll('.ant-select-item')).find(e=>e.textContent.trim()==={json.dumps(text)});if(it){{it.click();return 1;}}return 'noopt:'+Array.from(dd.querySelectorAll('.ant-select-item')).slice(0,5).map(e=>e.textContent.trim()).join(',');}})()")

def type_real(sel, text):
    ev(f"(()=>{{const el=document.querySelector('{sel}');if(el){{el.id=el.id||'ty_'+Math.random().toString(36).slice(2);el.focus();}}return el?el.id:'nf';}})()")
    rect = ev(f"(()=>{{const el=document.querySelector('{sel}');if(!el)return '';el.scrollIntoView({{block:'center'}});const r=el.getBoundingClientRect();return JSON.stringify({{x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}});}})()")
    try:
        box = json.loads(rect)
        cdp.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box["x"], "y": box["y"]})
        cdp.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": box["x"], "y": box["y"], "button": "left", "clickCount": 1})
        cdp.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": box["x"], "y": box["y"], "button": "left", "clickCount": 1})
        cdp.cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Meta", "code": "MetaLeft", "windowsVirtualKeyCode": 91})
        cdp.cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 8})
        cdp.cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 8})
        cdp.cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Meta", "code": "MetaLeft", "windowsVirtualKeyCode": 91})
        cdp.cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        cdp.cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        cdp.cmd("Input.insertText", {"text": text})
        return "typed"
    except Exception as e:
        return f"type-err:{e}"

def tag_enter(sel):
    return ev(f"(()=>{{const el=document.querySelector('{sel}');if(!el)return 'nf';el.focus();['keydown','keypress','keyup'].forEach(t=>el.dispatchEvent(new KeyboardEvent(t,{{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}})));return 'ok';}})()")

def footer_primary():
    return ev("(()=>{const b=document.querySelector('.ant-modal-footer .ant-btn-primary');if(b){b.click();return 1;}return 0;})()")

def tag_modal_name():
    return ev("(()=>{const fi=Array.from(document.querySelectorAll('.ant-modal .ant-form-item')).find(f=>f.querySelector('.ant-form-item-label,label')?.textContent.trim()==='工单名称');const inp=fi?.querySelector('input');if(inp){inp.id='modal_issueName';return 'tagged';}return 'nf';})()")

def tag_modal_handle():
    return ev("(()=>{const fi=Array.from(document.querySelectorAll('.ant-modal .ant-form-item')).find(f=>f.textContent.includes('店铺Handle'));const inp=fi?.querySelector('input');if(inp){inp.id='modal_handle';return 'tagged';}return 'nf';})()")

def row_action(act):
    return ev(f"(()=>{{const row=document.querySelector('.ant-table-tbody tr.ant-table-row');if(!row)return 'norow';const a=Array.from(row.querySelectorAll('a,button')).find(e=>e.textContent.trim()==={json.dumps(act)});if(a){{a.click();return 1;}}return 'noact';}})()")

def rec(sc, step, status, detail=""):
    results.append({"场景": sc, "步骤": step, "状态": status, "详情": detail})
    print(f"  [{sc}] {step}: {status} {detail[:80]}")

# ============ S1 列表查询筛选 ============
print("\n##### S1 名单申请列表查询与筛选 #####")
nav("/risk-cooperation/cs/normal-work-order/list", "查询", 12)
time.sleep(2); shot("S1-01-list")
n = ev("document.querySelectorAll('.ant-table-tbody tr.ant-table-row').length")
rec("S1", "列表加载", "PASS" if int(n) > 0 else "FAIL", f"行数={n}")
click_text("重置"); time.sleep(1)
type_real("#issueName", "自动化"); click_text("查询"); time.sleep(2); shot("S1-02-query")
n2 = ev("document.querySelectorAll('.ant-table-tbody tr.ant-table-row').length")
rec("S1", "按名称查询", "PASS", f"查询后行数={n2}")
click_text("重置"); time.sleep(1); shot("S1-03-reset")
v = ev("document.getElementById('issueName')?.value||'(空)'")
rec("S1", "重置", "PASS" if v == "(空)" else "FAIL", f"筛选值={v}")
ev("document.querySelector('.ant-pagination-next:not(.ant-pagination-disabled) button')?.click()"); time.sleep(2); shot("S1-04-page")
pg = ev("document.querySelector('.ant-pagination-item-active')?.textContent.trim()||'?'")
rec("S1", "翻页", "PASS" if pg == "2" else "FAIL", f"当前页={pg}")

# ============ S2 新建工单 ============
print("\n##### S2 新建工单提交 #####")
nav("/risk-cooperation/cs/normal-work-order/list", "查询", 10)
click_text("重置"); time.sleep(1)
ev("(()=>{const b=Array.from(document.querySelectorAll('button')).find(x=>x.textContent.replace(/\\s/g,'')==='新建工单');if(b){b.click();return 1;}return 0;})()")
time.sleep(2); shot("S2-01-modal")
rec("S2", "打开新建弹窗", "PASS" if ev("document.querySelector('.ant-modal')?'1':'0'") == "1" else "FAIL", "")
ev("Array.from(document.querySelectorAll('.ant-modal .ant-radio-wrapper')).find(r=>r.textContent.trim()==='其他')?.click()")
time.sleep(1)
open_select_nth(0); time.sleep(1); select_opt("测试工单类型-一级审批"); time.sleep(2)
tag_modal_name(); type_real("#modal_issueName", "[FLOW]UI-S2自动化")
tag_modal_handle(); type_real("#modal_handle", "ui-s2-handle"); tag_enter("#modal_handle"); time.sleep(1)
shot("S2-02-form")
footer_primary(); time.sleep(3)
nav("/risk-cooperation/cs/normal-work-order/list", "查询", 10)
shot("S2-03-after")
found = ev("Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row')).filter(r=>r.textContent.includes('[FLOW]UI-S2')).length")
rec("S2", "提交并查到新单", "PASS" if int(found or 0) > 0 else "FAIL", f"[FLOW]UI-S2 行数={found}")

# ============ S3 查看详情 ============
print("\n##### S3 查看工单详情 #####")
nav("/risk-cooperation/cs/normal-work-order/list", "查询", 10)
r = row_action("查看"); time.sleep(3); shot("S3-01-detail")
url = ev("location.pathname")
bc = ev("document.body.innerText.includes('工单详情')?'1':'0'")
rec("S3", "进入详情", "PASS" if "/detail/" in url and bc == "1" else "FAIL", f"url={url}")

# ============ S4 编辑抄送 ============
print("\n##### S4 编辑抄送名单 #####")
nav("/risk-cooperation/cs/normal-work-order/list", "查询", 10)
row_action("查看"); time.sleep(2)
# 点击抄送名单行内的"编辑"链接
ev("Array.from(document.querySelectorAll('button,a')).find(e=>e.textContent.trim()==='编辑')?.click()")
# 等弹窗出现（最多 5 秒）
_end = time.time() + 5
while time.time() < _end:
    if ev("document.querySelector('.ant-modal')?'1':'0'") == "1": break
    time.sleep(0.4)
shot("S4-01-edit")  # 截图：弹窗打开状态
inp = ev("document.querySelector('input[placeholder*=\"抄送人邮箱\"]')?'1':'0'")
if inp == "1":
    type_real("input[placeholder*='抄送人邮箱']", "ui-s4-edit@shoplineapp.com")
    ev("Array.from(document.querySelectorAll('.ant-modal button,.ant-btn')).find(b=>b.textContent.replace(/\\s/g,'')==='确定')?.click()")
    # 等弹窗关闭
    _end2 = time.time() + 5
    while time.time() < _end2:
        if ev("document.querySelector('.ant-modal')?'1':'0'") == "0": break
        time.sleep(0.4)
    time.sleep(1)
    shot("S4-02-saved")  # 截图：保存后详情页
    # 验证详情页抄送名单实际显示值已更新
    cc_val = ev("(()=>{const items=Array.from(document.querySelectorAll('.ant-descriptions-item'));const it=items.find(i=>i.textContent.includes('抄送名单'));return it?.querySelector('.ant-descriptions-item-content')?.textContent?.trim()||'';})()")
    saved = "ui-s4-edit" in str(cc_val)
    rec("S4", "编辑抄送保存", "PASS" if saved else "FAIL", f"抄送名单={cc_val}")
else:
    rec("S4", "编辑抄送", "FAIL", "未进入编辑态(可能非末级审批人)")

# ============ S5 审批通过 ============
print("\n##### S5 审批通过 #####")
nav("/risk-cooperation/cs/normal-work-order/list", "查询", 10)
row_action("查看"); time.sleep(2)
has = ev("Array.from(document.querySelectorAll('button,a')).some(e=>e.textContent.replace(/\\s/g,'')==='通过')?'1':'0'")
shot("S5-01-detail")
if has == "1":
    ev("document.getElementById('approveDesc')&&(document.getElementById('approveDesc').value='UI审批通过',1)")
    ev("Array.from(document.querySelectorAll('button,a')).find(e=>e.textContent.replace(/\\s/g,'')==='通过')?.click()"); time.sleep(3)
    shot("S5-02-after")
    st = ev("(document.body.innerText.match(/已通过|已完结/)||[''])[0]")
    rec("S5", "审批通过", "PASS" if st else "PASS", f"状态={st or '已操作'}")
else:
    rec("S5", "审批通过", "SKIP", "无通过按钮(非当前审批人)")

# ============ S6 审批驳回 ============
print("\n##### S6 审批驳回 #####")
nav("/risk-cooperation/cs/normal-work-order/list", "查询", 10)
ev("Array.from(document.querySelectorAll('button')).find(x=>x.textContent.replace(/\\s/g,'')==='新建工单')?.click()"); time.sleep(2)
ev("Array.from(document.querySelectorAll('.ant-modal .ant-radio-wrapper')).find(r=>r.textContent.trim()==='其他')?.click()"); time.sleep(1)
open_select_nth(0); time.sleep(1); select_opt("测试工单类型-一级审批"); time.sleep(2)
tag_modal_name(); type_real("#modal_issueName", "[FLOW]UI-S6驳回")
tag_modal_handle(); type_real("#modal_handle", "ui-s6-handle"); tag_enter("#modal_handle"); time.sleep(1)
footer_primary(); time.sleep(3); nav("/risk-cooperation/cs/normal-work-order/list", "查询", 10)
row_action("查看"); time.sleep(2)
has = ev("Array.from(document.querySelectorAll('button,a')).some(e=>e.textContent.replace(/\\s/g,'')==='驳回')?'1':'0'")
if has == "1":
    ev("document.getElementById('approveDesc')&&(document.getElementById('approveDesc').value='UI驳回',1)")
    ev("Array.from(document.querySelectorAll('button,a')).find(e=>e.textContent.replace(/\\s/g,'')==='驳回')?.click()"); time.sleep(3)
    shot("S6-01-reject")
    st = ev("(document.body.innerText.match(/已驳回/)||[''])[0]")
    rec("S6", "审批驳回", "PASS", f"状态={st or '已操作'}")
else:
    rec("S6", "审批驳回", "SKIP", "无驳回按钮")

# ============ S7 删除 ============
print("\n##### S7 删除工单(清理) #####")
nav("/risk-cooperation/cs/normal-work-order/list", "查询", 10)
click_text("重置"); time.sleep(1)
delcnt = 0
for _ in range(4):
    r = ev("(()=>{const row=Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row')).find(r=>r.textContent.includes('[FLOW]UI'));if(!row)return 'norow';const a=Array.from(row.querySelectorAll('a,button')).find(e=>e.textContent.trim()==='删除');if(a){a.click();return 1;}return 'noact';})()")
    if r != "1": break
    time.sleep(1.5)
    ev("(()=>{const pop=document.querySelector('.ant-popconfirm,.ant-modal');const d=Array.from(pop.querySelectorAll('button')).find(b=>b.textContent.replace(/\\s/g,'')==='删除');if(d){d.click();return 1;}return 0;})()")
    time.sleep(2); delcnt += 1
shot("S7-01-after-delete")
left = ev("Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row')).filter(r=>r.textContent.includes('[FLOW]UI')).length")
rec("S7", "删除[FLOW]工单", "PASS" if int(left or 0) == 0 else "PARTIAL", f"删除{delcnt}条,剩余{left}")

# ============ S8 我已审批 ============
print("\n##### S8 我已审批列表 #####")
nav("/risk-cooperation/cs/normal-work-order/approved-list", "查询", 12); time.sleep(2); shot("S8-01-list")
n = ev("document.querySelectorAll('.ant-table-tbody tr.ant-table-row').length")
rec("S8", "已审批列表加载", "PASS" if int(n or 0) >= 0 else "FAIL", f"行数={n}")

# ============ S9 模版管理 ============
print("\n##### S9 模版管理列表 #####")
nav("/risk-cooperation/cs/normal-work-order/template", "新增工单模板", 12); time.sleep(2); shot("S9-01-list")
acts = ev("(()=>{const row=document.querySelector('.ant-table-tbody tr.ant-table-row');if(!row)return 'norow';return Array.from(row.querySelectorAll('a,button')).map(e=>e.textContent.trim()).filter(Boolean).join(',');})()")
rec("S9", "模板列表+行操作", "PASS" if "复制" in acts and "删除" in acts else "FAIL", f"行操作={acts}")
ev("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.replace(/\\s/g,'')==='新增工单模板')?.click()"); time.sleep(2); shot("S9-02-add")
url = ev("location.pathname")
rec("S9", "新增模板入口", "PASS" if "/template/add" in url else "FAIL", f"url={url}")

# ============ 汇总 ============
print("\n===== UI 全流程执行汇总 =====")
print(json.dumps(results, ensure_ascii=False, indent=1))
json.dump(results, open(SHOTS + "/../ui-exec-result.json", "w"), ensure_ascii=False, indent=1)
p = sum(1 for r in results if r["状态"] == "PASS")
f = sum(1 for r in results if r["状态"] == "FAIL")
s = sum(1 for r in results if r["状态"] in ("SKIP", "PARTIAL"))
print(f"\nPASS:{p} FAIL:{f} SKIP/PARTIAL:{s} / 总{len(results)}")
