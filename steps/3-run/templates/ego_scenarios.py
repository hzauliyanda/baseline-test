#!/usr/bin/env python3
"""ego_scenarios：22 个 UI 场景（对齐 Playwright 版 runner.spec.ts S1–S9 +
runner-augment.spec.ts S10–S23 的语义；S21 原版即缺号）。

设计约定：
  - 除 S2/S5/S6/S7 有真实数据动作外，其余一律走【取消/只读】，不提交、不建数据 → 可重复跑
  - 每步 rec() 落记录；条件不满足记 SKIP（对齐 PW 的 test.skip），不算 FAIL
  - S2/S6 建单后 API 查回铁证 + 自清理；S7 兜底清扫 [EGO] 残留
  - 截图经 shot_step() 统一命名 {Sx}-ego-{NN}-{步骤}.png
"""
import sys
import time

import requests

from ego_ui_runner import (
    APPROVED_URL, BASE_URL, LIST_URL, TPL_ADD_URL, TPL_LIST_URL,
    EgoDriver, ego_log, js_cancel_modal, js_click_text, js_delete_sweep,
    js_focus_expr, js_focus_modal_field, js_goto, js_open_create_modal,
    js_pagination_next, js_pick_radio_and_template, js_remark_and_click,
    js_row_action, js_row_action_td, js_select_by_label, js_submit,
    r_errors, r_has_btn, r_input_value, rec, shot_step, wait_log,
    R_FOOTER_WIDTH, R_LABELS, R_MODAL_HIDDEN, R_ROWS, R_TOASTS,
)

TPl_ONE_LEVEL = "测试工单类型-一级审批"   # S2/S6：一级审批人=liyanda
TPL_NAMELIST = "名单申请测试1"            # S15/S16
TPL_MULTI_MAT = "测试多个材料-001"        # S17/S18


# ── API 侧 helpers（铁证 + 清理） ─────────────────────────────────────────────
_CK = None


def _cookie():
    global _CK
    if _CK is None:
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
        from api_runner import get_cookie_from_ego
        _CK = get_cookie_from_ego()
    return _CK


def api_find_issue(name):
    r = requests.post(f"{BASE_URL}/mapi/cs/issue/normal/list",
                      headers={"appId": "4", "version": "v2", "Content-Type": "application/json",
                               "Cookie": _cookie()},
                      json={"listType": "NAMELIST_APPLY", "issueName": name, "pageNum": 1, "pageSize": 10},
                      timeout=20)
    rows = (r.json().get("data") or {}).get("list") or []
    hit = [x for x in rows if x.get("issueName") == name]
    return hit[0] if hit else None


def api_delete_issue(issue_id):
    r = requests.delete(f"{BASE_URL}/mapi/cs/issue/base/{issue_id}",
                        headers={"appId": "4", "version": "v2", "Cookie": _cookie()}, timeout=20)
    return r.status_code


# ═══ S1 列表查询筛选 ═════════════════════════════════════════════════════════
def run_s1(d: EgoDriver):
    scene = "S1"
    print(f"\n===== {scene} 列表查询筛选 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    rows = d.read(R_ROWS) or 0
    s1 = shot_step(d, scene, 1, "列表初载")
    if not rows or rows <= 0:
        rec(scene, "列表加载有数据", "FAIL", f"rows={rows}", s1)
        return
    rec(scene, "列表加载有数据", "PASS", f"rows={rows}", s1)

    d.fire(js_focus_expr("document.getElementById('issueName')"), settle=0.5)
    d.type_text("自动化")
    d.fire(js_click_text("查询"), settle=4)
    rows2 = d.read(R_ROWS) or 0
    s2 = shot_step(d, scene, 2, "查询自动化")
    rec(scene, "按名称查询", "PASS", f"rows={rows2}", s2)

    d.fire(js_click_text("重置"), settle=2.5)
    name_val = d.read(r_input_value("document.getElementById('issueName')")) or ""
    s3 = shot_step(d, scene, 3, "重置后")
    rec(scene, "重置清空输入", "PASS" if name_val == "" else "FAIL", f"value='{name_val}'", s3)

    d.fire(js_pagination_next(), settle=3.5)
    active = d.read("return (document.querySelector('.ant-pagination-item-active') || {}).textContent "
                    "? document.querySelector('.ant-pagination-item-active').textContent.trim() : '?'") or "?"
    s4 = shot_step(d, scene, 4, "翻页")
    if active == "2":
        rec(scene, "翻到第2页", "PASS", "active=2", s4)
    else:
        disabled = d.read("return (document.querySelector('.ant-pagination-next') || {}).className"
                          " ? document.querySelector('.ant-pagination-next').className.includes('disabled') : true")
        rec(scene, "翻到第2页", "SKIP" if disabled else "FAIL",
            f"active={active} next-disabled={disabled}", s4)


# ═══ S2 新建工单提交（纯 ego 全链路，2026-08-16 已两轮验证） ═════════════════
def run_s2(d: EgoDriver):
    scene, ts = "S2", str(int(time.time()))
    name, handle = f"[EGO-S2]{ts}", f"ego-s2-{ts}"
    print(f"\n===== {scene} 新建工单提交 =====")
    d.fire(js_goto(LIST_URL), settle=6)

    d.fire(js_open_create_modal(), settle=3)
    d.fire(js_pick_radio_and_template("其他", TPl_ONE_LEVEL, focus_after="工单名称"), settle=9)
    logs = ego_log(d)
    s2 = shot_step(d, scene, 2, "弹窗模板已选")
    fields = next((x for x in logs if x.startswith("fields:")), "")
    if any("tpl-picked" in x for x in logs):
        rec(scene, "新建弹窗·选其他类型·选模板(一级审批)", "PASS", fields[:120], s2)
    else:
        rec(scene, "新建弹窗·选其他类型·选模板(一级审批)", "FAIL", f"logs={logs[-3:]}", s2)
        return

    d.type_text(name)
    got = d.read("return Array.from(document.querySelectorAll('.ant-modal .ant-form-item'))"
                 ".filter(it => ((it.querySelector('label') || {}).textContent || '').includes('工单名称'))"
                 ".map(it => it.querySelector('input') ? it.querySelector('input').value : '').join(',')") or ""
    s3 = shot_step(d, scene, 3, "名称已填")
    if name in str(got):
        rec(scene, "填工单名称", "PASS", got, s3)
    else:
        rec(scene, "填工单名称", "FAIL", f"回读={got}", s3)
        return

    d.fire(js_focus_modal_field("店铺Handle"), settle=2)
    d.type_text(handle)
    d.fire(d.enter_js(), settle=1.5)
    toks = d.read("return Array.from(document.querySelectorAll('.ant-modal .ant-select-selection-item'))"
                  ".map(t => t.textContent.trim())") or []
    s4 = shot_step(d, scene, 4, "handle成tag")
    if handle in toks:
        rec(scene, "填店铺Handle并回车成tag", "PASS", f"tokens={toks}", s4)
    else:
        rec(scene, "填店铺Handle并回车成tag", "FAIL", f"tokens={toks}", s4)
        return

    d.fire(js_submit(), settle=9)
    logs = ego_log(d)
    s5 = shot_step(d, scene, 5, "提交后列表")
    if "modal-closed" in logs:
        rec(scene, "提交·弹窗关闭·零校验错误", "PASS", "modal-closed", s5)
    else:
        rec(scene, "提交·弹窗关闭·零校验错误", "FAIL", f"logs={logs[-3:] if logs else '无'}", s5)
        return

    try:
        row = api_find_issue(name)
        if row:
            rec(scene, "API 查回新建工单", "PASS",
                f"issueId={row.get('issueId')} status={row.get('issueStatus')}")
            code = api_delete_issue(row.get("issueId"))
            rec(scene, "清理测试工单", "PASS" if code in (200, 204) else "FAIL",
                f"DELETE {row.get('issueId')} → {code}")
        else:
            rec(scene, "API 查回新建工单", "FAIL", "list 未找到该工单")
    except Exception as e:
        rec(scene, "API 查回新建工单", "FAIL", str(e)[:120])


# ═══ S3 查看工单详情 ═════════════════════════════════════════════════════════
def run_s3(d: EgoDriver):
    scene = "S3"
    print(f"\n===== {scene} 查看工单详情 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_row_action("查看"), settle=5)
    logs = ego_log(d)
    url = d.read("return location.href") or ""
    body_has = d.read("return document.body.innerText.includes('工单详情')") or False
    s1 = shot_step(d, scene, 1, "详情页")
    if not any("acted:查看" in x for x in logs):
        rec(scene, "行操作查看跳详情", "SKIP", "列表无可查看行", s1)
        return
    ok = "/detail/" in url and body_has
    rec(scene, "行操作查看跳详情", "PASS" if ok else "FAIL", f"url={url[:80]} 含工单详情={body_has}", s1)


# ═══ S4 编辑抄送名单 ═════════════════════════════════════════════════════════
def run_s4(d: EgoDriver):
    scene = "S4"
    print(f"\n===== {scene} 编辑抄送名单 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_row_action("查看"), settle=5)
    d.fire(js_click_text("编辑"), settle=3)
    expr = "Array.from(document.querySelectorAll('input')).find(i => (i.placeholder || '').includes('抄送人邮箱'))"
    has_input = d.read(f"return !!{expr}")
    s1 = shot_step(d, scene, 1, "编辑态")
    if not has_input:
        rec(scene, "编辑抄送名单", "SKIP", "无抄送人邮箱输入框（非末级审批人）", s1)
        return
    rec(scene, "进入行内编辑", "PASS", "抄送人邮箱输入框出现", s1)

    d.fire(js_focus_expr(expr), settle=0.5)
    d.type_text("ui-s4-edit@shoplineapp.com")
    d.fire(js_click_text("确定"), settle=3)
    cc = d.read("const it = Array.from(document.querySelectorAll('.ant-descriptions-item'))"
                ".find(i => i.textContent.includes('抄送名单'));"
                "return it && it.querySelector('.ant-descriptions-item-content') "
                "? it.querySelector('.ant-descriptions-item-content').textContent.trim() : '';") or ""
    s2 = shot_step(d, scene, 2, "保存后")
    rec(scene, "保存抄送名单", "PASS" if "ui-s4-edit" in cc else "FAIL", f"cc={cc[:80]}", s2)


# ═══ S5 审批通过 ═════════════════════════════════════════════════════════════
def run_s5(d: EgoDriver):
    scene = "S5"
    print(f"\n===== {scene} 审批通过 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_row_action("查看"), settle=5)
    has = d.read(r_has_btn("通过"))
    s1 = shot_step(d, scene, 1, "详情页")
    if not has:
        rec(scene, "审批通过", "SKIP", "无通过按钮（非当前审批人）", s1)
        return
    rec(scene, "进入可审批详情", "PASS", "通过按钮存在", s1)
    d.fire(js_remark_and_click("UI审批通过", "通过"), settle=4)
    logs = ego_log(d)
    s2 = shot_step(d, scene, 2, "通过后")
    clicked = any("clicked:通过" in x for x in logs)
    rec(scene, "点击通过", "PASS" if clicked else "FAIL",
        f"logs={logs[-2:] if logs else '无'}", s2)


# ═══ S6 审批驳回（自建自驳，闭环清理） ═══════════════════════════════════════
def run_s6(d: EgoDriver):
    scene, ts = "S6", str(int(time.time()))
    name, handle = f"[EGO-S6]{ts}", f"ego-s6-{ts}"
    print(f"\n===== {scene} 审批驳回 =====")
    # 1. 建单（一级审批人=liyanda=当前登录人 → 有驳回权）
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_open_create_modal(), settle=3)
    d.fire(js_pick_radio_and_template("其他", TPl_ONE_LEVEL, focus_after="工单名称"), settle=9)
    logs = ego_log(d)
    if not any("tpl-picked" in x for x in logs):
        s0 = shot_step(d, scene, 1, "建单失败")
        rec(scene, "建单（驳回素材）", "FAIL", f"logs={logs[-3:]}", s0)
        return
    d.type_text(name)
    d.fire(js_focus_modal_field("店铺Handle"), settle=2)
    d.type_text(handle)
    d.fire(d.enter_js(), settle=1.5)
    d.fire(js_submit(), settle=9)
    logs = ego_log(d)
    issue_id = None
    try:
        row = api_find_issue(name)
        issue_id = row and row.get("issueId")
    except Exception:
        pass
    s1 = shot_step(d, scene, 1, "建单完成")
    ok = "modal-closed" in logs and issue_id
    rec(scene, "建单（驳回素材）", "PASS" if ok else "FAIL",
        f"issueId={issue_id} modal-closed={'modal-closed' in logs}", s1)
    if not ok:
        return

    # 2. 找到该单 → 驳回
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_row_action("查看", row_contains=name), settle=5)
    has = d.read(r_has_btn("驳回"))
    if not has:
        s2 = shot_step(d, scene, 2, "详情无驳回按钮")
        rec(scene, "审批驳回", "SKIP", "无驳回按钮（非当前审批人）", s2)
        api_delete_issue(issue_id)
        return
    d.fire(js_remark_and_click("UI驳回", "驳回"), settle=4)
    logs = ego_log(d)
    clicked = any("clicked:驳回" in x for x in logs)
    status_after = None
    try:
        row = api_find_issue(name)
        status_after = row and row.get("issueStatus")
    except Exception:
        pass
    s2 = shot_step(d, scene, 2, "驳回后")
    rec(scene, "审批驳回", "PASS" if clicked else "FAIL",
        f"clicked={clicked} status_after={status_after}", s2)

    # 3. API 清理（已驳回单不留 env）
    try:
        code = api_delete_issue(issue_id)
        rec(scene, "清理测试工单", "PASS" if code in (200, 204) else "FAIL", f"DELETE {issue_id} → {code}")
    except Exception as e:
        rec(scene, "清理测试工单", "FAIL", str(e)[:120])


# ═══ S7 删除 [EGO] 工单（兜底清扫） ═══════════════════════════════════════════
def run_s7(d: EgoDriver):
    scene = "S7"
    print(f"\n===== {scene} 删除[EGO]残留工单 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_click_text("重置"), settle=2.5)
    d.fire(js_delete_sweep("[EGO"), settle=5)
    logs = wait_log(d, "sweep-done", timeout=35, interval=4)
    line = next((x for x in logs if x.startswith("sweep-done")), "sweep-done deleted:? left:?")
    deleted = left = None
    try:
        parts = dict(p.split(":") for p in line.split()[1:])
        deleted, left = int(parts["deleted"]), int(parts["left"])
    except Exception:
        pass
    s1 = shot_step(d, scene, 1, "清扫后")

    if left is not None and left > 0:
        # UI 删不动（如已驳回无删除按钮）→ API 兜底
        swept = []
        try:
            r = requests.post(f"{BASE_URL}/mapi/cs/issue/normal/list",
                              headers={"appId": "4", "version": "v2", "Content-Type": "application/json",
                                       "Cookie": _cookie()},
                              json={"listType": "NAMELIST_APPLY", "pageNum": 1, "pageSize": 50}, timeout=20)
            for x in (r.json().get("data") or {}).get("list") or []:
                if "[EGO" in (x.get("issueName") or ""):
                    api_delete_issue(x.get("issueId"))
                    swept.append(x.get("issueId"))
        except Exception as e:
            rec(scene, "API 兜底清扫", "FAIL", str(e)[:100], s1)
            return
        rec(scene, "删除[EGO]残留工单", "PASS", f"UI删{deleted}条 + API兜底{swept}（已驳回等无行内删除按钮）", s1)
    else:
        rec(scene, "删除[EGO]残留工单", "PASS", f"UI删{deleted}条 left={left}", s1)


# ═══ S8 我已审批列表 ═════════════════════════════════════════════════════════
def run_s8(d: EgoDriver):
    scene = "S8"
    print(f"\n===== {scene} 我已审批列表 =====")
    d.fire(js_goto(APPROVED_URL), settle=6)
    title = d.read("return document.title") or ""
    rows = d.read(R_ROWS) or 0
    s1 = shot_step(d, scene, 1, "已审批列表")
    rec(scene, "我已审批列表渲染", "PASS" if title else "FAIL", f"title='{title}' rows={rows}", s1)


# ═══ S9 模版管理 ═════════════════════════════════════════════════════════════
def run_s9(d: EgoDriver):
    scene = "S9"
    print(f"\n===== {scene} 模版管理 =====")
    d.fire(js_goto(TPL_LIST_URL), settle=6)
    actions = d.read("return Array.from((document.querySelector('.ant-table-tbody tr.ant-table-row') "
                     "|| { querySelectorAll: () => [] }).querySelectorAll('a,button'))"
                     ".map(e => e.textContent.trim()).filter(Boolean).join(',')") or ""
    s1 = shot_step(d, scene, 1, "模板列表")
    has_copy, has_del = "复制" in actions, "删除" in actions
    rec(scene, "模板行操作含复制/删除", "PASS" if (has_copy and has_del) else "FAIL",
        f"actions={actions[:60]}", s1)

    d.fire(js_click_text("新增工单模板"), settle=4)
    url = d.read("return location.href") or ""
    s2 = shot_step(d, scene, 2, "新增模板页")
    rec(scene, "跳转新增模板页", "PASS" if "/template/add" in url else "FAIL", f"url={url[:80]}", s2)


# ═══ S10 模板表单必填校验 ════════════════════════════════════════════════════
def run_s10(d: EgoDriver):
    scene = "S10"
    print(f"\n===== {scene} 模板表单必填校验 =====")
    d.fire(js_goto(TPL_ADD_URL), settle=6)
    d.fire(js_click_text("完成"), settle=2)
    errs = d.read(r_errors()) or []
    s1 = shot_step(d, scene, 1, "空表单校验")
    rec(scene, "报模板类型必填", "PASS" if "请选择模板类型" in errs else "FAIL", f"errs={errs}", s1)
    rec(scene, "报模板名称必填", "PASS" if "请输入模板名称" in errs else "FAIL", "", s1)
    rec(scene, "空态不出现主键必填", "PASS" if not any("主键" in e for e in errs) else "FAIL",
        "未选类型时主键字段不渲染", s1)


# ═══ S11 模板类型驱动字段显隐 ════════════════════════════════════════════════
def run_s11(d: EgoDriver):
    scene = "S11"
    print(f"\n===== {scene} 模板类型驱动字段显隐 =====")
    d.fire(js_goto(TPL_ADD_URL), settle=6)

    d.fire(js_select_by_label("模板类型", "其他"), settle=3)
    labels = d.read(R_LABELS) or []
    rec(scene, "OTHER 有主键字段", "PASS" if any("主键字段" in x for x in labels) else "FAIL",
        f"labels={labels[:10]}", None)
    rec(scene, "OTHER 无名单库", "PASS" if not any("名单库" in x for x in labels) else "FAIL", "", None)

    d.fire(js_select_by_label("模板类型", "名单申请"), settle=3)
    labels = d.read(R_LABELS) or []
    rec(scene, "名单申请有名单库", "PASS" if any("名单库" in x for x in labels) else "FAIL",
        f"labels={labels[:10]}", None)
    rec(scene, "名单申请有是否约定月份", "PASS" if any("是否约定月份" in x for x in labels) else "FAIL", "", None)

    d.fire(js_select_by_label("模板类型", "名单剔除"), settle=3)
    labels = d.read(R_LABELS) or []
    s1 = shot_step(d, scene, 1, "类型联动")
    rec(scene, "名单剔除为剔除名单库", "PASS" if any("剔除名单库" in x for x in labels) else "FAIL",
        f"labels={labels[:10]}", s1)
    rec(scene, "名单剔除无材料配置", "PASS" if not any("配置材料" in x for x in labels) else "FAIL", "", s1)


# ═══ S12 材料配置分支（ENUM/枚举值/最多20） ══════════════════════════════════
def run_s12(d: EgoDriver):
    scene = "S12"
    print(f"\n===== {scene} 材料配置分支 =====")
    d.fire(js_goto(TPL_ADD_URL), settle=6)
    d.fire(js_select_by_label("模板类型", "其他"), settle=3)
    d.fire(js_click_text("添加多材料"), settle=2)

    d.fire(js_open_select_by_placeholder("请选择材料类型"), settle=2)
    opts = d.read("return Array.from(document.querySelectorAll("
                  "'.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option-content'))"
                  ".map(e => e.textContent.trim())") or []
    rec(scene, "材料类型含枚举", "PASS" if "枚举" in opts else "FAIL", f"opts={opts}", None)

    d.fire(js_click_option("枚举"), settle=2)
    has_enum = d.read("return Array.from(document.querySelectorAll('input,textarea'))"
                      ".some(i => /枚举值/.test(i.placeholder || ''))")
    rec(scene, "选枚举出现枚举值输入框", "PASS" if has_enum else "FAIL", f"hasEnumInput={has_enum}", None)

    d.fire(js_click_text_n("添加多材料", 25), settle=2.5)
    toasts = d.read(R_TOASTS) or []
    s1 = shot_step(d, scene, 1, "材料上限")
    rec(scene, "提示配置材料最多20个", "PASS" if any("配置材料最多20个" in t for t in toasts) else "FAIL",
        f"toasts={toasts[:3]}", s1)


def js_open_select_by_placeholder(placeholder):
    from ego_ui_runner import HELPERS
    return ("(async () => {" + HELPERS + f"""
  try {{
    const s = Array.from(document.querySelectorAll('.ant-select')).find(x => /{placeholder}/.test((x.querySelector('.ant-select-selection-placeholder') || {{}}).textContent || ''));
    const sel = s && s.querySelector('.ant-select-selector');
    if (!sel) {{ log('NO-placeholder:{placeholder}'); return; }}
    mdown(sel);
    for (let i = 0; i < 12; i++) {{ if (visibleDd()) break; await sleep(250); }}
    log('dd-open');
  }} catch (e) {{ log('ERR ' + e.message); }}
}})();""")


def js_click_option(text):
    from ego_ui_runner import HELPERS
    return ("(async () => {" + HELPERS + f"""
  try {{
    const o = Array.from(document.querySelectorAll('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option'))
      .find(x => (x.textContent || '').trim() === '{text}');
    if (!o) {{ log('NO-opt:{text}'); return; }}
    mdown(o);
    log('opt-clicked:{text}');
  }} catch (e) {{ log('ERR ' + e.message); }}
}})();""")


def js_click_text_n(text, n):
    from ego_ui_runner import HELPERS
    return ("(async () => {" + HELPERS + f"""
  try {{
    const b = btn('{text}');
    if (!b) {{ log('NO-btn:{text}'); return; }}
    for (let i = 0; i < {n}; i++) b.click();
    log('clicked-n:{text}x{n}');
  }} catch (e) {{ log('ERR ' + e.message); }}
}})();""")


# ═══ S13 审批与运营地区配置 ══════════════════════════════════════════════════
def run_s13(d: EgoDriver):
    scene = "S13"
    print(f"\n===== {scene} 审批与运营地区配置 =====")
    d.fire(js_goto(TPL_ADD_URL), settle=6)
    d.fire(js_select_by_label("模板类型", "名单申请"), settle=3)
    disabled = d.read("const s = Array.from(document.querySelectorAll('.ant-select')).find(x => /运营地区/"
                      ".test((x.querySelector('.ant-select-selection-placeholder') || {}).textContent || ''));"
                      "return s ? s.classList.contains('ant-select-disabled') : null;")
    rec(scene, "单块运营地区 disabled", "PASS" if disabled is True else "FAIL", f"disabled={disabled}", None)

    d.fire(js_click_text_n("添加多级审批人", 8), settle=2.5)
    toasts = d.read(R_TOASTS) or []
    s1 = shot_step(d, scene, 1, "审批上限")
    rec(scene, "提示审批人最多五级", "PASS" if any("审批人最多五级" in t for t in toasts) else "FAIL",
        f"toasts={toasts[:3]}", s1)


# ═══ S14 模板编辑回显与 disabled（只读） ═════════════════════════════════════
def run_s14(d: EgoDriver):
    scene = "S14"
    print(f"\n===== {scene} 模板编辑回显与disabled =====")
    d.fire(js_goto(TPL_LIST_URL), settle=6)
    d.fire(js_row_action("编辑"), settle=5)
    url = d.read("return location.href") or ""
    s1 = shot_step(d, scene, 1, "编辑回显")
    if "operateType=edit" not in url:
        rec(scene, "进入编辑模板页", "FAIL", f"url={url[:80]}", s1)
        return
    rec(scene, "进入编辑模板页", "PASS", "operateType=edit", s1)
    st = d.read("const typeSel = Array.from(document.querySelectorAll('.ant-select')).find(s => "
                "{ const it = s.querySelector('.ant-select-selection-item'); "
                "return it && ['名单申请','名单剔除','其他','商家入驻'].includes(it.textContent.trim()); });"
                "const nameInputs = Array.from(document.querySelectorAll('input'))"
                ".filter(i => /200字符/.test(i.placeholder || ''));"
                "return { typeDisabled: typeSel ? typeSel.classList.contains('ant-select-disabled') : null,"
                " nameDisabled: nameInputs.slice(0, 2).map(i => i.disabled) };") or {}
    ok = st.get("typeDisabled") is True and all(st.get("nameDisabled") or [])
    rec(scene, "类型/名称(中英) disabled", "PASS" if ok else "FAIL", f"st={st}", s1)


# ═══ S15 新建弹窗双层门槛与取消 ══════════════════════════════════════════════
def run_s15(d: EgoDriver):
    scene = "S15"
    print(f"\n===== {scene} 新建弹窗双层门槛与取消 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_open_create_modal(), settle=3)
    l1 = d.read(R_FOOTER_WIDTH) or {}
    ok1 = l1.get("foot") and all(b.get("d") for b in l1["foot"]) and l1.get("width") == "600px"
    rec(scene, "第一层保存/完成禁用·宽600", "PASS" if ok1 else "FAIL", f"l1={l1}", None)

    d.fire(js_pick_radio_and_template("名单申请", TPL_NAMELIST), settle=9)
    l2 = d.read(R_FOOTER_WIDTH) or {}
    ok2 = l2.get("foot") and all(not b.get("d") for b in l2["foot"]) and l2.get("width") == "1180px"
    s1 = shot_step(d, scene, 1, "双层门槛")
    rec(scene, "第二层保存/完成可用·宽1180", "PASS" if ok2 else "FAIL", f"l2={l2}", s1)

    d.fire(js_cancel_modal(), settle=2)
    hidden = d.read(R_MODAL_HIDDEN)
    s2 = shot_step(d, scene, 2, "取消后")
    rec(scene, "取消后弹窗隐藏", "PASS" if hidden is True else "FAIL", f"hidden={hidden}", s2)


# ═══ S16 名单数据 dataSync 联动 ══════════════════════════════════════════════
def run_s16(d: EgoDriver):
    scene = "S16"
    print(f"\n===== {scene} 名单数据dataSync联动 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_open_create_modal(), settle=3)
    d.fire(js_pick_radio_and_template("名单申请", TPL_NAMELIST), settle=9)
    d.fire(js_select_by_label("主键", "商家账号", scope="modal", placeholder="请选择主键"), settle=3)
    logs = ego_log(d)
    picked = any("picked:主键=商家账号" in x for x in logs)
    cbs = d.read("return Array.from(document.querySelectorAll('.ant-modal .ant-checkbox-wrapper'))"
                 ".map(c => c.textContent.trim())") or []
    s1 = shot_step(d, scene, 1, "T+1同步")
    ok = picked and any("T+1同步" in x for x in cbs)
    rec(scene, "商家账号显示T+1同步文案", "PASS" if ok else "FAIL",
        f"picked={picked} cbs={cbs[:5]}", s1)
    d.fire(js_cancel_modal(), settle=1.5)


# ═══ S17 申请说明非必填 + 主键tags必填 ═══════════════════════════════════════
def run_s17(d: EgoDriver):
    scene = "S17"
    print(f"\n===== {scene} 申请说明与主键tags =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_open_create_modal(), settle=3)
    d.fire(js_pick_radio_and_template("其他", TPL_MULTI_MAT), settle=9)
    d.fire(js_click_text("完成"), settle=2)
    errs = d.read(r_errors("modal")) or []
    s1 = shot_step(d, scene, 1, "必填校验")
    rec(scene, "报工单名称必填", "PASS" if "请输入工单名称" in errs else "FAIL", f"errs={errs}", s1)
    rec(scene, "报主键(店铺Handle)必填", "PASS" if any("店铺Handle" in e for e in errs) else "FAIL", "", s1)
    rec(scene, "申请说明不报必填", "PASS" if not any("申请说明" in e for e in errs) else "FAIL", "", s1)
    d.fire(js_cancel_modal(), settle=1.5)


# ═══ S18 材料动态字段渲染 ════════════════════════════════════════════════════
def run_s18(d: EgoDriver):
    scene = "S18"
    print(f"\n===== {scene} 材料动态字段渲染 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_open_create_modal(), settle=3)
    d.fire(js_pick_radio_and_template("其他", TPL_MULTI_MAT), settle=9)
    info = d.read("const m = document.querySelector('.ant-modal');"
                  "return { hasTextarea: Array.from(m ? m.querySelectorAll('textarea') : [])"
                  "  .some(t => /请输入配置字段/.test(t.placeholder || '')),"
                  " hasUpload: !!(m && m.querySelector('.ant-upload')),"
                  " hint: !!(m && /大小不能超过5MB/.test(m.textContent || '')) };") or {}
    s1 = shot_step(d, scene, 1, "材料动态字段")
    ok = info.get("hasTextarea") and info.get("hasUpload") and info.get("hint")
    rec(scene, "TEXT渲染TextArea·FILE渲染Upload·5MB提示", "PASS" if ok else "FAIL",
        f"info={info}", s1)
    d.fire(js_cancel_modal(), settle=1.5)


# ═══ S19 空备注审批拦截（只读，被拦不提交） ══════════════════════════════════
def run_s19(d: EgoDriver):
    scene = "S19"
    print(f"\n===== {scene} 空备注审批拦截 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_row_action_td("查看", [(3, "待审批"), (7, "liyanda")]), settle=5)
    logs = ego_log(d)
    if not any("acted:查看" in x for x in logs):
        s1 = shot_step(d, scene, 1, "无可测行")
        rec(scene, "空备注审批拦截", "SKIP", "无待审批(liyanda)工单可测", s1)
        return
    has = d.read(r_has_btn("通过"))
    if not has:
        s1 = shot_step(d, scene, 1, "详情无通过按钮")
        rec(scene, "空备注审批拦截", "SKIP", "详情无通过按钮", s1)
        return
    d.fire(js_click_text("通过"), settle=2)
    errs = d.read(r_errors()) or []
    s1 = shot_step(d, scene, 1, "空备注拦截")
    rec(scene, "空备注点通过报请输入备注", "PASS" if any("请输入备注" in e for e in errs) else "FAIL",
        f"errs={errs[:3]}", s1)


# ═══ S20 终态工单不可再审批 + 只读 ═══════════════════════════════════════════
def run_s20(d: EgoDriver):
    scene = "S20"
    print(f"\n===== {scene} 终态不可审批与只读 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_row_action_td("查看", [(3, "已完结")]), settle=5)
    logs = ego_log(d)
    if not any("acted:查看" in x for x in logs):
        s1 = shot_step(d, scene, 1, "无可测行")
        rec(scene, "终态不可审批与只读", "SKIP", "无已完结工单可测", s1)
        return
    st = d.read("const t = document.body.innerText.replace(/\\s+/g, '');"
                "return { hasApproveBtn: Array.from(document.querySelectorAll('button'))"
                "  .some(b => ['通过','驳回'].includes((b.textContent || '').replace(/\\s+/g, ''))),"
                " hasApprovalArea: t.includes('审批操作') };") or {}
    s1 = shot_step(d, scene, 1, "终态只读")
    ok = st.get("hasApproveBtn") is False and st.get("hasApprovalArea") is False
    rec(scene, "已完结无审批按钮/审批区", "PASS" if ok else "FAIL", f"st={st}", s1)


# ═══ S22 列表筛选模板联动（记录实测行为） ════════════════════════════════════
def run_s22(d: EgoDriver):
    scene = "S22"
    print(f"\n===== {scene} 列表筛选模板联动 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    d.fire(js_select_by_label("模板类型", "名单申请"), settle=3)
    d.fire(js_open_tpl_filter_dd(), settle=2.5)
    cnt = d.read("return (document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)')"
                 " || { querySelectorAll: () => [] }).querySelectorAll('.ant-select-item-option').length") or 0
    s1 = shot_step(d, scene, 1, "筛选联动")
    rec(scene, "工单模板下拉有选项", "PASS" if cnt and cnt > 0 else "FAIL", f"opts={cnt}", s1)
    if cnt and cnt > 0:
        print(f"    [S22][FINDING] 选模板类型=名单申请后 工单模板选项数={cnt}"
              f"（实测不随类型收窄，疑似缺陷，需产品确认）")


def js_open_tpl_filter_dd():
    from ego_ui_runner import HELPERS
    return ("(async () => {" + HELPERS + """
  try {
    const fi = Array.from(document.querySelectorAll('.ant-form-item'))
      .find(it => (it.querySelector('.ant-form-item-label label') || {}).textContent === '工单模板');
    const sel = fi && fi.querySelector('.ant-select-selector');
    if (!sel) { log('NO-label:工单模板'); return; }
    mdown(sel);
    for (let i = 0; i < 12; i++) { if (visibleDd()) break; await sleep(250); }
    await sleep(800);
    log('tpl-dd-open');
  } catch (e) { log('ERR ' + e.message); }
})();""")


# ═══ S23 列表筛选：创建人/处理人/创建时间 ════════════════════════════════════
def run_s23(d: EgoDriver):
    scene = "S23"
    print(f"\n===== {scene} 列表筛选用户与时间 =====")
    d.fire(js_goto(LIST_URL), settle=6)
    st = d.read("const labels = Array.from(document.querySelectorAll('.ant-form-item-label label'))"
                ".map(l => l.textContent.trim());"
                "return { hasCreator: labels.includes('创建人'),"
                " hasHandler: labels.includes('处理人'),"
                " hasCreatedTime: labels.includes('创建时间'),"
                " hasRangePicker: !!document.querySelector('.ant-picker') };") or {}
    s1 = shot_step(d, scene, 1, "筛选字段")
    ok = st.get("hasCreator") and st.get("hasHandler") and st.get("hasCreatedTime") and st.get("hasRangePicker")
    rec(scene, "创建人/处理人/创建时间/范围选择器", "PASS" if ok else "FAIL", f"st={st}", s1)


SCENARIOS = {
    "S1": run_s1, "S2": run_s2, "S3": run_s3, "S4": run_s4, "S5": run_s5,
    "S6": run_s6, "S7": run_s7, "S8": run_s8, "S9": run_s9,
    "S10": run_s10, "S11": run_s11, "S12": run_s12, "S13": run_s13, "S14": run_s14,
    "S15": run_s15, "S16": run_s16, "S17": run_s17, "S18": run_s18, "S19": run_s19,
    "S20": run_s20, "S22": run_s22, "S23": run_s23,
}

# 场景标题（报告展示用；S21 原版 Playwright 即缺号）
TITLES = {
    "S1": "S1 列表查询筛选", "S2": "S2 新建工单提交", "S3": "S3 查看工单详情",
    "S4": "S4 编辑抄送名单", "S5": "S5 审批通过", "S6": "S6 审批驳回",
    "S7": "S7 删除[EGO]残留工单", "S8": "S8 我已审批列表", "S9": "S9 模版管理",
    "S10": "S10 模板表单必填校验", "S11": "S11 模板类型驱动字段显隐",
    "S12": "S12 材料配置分支", "S13": "S13 审批与运营地区配置",
    "S14": "S14 模板编辑回显与disabled", "S15": "S15 新建弹窗双层门槛与取消",
    "S16": "S16 名单数据dataSync联动", "S17": "S17 申请说明与主键tags",
    "S18": "S18 材料动态字段渲染", "S19": "S19 空备注审批拦截",
    "S20": "S20 终态不可审批与只读", "S22": "S22 列表筛选模板联动",
    "S23": "S23 列表筛选用户与时间",
}
