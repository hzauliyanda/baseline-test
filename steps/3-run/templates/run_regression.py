#!/usr/bin/env python3
"""
run_regression.py —— ③tc-run 编排器（工具无关）

读模块根的 baseline.yaml，按序执行 API 回归 → UI 回归 → 报告生成，收口打印对账。

用法（在模块根目录）:
    python3 run_regression.py               # 全量：API + UI + 报告
    python3 run_regression.py --api-only    # 只跑 API + 报告
    python3 run_regression.py --ui-only     # 只跑 UI + 报告
    python3 run_regression.py --dry-run     # 只做预检，不执行

退出码: 0=跑完（含已知恒红） 1=预检失败或执行器崩溃 2=用法错误
「全绿判定」不在本脚本——回归结果与 baseline.yaml 口径的对账归 ④tc-verify。

依赖: python3≥3.9 / pyyaml / requests / jsonpath_ng；ego-browser 已登录目标系统。
"""
import os, sys, json, subprocess, time, shutil
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE                           # run_regression.py 放模块根，auto/ 在其下

API_RUNNER = os.path.join(ROOT, "auto", "api", "api_runner.py")
UI_RUNNER  = os.path.join(ROOT, "auto", "ui", "ego_ui_runner.py")
REPORT_GEN = os.path.join(HERE, "gen_report.py")
API_RESULT = os.path.join(ROOT, "auto", "api-exec-result.json")
UI_RESULT  = os.path.join(ROOT, "auto", "ui-ego-exec-result.json")

def die(msg, code=1):
    print(f"🔴 预检失败: {msg}"); sys.exit(code)

def precheck(api=True, ui=True):
    print("== 预检 ==")
    bl_path = os.path.join(ROOT, "baseline.yaml")
    if os.path.isfile(bl_path):
        bl = yaml.safe_load(open(bl_path, encoding="utf-8")) or {}
        url = (bl.get("entry_url") or "").strip()
        if url:
            os.environ.setdefault("TC_BASE_URL", url)
            print(f"  🟢 baseline.yaml: {bl.get('module')} @ {url}")
        else:
            die("baseline.yaml 存在但 entry_url 为空")
    else:
        print("  🟡 无 baseline.yaml（回退各 runner 内置配置）——建议补上，见 steps/schema/baseline.yaml")

    if not shutil.which("ego-browser"):
        die("ego-browser 不在 PATH——先安装并登录目标系统")
    print("  🟢 ego-browser 在 PATH")

    if api:
        flows = [f for f in os.listdir(os.path.join(ROOT, "auto", "api"))
                 if f.startswith("flow") and f.endswith(".yaml")] if os.path.isdir(os.path.join(ROOT, "auto", "api")) else []
        if not flows:
            die("auto/api/ 下没有 flow*.yaml——先跑 ①②")
        if not os.path.isfile(API_RUNNER):
            die(f"缺 {API_RUNNER}（从 kit steps/3-run/templates/ 拷入）")
        print(f"  🟢 API: {len(flows)} 份 flow")
    if ui:
        if not os.path.isfile(UI_RUNNER):
            die(f"缺 {UI_RUNNER}（从 kit steps/3-run/templates/ 拷入）")
        if not os.path.isfile(os.path.join(ROOT, "auto", "ui", "ego_scenarios.py")):
            die("缺 auto/ui/ego_scenarios.py——UI 场景未派生，先跑 ②")
        print("  🟢 UI: ego_ui_runner + ego_scenarios")
    if not os.path.isfile(REPORT_GEN):
        die(f"缺 {REPORT_GEN}（从 kit steps/3-run/templates/ 拷入）")

def run(label, cmd, result_file=None, timeout=1800):
    print(f"\n{'='*55}\n▶ {label}\n{'='*55}", flush=True)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, timeout=timeout)
    dt = time.time() - t0
    if p.returncode != 0:
        print(f"🔴 {label} 执行器退出码 {p.returncode}（{dt:.0f}s）"); return False, dt
    if result_file and not os.path.isfile(result_file):
        print(f"🔴 {label} 跑完但没落 {os.path.basename(result_file)}"); return False, dt
    print(f"🟢 {label} 完成（{dt:.0f}s）"); return True, dt

def summarize():
    print(f"\n{'='*55}\n▶ 对账\n{'='*55}")
    ok = True
    for name, path in (("API", API_RESULT), ("UI", UI_RESULT)):
        if not os.path.isfile(path):
            print(f"  — {name}: 无结果文件"); continue
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            print(f"  🔴 {name} 结果解析失败: {e}"); ok = False; continue
        if name == "API":
            total = sum(len(f["steps"]) for f in data)
            npass = sum(1 for f in data for s in f["steps"] if s["pass"])
            print(f"  API: {npass}/{total} step PASS" + (f"，❌ {total-npass} FAIL" if npass < total else "，全绿"))
        else:
            summ = (data.get("summary") or {})
            print(f"  UI: {summ.get('pass', '?')} PASS / {summ.get('fail', '?')} FAIL / {summ.get('skip', '?')} SKIP"
                  f"（{len(data.get('scenes') or {})} 场景）")
    bl_path = os.path.join(ROOT, "baseline.yaml")
    if os.path.isfile(bl_path):
        base = ((yaml.safe_load(open(bl_path, encoding="utf-8")) or {}).get("regression") or {}).get("baseline") or {}
        for k, v in base.items():
            print(f"  基线口径[{k}]: {v}")
        print("  ↑ 与上面数字不符时：先查是回归还是基线口径过期，再进 ④tc-verify")
    return ok

def main():
    if "--dry-run" in sys.argv and len(sys.argv) > 2 and sys.argv[1] != "--dry-run":
        print(__doc__); sys.exit(2)
    api = "--ui-only" not in sys.argv
    ui  = "--api-only" not in sys.argv
    dry = "--dry-run" in sys.argv
    precheck(api=api, ui=ui)          # dry-run 也做全量预检（这就是它的意义）
    if dry:
        print("\n🟢 dry-run 预检通过（未执行）"); sys.exit(0)

    ok = True
    if api:
        ok &= run("API 回归", [sys.executable, API_RUNNER], API_RESULT)[0]
    if ui:
        ok &= run("UI 回归", [sys.executable, UI_RUNNER], UI_RESULT)[0]
    if ok:
        ok &= run("报告生成", [sys.executable, REPORT_GEN])[0]
    ok &= summarize()
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
