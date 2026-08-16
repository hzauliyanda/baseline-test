#!/usr/bin/env python3
"""
check_coverage.py —— ②tc-cases 的机算放行门（工具无关，纯 python3+pyyaml）

用法:
    python3 steps/2-cases/check_coverage.py <模块根目录>
    python3 steps/2-cases/check_coverage.py <模块根目录> --check-case-ids   # 连用例真实存在一起核

检查项（任一 FAIL → 退出码 1，②不放行）:
  1. 前置: baseline.yaml 存在、repos.backend/frontend.url 非空、audit_base 不含"待回填"
  2. schema: endpoints/pages 的 status ∈ {covered, skip_note, manual, uncovered};
     skip_note/manual 必须有 note; covered 必须有非空 cases
  3. 缺口: 任何 status=uncovered → FAIL
  4. 枚举: 每个枚举 values - covered - exempt 必须为空（重算 gaps，矩阵里漏标的也会被抓出）;
     covered/exempt 里出现 values 之外的值 → WARN(过期) 不 FAIL
  5. 状态机: reachable - covered - exempt 必须为空
  6. (--check-case-ids) 用例 id 真实存在: flow:step 在 artifacts.api_cases 的 yaml 里有对应
     step id; UI S 编号在 artifacts.ui_scenarios 或 traceability.json 里出现。模块文件不在
     本机时自动降级 WARN（金标准实例在 kit 里就是这种情况）。

退出码: 0=放行  1=有缺口  2=文件缺失/schema 打不开
"""
import sys, os, re, glob, json
import yaml

VALID_STATUS = {"covered", "skip_note", "manual", "uncovered"}

def ok(msg):   print(f"  🟢 {msg}")
def warn(msg): print(f"  🟡 WARN {msg}")
def fail(msg): print(f"  🔴 {msg}")

def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    root = sys.argv[1]
    check_ids = "--check-case-ids" in sys.argv
    bl_path = os.path.join(root, "baseline.yaml")
    api_cov = os.path.join(root, "coverage", "api-coverage.yaml")
    ui_cov  = os.path.join(root, "coverage", "ui-coverage.yaml")

    if not os.path.isfile(bl_path):
        fail(f"缺 baseline.yaml: {bl_path} → 先跑 ①tc-explore"); return 2
    if not os.path.isfile(api_cov) or not os.path.isfile(ui_cov):
        fail("缺 coverage/api-coverage.yaml 或 ui-coverage.yaml"); return 2

    bl = load_yaml(bl_path)
    n_fail = n_warn = 0

    # ── 1. 前置 ─────────────────────────────────────────────
    print("== 1 前置 baseline.yaml ==")
    repos = bl.get("repos") or {}
    for side in ("backend", "frontend"):
        r = repos.get(side) or {}
        url = (r.get("url") or "").strip()
        ab  = (r.get("audit_base") or "").strip()
        if not url:
            fail(f"repos.{side}.url 为空"); n_fail += 1
        elif "待回填" in ab or not ab:
            fail(f"repos.{side}.audit_base 未填（'{ab}'）——覆盖对账无锚点"); n_fail += 1
        else:
            ok(f"repos.{side}: {url} @ {ab}")

    # ── 2+3. endpoints / pages schema + 缺口 ────────────────
    def check_items(items, label):
        nonlocal n_fail, n_warn
        cnt = {s: 0 for s in VALID_STATUS}
        for it in items or []:
            st = it.get("status")
            if st not in VALID_STATUS:
                fail(f"{label}: 非法 status '{st}'（{it.get('endpoint') or it.get('interaction')}）"); n_fail += 1; continue
            cnt[st] += 1
            cases = it.get("cases") or []
            note = (it.get("note") or "").strip()
            if st == "covered" and not cases:
                fail(f"{label}: status=covered 但 cases 为空（{it.get('endpoint') or it.get('interaction')}）"); n_fail += 1
            if st in ("skip_note", "manual") and not note:
                fail(f"{label}: status={st} 缺 note（{it.get('endpoint') or it.get('interaction')}）"); n_fail += 1
            if st == "uncovered":
                fail(f"{label} 缺口: {it.get('endpoint') or it.get('interaction')} → 补用例或改 skip_note/manual/exempt 并写理由"); n_fail += 1
        return cnt

    print("== 2/3 api endpoints ==")
    acov = load_yaml(api_cov)
    cnt_api = check_items(acov.get("endpoints"), "api")
    print(f"  统计: {cnt_api}")

    print("== 2/3 ui pages×interactions ==")
    ucov = load_yaml(ui_cov)
    n_inter = 0; cnt_ui = {s: 0 for s in VALID_STATUS}
    for pg in ucov.get("pages") or []:
        c = check_items(pg.get("interactions") or [], f"ui[{pg.get('page')}]")
        n_inter += sum(c.values())
        for k in c: cnt_ui[k] += c[k]
    print(f"  统计: {cnt_ui}（页面 {len(ucov.get('pages') or [])} 个）")

    # ── 4. 枚举 ─────────────────────────────────────────────
    def check_enums(enums, label):
        nonlocal n_fail, n_warn
        for name, e in (enums or {}).items():
            values   = set(e.get("values") or [])
            covered_map = e.get("covered") or {}
            covered  = set()   # 只认用例列表非空的键；空列表 = 假覆盖
            for v, cs in covered_map.items():
                if cs and str(cs[0]).strip():
                    covered.add(v)
                else:
                    fail(f"{label} 枚举[{name}] covered['{v}'] 用例列表为空 = 假覆盖 → 补用例或挪进 gaps/exempt"); n_fail += 1
            exempt   = set((e.get("exempt") or {}).keys())
            declared = set(e.get("gaps") or [])
            real_gaps = values - covered - exempt
            if real_gaps:
                fail(f"{label} 枚举[{name}] 缺值: {sorted(real_gaps)} → 每值至少 1 条正向用例，或 exempt 带理由"); n_fail += 1
            elif declared != real_gaps:
                warn(f"{label} 枚举[{name}] 矩阵 gaps 声明与实算不一致（声明 {sorted(declared)} / 实算 {sorted(real_gaps)}），已按实算放行"); n_warn += 1
            else:
                ok(f"枚举[{name}] {len(covered & values)}/{len(values)} 值已覆盖")
            stale = (covered | exempt) - values
            if stale:
                warn(f"{label} 枚举[{name}] covered/exempt 里过期值 {sorted(stale)}（values 里没有，代码可能已删）"); n_warn += 1

    print("== 4 枚举维度 ==")
    check_enums(acov.get("enums"), "api")
    check_enums(ucov.get("enums"), "ui")

    # ── 5. 状态机 ───────────────────────────────────────────
    print("== 5 状态机 ==")
    st = ucov.get("states") or {}
    if st:
        reachable = set(st.get("reachable") or [])
        covered   = set((st.get("covered") or {}).keys())
        exempt    = set((st.get("exempt") or {}).keys())
        gaps = reachable - covered - exempt
        if gaps:
            fail(f"状态机[{st.get('machine')}] 缺状态: {sorted(gaps)} → 每个可达状态至少 1 条场景到达或 exempt"); n_fail += 1
        else:
            ok(f"状态机[{st.get('machine')}] {len(covered & reachable)}/{len(reachable)} 状态已到达")
    else:
        warn("ui-coverage 无 states 节（无状态机的模块可忽略）"); n_warn += 1

    # ── 6. 用例 id 真实存在（可选） ─────────────────────────
    if check_ids:
        print("== 6 用例 id 存在性 ==")
        arts = bl.get("artifacts") or {}
        api_dir = os.path.join(root, arts.get("api_cases") or "auto/api")
        ui_dir  = os.path.join(root, arts.get("ui_scenarios") or "auto/ui")
        flow_text = ""
        for p in glob.glob(os.path.join(api_dir, "*.yaml")):
            flow_text += open(p, encoding="utf-8").read()
        ui_text = ""
        for pat in (os.path.join(ui_dir, "*.py"), os.path.join(ui_dir, "traceability.json")):
            for p in glob.glob(pat):
                ui_text += open(p, encoding="utf-8").read()
        if not flow_text and not ui_text:
            warn(f"模块用例文件不在本机（{api_dir} / {ui_dir}），跳过 id 存在性核验"); n_warn += 1
        else:
            ids = set()
            for it in acov.get("endpoints") or []:
                ids.update(it.get("cases") or [])
            for pg in ucov.get("pages") or []:
                for inter in pg.get("interactions") or []:
                    ids.update(inter.get("cases") or [])
            for enums in (acov.get("enums") or {}, ucov.get("enums") or {}):
                for e in enums.values():
                    for cs in (e.get("covered") or {}).values():
                        ids.update(cs or [])
            missing = []
            for cid in sorted(ids):
                m = re.match(r"^(?:([^:]+):)?(.+)$", str(cid))
                if ":" in str(cid):   # flow:step_id 形式
                    if f"id: {m.group(2)}" not in flow_text: missing.append(cid)
                elif re.match(r"^S\d+$", str(cid)):  # UI 场景编号
                    if f'"{cid}"' not in ui_text and f"'{cid}'" not in ui_text and cid not in ui_text: missing.append(cid)
            if missing:
                fail(f"矩阵引用了不存在的用例 id（假覆盖）: {missing}"); n_fail += 1
            else:
                ok(f"{len(ids)} 个用例 id 全部真实存在")

    # ── verdict ─────────────────────────────────────────────
    print()
    if n_fail:
        print(f"VERDICT: 不放行（{n_fail} 缺口 / {n_warn} 警告）——补全后重跑本脚本")
        return 1
    print(f"VERDICT: 放行（0 缺口 / {n_warn} 警告）——可进 ③tc-run")
    return 0

if __name__ == "__main__":
    sys.exit(main())
