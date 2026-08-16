#!/usr/bin/env python3
"""tc-verify 机算对账（第④步前半）：独立重算 + 交叉核对，输出 recon JSON。

用法：python3 steps/4-verify/verify_recon.py <模块根目录>

六项检查（全部只读，不改任何产物）：
  A 产物齐全     baseline.yaml / coverage×2 / api JSON / ui JSON / 最新报告 HTML
  B 数字对账     独立重算 JSON 数字，与报告 HTML 内嵌数字逐一比对（篡改/过期检测）
  C 恒红核对     API FAIL 所在 flow 是否都被 baseline 口径点名；UI FAIL 场景口径是否容纳
  D 覆盖门复跑   check_coverage.py 退出码必须 0
  E 假覆盖扫描   coverage 枚举 covered 列表为空 = 假覆盖
  F audit_base   已填=info；⏳待回填=warn（覆盖对账锚点缺失，④人工部分降级）

退出码：0=机算全过；1=有硬伤（审查必须介入）；2=baseline.yaml 缺失
产物：docs/reports/verify-recon-YYYY-MM-DD.json（干净上下文审查员的输入之一）
"""
import json, os, re, subprocess, sys, datetime

KIT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fail(msg):  print(f"  ❌ {msg}")
def warn(msg):  print(f"  ⚠️  {msg}")
def ok(msg):    print(f"  ✅ {msg}")

def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    ROOT = os.path.abspath(sys.argv[1])
    checks, findings, warns = [], [], []

    bl_path = os.path.join(ROOT, "baseline.yaml")
    if not os.path.exists(bl_path):
        fail(f"baseline.yaml 不存在：{bl_path}")
        raise SystemExit(2)
    import yaml
    bl = yaml.safe_load(open(bl_path, encoding="utf-8")) or {}
    reg = bl.get("regression") or {}
    caliber = reg.get("baseline") or {}

    # ── A 产物齐全 ────────────────────────────────────────────────
    print("== A 产物齐全 ==")
    api_json = os.path.join(ROOT, "auto", "api-exec-result.json")
    ui_json  = os.path.join(ROOT, "auto", "ui-ego-exec-result.json")
    cov = [os.path.join(ROOT, "coverage", n) for n in ("api-coverage.yaml", "ui-coverage.yaml")]
    arts = {"api-exec-result.json": api_json, "ui-ego-exec-result.json": ui_json,
            "coverage/api-coverage.yaml": cov[0], "coverage/ui-coverage.yaml": cov[1]}
    for repo in (bl.get("repos") or {}).values():
        pass  # url 只在 ②/① 检查，这里不 clone
    missing = [k for k, p in arts.items() if not os.path.exists(p)]

    # 报告：按 baseline 口径 pattern 找最新一份
    report = None
    pat = reg.get("report") or ""
    if pat:
        glob_pat = os.path.join(ROOT, pat.replace("YYYY-MM-DD", "2*"))
        import glob as g
        cands = sorted(g.glob(glob_pat), key=os.path.getmtime)
        report = cands[-1] if cands else None
    if not report:
        missing.append("回归报告 HTML（regression.report 模式匹配不到）")
    if missing:
        for m in missing: fail(f"缺产物：{m}"); findings.append(f"缺产物: {m}")
    else:
        ok("五类产物齐全")
    checks.append({"id": "A", "name": "产物齐全", "pass": not missing, "missing": missing})

    if missing:
        _write(ROOT, checks, findings, warns, bl)
        raise SystemExit(1)

    # ── B 数字对账（独立重算） ─────────────────────────────────────
    print("== B 数字对账（独立重算 vs 报告 HTML）==")
    api = json.load(open(api_json, encoding="utf-8"))
    ui  = json.load(open(ui_json, encoding="utf-8"))

    api_pass = api_fail = api_steps = api_db = 0
    for flow in api:
        for s in flow["steps"]:
            api_steps += 1
            if s["pass"]: api_pass += 1
            else:         api_fail += 1
            if s.get("db_check"): api_db += 1

    # UI 场景聚合：独立重实现（不 import gen_report——审查必须独立计算）
    scenes = {}
    for r in ui.get("records", []):
        st = r.get("status")
        cur = scenes.setdefault(r["scene"], set())
        cur.add(st)
    ui_pass = sum(1 for sts in scenes.values() if sts == {"PASS"})
    ui_fail = sum(1 for sts in scenes.values() if "FAIL" in sts)
    ui_skip = sum(1 for sts in scenes.values() if sts == {"SKIP"} and "FAIL" not in sts)

    html = open(report, encoding="utf-8", errors="ignore").read()
    nums = [n.strip() for n in re.findall(r'<div class="n"[^>]*>([^<]*)</div>', html)]
    # 模板固定顺序: ui_pass, ui_fail, ui_skip, ui_dur(fmt,跳过), api_pass, api_fail, api_steps, db, l3
    if len(nums) < 7:
        fail(f"报告 HTML 解析不到统计区（{len(nums)} 个数字）——模板变了？")
        findings.append("报告 HTML 统计区解析失败")
        num_ok = False
    else:
        pairs = [("UI PASS", nums[0], ui_pass), ("UI FAIL", nums[1], ui_fail),
                 ("UI SKIP", nums[2], ui_skip), ("API PASS", nums[4], api_pass),
                 ("API FAIL", nums[5], api_fail), ("API step", nums[6], api_steps)]
        bad = [(k, h, j) for k, h, j in pairs if h != str(j)]
        num_ok = not bad
        if bad:
            for k, h, j in bad:
                fail(f"报告[{k}]={h} 与 JSON 重算={j} 不符（篡改或报告过期）")
                findings.append(f"数字不符: 报告{k}={h} vs JSON={j}")
        else:
            ok(f"报告与 JSON 全部一致：UI {ui_pass}/{ui_fail}/{ui_skip}（{len(scenes)} 场景），"
               f"API {api_pass}/{api_fail}/{api_steps} step，🟡DB {api_db}")
    checks.append({"id": "B", "name": "数字对账", "pass": num_ok,
                   "recomputed": {"ui": {"pass": ui_pass, "fail": ui_fail, "skip": ui_skip,
                                         "scenes": len(scenes)},
                                  "api": {"pass": api_pass, "fail": api_fail,
                                          "steps": api_steps, "db_checks": api_db}}})

    # ── C 恒红核对 ────────────────────────────────────────────────
    print("== C 恒红核对（FAIL 必须被口径点名/容纳）==")
    c_findings = []
    api_cal = str(caliber.get("api", ""))
    for flow in api:
        for s in flow["steps"]:
            if s["pass"]: continue
            # 口径点名粒度 = step id（或 flow 文件名）；两者都不在口径 → 新红
            sid  = str(s.get("id", ""))
            fname = os.path.basename(flow["file"]).replace(".yaml", "")
            if sid not in api_cal and fname not in api_cal:
                c_findings.append(f"API [{fname}/{sid}] FAIL 但口径未点名 → 新红=疑似回归")
    ui_cal = str(caliber.get("ui", ""))
    for sc, sts in scenes.items():
        if "FAIL" in sts and sc not in ui_cal:
            c_findings.append(f"UI 场景 [{sc}] FAIL 但口径未容纳（口径原文：{ui_cal[:60]}…）")
    for m in c_findings: fail(m); findings.append(m)
    if not c_findings: ok("所有 FAIL 均在口径内（恒红）")
    checks.append({"id": "C", "name": "恒红核对", "pass": not c_findings, "findings": c_findings})

    # ── D 覆盖门复跑 ──────────────────────────────────────────────
    print("== D 覆盖门复跑（check_coverage.py）==")
    cc = os.path.join(KIT_ROOT, "steps", "2-cases", "check_coverage.py")
    r = subprocess.run([sys.executable, cc, ROOT], capture_output=True, text=True)
    cc_pass = (r.returncode == 0)
    tail = (r.stdout or "").strip().splitlines()[-3:]
    if cc_pass: ok(f"exit 0（{(tail[-1] if tail else '').strip()}）")
    else:
        fail(f"exit {r.returncode}——②覆盖缺口未清，按管道纪律本不应进③：")
        for line in tail: print(f"     {line}")
        findings.append("check_coverage 未放行（缺口未清）")
    checks.append({"id": "D", "name": "覆盖门复跑", "pass": cc_pass, "exit": r.returncode,
                   "tail": tail})

    # ── E 假覆盖扫描 ──────────────────────────────────────────────
    print("== E 假覆盖扫描（covered 空列表）==")
    e_findings = []
    for p in cov:
        if not os.path.exists(p): continue
        c = yaml.safe_load(open(p, encoding="utf-8")) or {}
        for name, e in ((c.get("enums") or {}).items()):
            for v, cs in ((e.get("covered") or {}).items()):
                if not cs or not str(cs[0]).strip():
                    e_findings.append(f"{os.path.basename(p)} 枚举[{name}] covered['{v}'] 空=假覆盖")
    for m in e_findings: fail(m); findings.append(m)
    if not e_findings: ok("无假覆盖行")
    checks.append({"id": "E", "name": "假覆盖扫描", "pass": not e_findings, "findings": e_findings})

    # ── F audit_base ──────────────────────────────────────────────
    print("== F audit_base（覆盖对账锚点）==")
    ab = {}
    for side in ("backend", "frontend"):
        v = ((bl.get("repos") or {}).get(side) or {}).get("audit_base") or ""
        ab[side] = v
        if "待回填" in v or not v:
            warn(f"repos.{side}.audit_base 待回填——④人工对账只能对到本地目录，对不到 commit")
            warns.append(f"audit_base[{side}] 待回填")
        else:
            ok(f"repos.{side}.audit_base = {v}")
    checks.append({"id": "F", "name": "audit_base", "pass": True, "values": ab})

    _write(ROOT, checks, findings, warns, bl)
    hard = any(not c["pass"] for c in checks)
    print("\n" + ("🔴 机算有硬伤，审查必须逐条裁决" if hard else "🟢 机算全过——继续干净上下文审查（见 PROMPT-审查清单.md）"))
    raise SystemExit(1 if hard else 0)

def _write(ROOT, checks, findings, warns, bl):
    out_dir = os.path.join(ROOT, "docs", "reports")
    os.makedirs(out_dir, exist_ok=True)
    date = datetime.date.today().isoformat()
    out = {
        "date": date,
        "module": bl.get("module") or os.path.basename(ROOT),
        "machine_result": "HARD_FAIL" if any(not c["pass"] for c in checks) else "PASS",
        "checks": checks,
        "findings": findings,
        "warnings": warns,
    }
    path = os.path.join(out_dir, f"verify-recon-{date}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n📦 机算结论落盘：{path}")

if __name__ == "__main__":
    main()
