#!/usr/bin/env python3
"""kit-admin —— 模块工作区管理（层1：登记与舰队视图）

用法：
  python3 kit-admin.py status [--root <工作区根>] [--json]

工作区根：--root > 环境变量 TC_MODULES > 默认 ~/tc-modules
发现规则（零配置）：工作区下任何 */*/baseline.yaml = 一个模块（系统/模块 两级约定）

每模块报告：
  覆盖门     check_coverage.py 实跑（✓ / ✗ N缺口）
  verdict    最新 docs/reports/verify-*.md 的结论 + 日期
  最近报告   docs/reports/*.html 最新一份的日期
  audit_base 锚 vs 本地仓当前 HEAD（落后 N commit / 未锚 / 无仓）

退出码：0=全部健康；1=有模块需关注（门未过 或 verdict=FAIL）
"""
import argparse, datetime, glob, json, os, re, subprocess, sys

KIT_ROOT = os.path.dirname(os.path.abspath(__file__))

def sh(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.stdout.strip() if r.returncode == 0 else None

def disp_w(s):  # 中文按 2 宽算，表格对齐用
    return sum(2 if ord(c) > 0x2E80 else 1 for c in s)

def pad(s, n):
    return s + " " * max(0, n - disp_w(s))

def discover(root):
    mods = []
    for bl in sorted(glob.glob(os.path.join(root, "*", "*", "baseline.yaml"))):
        m = os.path.dirname(bl)
        mods.append({"system": os.path.basename(os.path.dirname(m)),
                     "module": os.path.basename(m), "root": m})
    return mods

def check(mod):
    import yaml
    root = mod["root"]
    bl = yaml.safe_load(open(os.path.join(root, "baseline.yaml"), encoding="utf-8")) or {}
    mod["title"] = bl.get("title") or mod["module"]

    # 覆盖门（实跑，只读）
    cc = os.path.join(KIT_ROOT, "steps", "2-cases", "check_coverage.py")
    r = subprocess.run([sys.executable, cc, root], capture_output=True, text=True)
    if r.returncode == 0:
        mod["gate"] = "✓"
    else:
        m = re.search(r"(\d+) 缺口", r.stdout)
        mod["gate"] = f"✗ {m.group(1)}缺口" if m else "✗"

    # verdict（最新 verify-*.md）
    vd = sorted(glob.glob(os.path.join(root, "docs", "reports", "verify-*.md")))
    if vd:
        txt = open(vd[-1], encoding="utf-8").read()
        m = re.search(r"结论[:：]\s*\**\s*(PASS(?:-with-notes)?|FAIL)", txt)
        mod["verdict"] = (m.group(1) if m else "?")
        mod["verdict_date"] = os.path.basename(vd[-1])[7:-3]
    else:
        mod["verdict"], mod["verdict_date"] = "—", ""

    # 最近回归报告
    reps = sorted(glob.glob(os.path.join(root, "docs", "reports", "*.html")),
                  key=os.path.getmtime)
    mod["report"] = (datetime.date.fromtimestamp(os.path.getmtime(reps[-1])).isoformat()
                     if reps else "—")

    # audit_base 锚 vs 本地 HEAD
    drift = []
    for side, info in (bl.get("repos") or {}).items():
        ab = (info or {}).get("audit_base") or ""
        local = (info or {}).get("local")
        if "待回填" in ab or not ab:
            drift.append(f"{side}:未锚"); continue
        h = ab.split("@")[-1]
        now = sh(["git", "-C", local, "rev-parse", "--short", "HEAD"]) if local and os.path.isdir(local) else None
        if not now:
            drift.append(f"{side}:无仓"); continue
        if h != now:
            ahead = sh(["git", "-C", local, "rev-list", "--count", f"{h}..HEAD"]) or "?"
            drift.append(f"{side}:落后{ahead}c")
    mod["drift"] = " ".join(drift) if drift else "✓"
    return mod

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status"], default="status", nargs="?")
    ap.add_argument("--root", default=os.environ.get("TC_MODULES",
                   os.path.expanduser("~/tc-modules")))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        print(f"ℹ️  工作区 {root} 不存在——先用 new-module.sh 建第一个模块："
              f"\n   ~/baseline-test/steps/1-explore/new-module.sh {root}/<系统>/<模块> ...")
        return 0

    mods = [check(m) for m in discover(root)]

    # 约定检查：模块直接放根下（少一级系统目录）
    orphans = [os.path.dirname(p) for p in glob.glob(os.path.join(root, "*", "baseline.yaml"))]

    if a.json:
        print(json.dumps({"workspace": root, "modules": mods,
                          "orphans": orphans}, ensure_ascii=False, indent=2))
    else:
        cols = [("系统", "system"), ("模块", "title"), ("覆盖门", "gate"),
                ("verdict", "verdict"), ("verdict日期", "verdict_date"),
                ("最近报告", "report"), ("audit_base", "drift")]
        rows = []
        for m in mods:
            v = m["verdict"] + (f"({m['verdict_date']})" if m["verdict_date"] else "")
            rows.append([m["system"], m["title"], m["gate"], v, m["report"], m["drift"]])
        header = [c[0] for c in cols[:2]] + [c[0] for c in cols[2:4]] + [cols[5][0], cols[6][0]]
        # 列宽 = 表头与数据取宽
        table = [header] + rows
        widths = [max(disp_w(r[i]) for r in table) for i in range(len(header))]
        line = "-+-".join("-" * w for w in widths)
        print(f"工作区：{root}（{len(mods)} 模块）")
        for i, r in enumerate(table):
            print(" | ".join(pad(str(r[j]), widths[j]) for j in range(len(header))))
            if i == 0:
                print(line)
        for o in orphans:
            print(f"⚠️  {o} 少一级系统目录，不合 系统/模块 约定（status 发现不了它）")
        attention = [m for m in mods if m["gate"] != "✓" or m["verdict"] == "FAIL"]
        if mods:
            print(f"\n需关注：{len(attention)}/{len(mods)}"
                  + ("（门未过 / verdict=FAIL）" if attention else "——全部健康 ✅"))

    attention = [m for m in mods if m["gate"] != "✓" or m["verdict"] == "FAIL"]
    return 1 if attention else 0

if __name__ == "__main__":
    raise SystemExit(main())
