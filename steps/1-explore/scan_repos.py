#!/usr/bin/env python3
"""tc-explore 双源代码扫描器：后端路由/枚举 + 前端路由，产出三份 draft 供 ① 圈选合成。

用法：
  python3 steps/1-explore/scan_repos.py <模块根> \
      [--backend <本地后端仓>] [--frontend <本地前端仓>] \
      [--api-prefix /mapi/cs/issue] [--frontend-key normal-work-order] \
      [--diff]

repo 路径缺省读 <模块根>/baseline.yaml 的 repos.*.local。

产出（写入 <模块根>/explore/，全是 draft——① 的 LLM 圈选模块相关子集再进功能地图）：
  backend-endpoints.yaml   注释路由全集（@Get/@Post...，beego 形态；非此形态的仓由①人工补）
  enums-draft.yaml         枚举维度表草稿（EnumType{Code,Desc} 对 + 前端交叉引用）
  frontend-pages.yaml      前端路由树（config/routes.ts 形态）
  audit-<date>.md          仅 --diff：与上次落盘 draft 的增量审计报告（回填循环第③层）

--diff：先读旧 draft，重扫对比，输出新增/消失的 endpoint·枚举值·路由，然后
**刷新 draft 为本次结果**（draft 即上次扫描的锚，scan_base 字段记录 commit）。

退出码：0=扫描完成 / 无漂移；1=--diff 检出漂移（有增量待回填）；2=仓库路径不存在
"""
import argparse, os, re, sys, datetime, subprocess

def die(msg):
    print(f"❌ {msg}", file=sys.stderr)
    raise SystemExit(2)

# ── 后端：注释路由 ────────────────────────────────────────────────
ANNO = re.compile(r'^//\s*@(Get|Post|Put|Delete|Patch)\s+(\S+)\s*$', re.M)
FUNC = re.compile(r'^func\s+(\([^)]*\)\s*)?(\w+)', re.M)

def scan_endpoints(backend, prefix):
    out = []
    for dirpath, _dirs, files in os.walk(backend):
        if any(x in dirpath for x in ("/vendor/", "/.git/", "/node_modules/", "/test")):
            continue
        for fn in files:
            if not fn.endswith(".go"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                src = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            for m in ANNO.finditer(src):
                method, path = m.group(1).upper(), m.group(2)
                if prefix and prefix not in path:
                    continue
                # 注释后最近的 func = handler
                tail = src[m.end():]
                fm = FUNC.search(tail)
                handler = fm.group(2) if fm else "?"
                rel = os.path.relpath(p, backend)
                line = src[:m.start()].count("\n") + 1
                out.append({"method": method, "path": path,
                            "handler": handler, "ref": f"{rel}:{line}"})
    out.sort(key=lambda e: (e["path"], e["method"]))
    return out

# ── 后端：枚举（EnumType 对优先，const 字符串枚举兜底） ─────────────
ENUMTYPE = re.compile(r'var\s+(\w+)\s*=\s*_type\.EnumType\{Code:\s*"([^"]+)",\s*Desc:\s*"([^"]+)"\}')
CONST_STR = re.compile(r'^\s*(\w+)\s*=\s*\w*Enum\w*\(\s*"([^"]+)"\s*\)\s*(?://\s*(.+?))?\s*$', re.M)

def scan_enums(backend):
    dims = []
    for dirpath, _dirs, files in os.walk(backend):
        if any(x in dirpath for x in ("/vendor/", "/.git/")):
            continue
        for fn in files:
            if not (fn.endswith("_enum.go") or fn.endswith("_enums.go")):
                continue
            p = os.path.join(dirpath, fn)
            src = open(p, encoding="utf-8", errors="ignore").read()
            pairs, seen = [], set()
            for m in ENUMTYPE.finditer(src):
                var, code, desc = m.groups()
                if code not in seen:
                    seen.add(code)
                    pairs.append({"code": code, "desc": desc})
            if not pairs:  # 仓里没有 EnumType 工厂时兜底：const 字符串枚举（desc 取行尾注释）
                for m in CONST_STR.finditer(src):
                    _var, code, comment = m.groups()
                    if code and code not in seen:
                        seen.add(code)
                        pairs.append({"code": code, "desc": (comment or "").strip()})
            if not pairs:
                continue
            rel = os.path.relpath(p, backend)
            name = re.sub(r'_enums?\.go$', '', fn)
            dims.append({"name": name, "source_file": rel,
                         "values": pairs,
                         "behavior_branch": None,   # ① 补：该维度不同值是否走不同代码分支
                         "note": ""})
    dims.sort(key=lambda d: d["name"])
    return dims

# ── 前端：路由树 + 枚举交叉引用 ────────────────────────────────────
ROUTE_PATH = re.compile(r"path:\s*['\"]([^'\"]+)['\"]")
ROUTE_COMP = re.compile(r"component:\s*['\"]([^'\"]+)['\"]")

def scan_routes(frontend, key):
    rc = None
    for cand in ("config/routes.ts", "config/routes.js", "src/router.ts", "src/routes.ts"):
        p = os.path.join(frontend, cand)
        if os.path.exists(p):
            rc = p
            break
    if not rc:
        return None, f"未找到路由文件（找了 config/routes.ts 等 4 个位置）——① 人工指认"
    src = open(rc, encoding="utf-8", errors="ignore").read()
    lines = src.splitlines()
    routes = []
    for i, line in enumerate(lines):
        m = ROUTE_PATH.search(line)
        if not m:
            continue
        path = m.group(1)
        comp = ""
        for j in range(i, min(i + 4, len(lines))):
            cm = ROUTE_COMP.search(lines[j])
            if cm:
                comp = cm.group(1)
                break
        routes.append({"path": path, "component": comp, "ref": f"{os.path.relpath(rc, frontend)}:{i+1}"})
    if key:
        routes = [r for r in routes if key in r["path"] or key in r["component"]]
    return routes, None

def cross_ref(frontend, dims):
    """后端枚举 code 在前端哪些文件出现（双源互证 + 找 label 映射）"""
    codes = {v["code"] for d in dims for v in d["values"] if len(v["code"]) >= 4}
    if not codes:
        return
    pat = re.compile("|".join(re.escape(c) for c in sorted(codes)))
    for dirpath, _dirs, files in os.walk(os.path.join(frontend, "src")):
        for fn in files:
            if not fn.endswith((".ts", ".tsx")):
                continue
            p = os.path.join(dirpath, fn)
            try:
                src = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            hits = set(pat.findall(src))
            if not hits:
                continue
            rel = os.path.relpath(p, frontend)
            for d in dims:
                dcodes = {v["code"] for v in d["values"]}
                if hits & dcodes:
                    d.setdefault("frontend_refs", []).append(rel)

def git_anchor(repo):
    """当前分支@短hash——draft 的扫描锚，下次 --diff 的对照基准"""
    def g(*args):
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""
    br, h = g("rev-parse", "--abbrev-ref", "HEAD"), g("rev-parse", "--short", "HEAD")
    return f"{br}@{h}" if h else None

def load_draft(path, key):
    if not os.path.exists(path):
        return None
    import yaml
    d = yaml.safe_load(open(path, encoding="utf-8")) or {}
    return d.get(key)

def diff_report(old, eps, dims, routes, be_now, fe_now, out_dir):
    """旧 draft vs 本次扫描 → 增量审计报告。返回漂移条数。"""
    date = datetime.date.today().isoformat()
    L = [f"# 增量审计报告 audit-{date}", ""]
    L.append(f"- 本次扫描锚：backend `{be_now}` ｜ frontend `{fe_now}`")
    L.append("- 处置路径：新增项 → 功能地图回填 → ②增量用例 → check_coverage 重跑；")
    L.append("  消失项 → 核实是否下线/迁移，功能地图与 coverage 同步删。本报告不改任何用例。")
    L.append("")

    n = 0
    # endpoint
    k = lambda e: (e["method"], e["path"])
    old_eps = old.get("endpoints") or []
    if eps is not None and old_eps is not None:
        gone = [e for e in old_eps if k(e) not in {k(x) for x in eps}]
        new = [e for e in eps if k(e) not in {k(x) for x in old_eps}]
        if new or gone:
            L.append(f"## endpoint 变更（+{len(new)} / -{len(gone)}）")
            for e in new:  L.append(f"- ➕ {e['method']} `{e['path']}`  ({e['ref']})")
            for e in gone: L.append(f"- ➖ {e['method']} `{e['path']}`")
            L.append(""); n += len(new) + len(gone)
    # enums
    old_dims = {d["name"]: d for d in (old.get("dimensions") or [])}
    new_dims = {d["name"]: d for d in dims}
    for name in sorted(set(old_dims) | set(new_dims)):
        o, w = old_dims.get(name), new_dims.get(name)
        if o is None:
            L.append(f"## 枚举新增维度：{name}（{w['source_file']}，{len(w['values'])} 值）"); L.append(""); n += 1; continue
        if w is None:
            L.append(f"## 枚举消失维度：{name}（{o['source_file']}）"); L.append(""); n += 1; continue
        oc = {v["code"] for v in o["values"]}; wc = {v["code"] for v in w["values"]}
        add = [v for v in w["values"] if v["code"] not in oc]
        sub = [v for v in o["values"] if v["code"] not in wc]
        if add or sub:
            L.append(f"## 枚举[{name}] 变更（{w['source_file']}）")
            for v in add: L.append(f"- ➕ {v['code']} = {v['desc'] or '?'}")
            for v in sub: L.append(f"- ➖ {v['code']} = {v['desc'] or '?'}")
            L.append(""); n += len(add) + len(sub)
    # routes
    old_routes = old.get("routes") or []
    if routes and old_routes:
        op = {r["path"] for r in old_routes}; wp = {r["path"] for r in routes}
        add = wp - op; sub = op - wp
        if add or sub:
            L.append(f"## 前端路由变更（+{len(add)} / -{len(sub)}）")
            for p in sorted(add): L.append(f"- ➕ `{p}`")
            for p in sorted(sub): L.append(f"- ➖ `{p}`")
            L.append(""); n += len(add) + len(sub)

    if n == 0:
        L.append("## 无漂移")
        L.append("")
        L.append("endpoint / 枚举 / 路由与上次落盘 draft 完全一致——无需回填。")
    path = os.path.join(out_dir, f"audit-{date}.md")
    open(path, "w", encoding="utf-8").write("\n".join(L))
    return n, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("module_root")
    ap.add_argument("--backend"); ap.add_argument("--frontend")
    ap.add_argument("--api-prefix", default="")
    ap.add_argument("--frontend-key", default="")
    ap.add_argument("--diff", action="store_true",
                    help="与上次落盘 draft 对比出增量审计报告（回填循环第③层）")
    a = ap.parse_args()

    ROOT = os.path.abspath(a.module_root)
    blp = os.path.join(ROOT, "baseline.yaml")
    backend = frontend = None
    if os.path.exists(blp):
        try:
            import yaml
            bl = yaml.safe_load(open(blp, encoding="utf-8")) or {}
            repos = bl.get("repos") or {}
            backend = (repos.get("backend") or {}).get("local")
            frontend = (repos.get("frontend") or {}).get("local")
        except Exception:
            pass
    backend = a.backend or backend
    frontend = a.frontend or frontend
    if not backend or not os.path.isdir(backend):
        die(f"后端仓不可用：{backend}（--backend 或 baseline.yaml repos.backend.local）")
    if not frontend or not os.path.isdir(frontend):
        die(f"前端仓不可用：{frontend}（--frontend 或 baseline.yaml repos.frontend.local）")

    out_dir = os.path.join(ROOT, "explore")
    os.makedirs(out_dir, exist_ok=True)
    import yaml

    # --diff：先收旧 draft（重扫后会被刷新，先读后写）
    old = {}
    if a.diff:
        old["endpoints"]  = load_draft(os.path.join(out_dir, "backend-endpoints.yaml"), "endpoints")
        old["dimensions"] = load_draft(os.path.join(out_dir, "enums-draft.yaml"), "dimensions")
        old["routes"]     = load_draft(os.path.join(out_dir, "frontend-pages.yaml"), "routes")
        if old["endpoints"] is None and old["dimensions"] is None:
            print("ℹ️  无旧 draft——本次作为首扫基线（diff 无从对比）")

    print(f"▶ 后端路由扫描 {backend}（prefix={a.api_prefix or '全集'}）")
    eps = scan_endpoints(backend, a.api_prefix)
    print(f"  {len(eps)} 个 endpoint")

    print("▶ 后端枚举扫描（*enum*.go）")
    dims = scan_enums(backend)
    print(f"  {len(dims)} 个维度，共 {sum(len(d['values']) for d in dims)} 值")

    print(f"▶ 前端路由扫描 {frontend}（key={a.frontend_key or '全集'}）")
    routes, err = scan_routes(frontend, a.frontend_key)
    if err:
        print(f"  ⚠️  {err}")
    else:
        print(f"  {len(routes)} 条路由")

    print("▶ 前端交叉引用（枚举 code ↔ src 文件）")
    cross_ref(frontend, dims)

    # 扫描锚（draft 自带 commit，下次 --diff 的对照基准）
    scan_base = {"backend": git_anchor(backend), "frontend": git_anchor(frontend)}

    drift_n = None
    if a.diff:
        n, audit_path = diff_report(old, eps, dims, routes or [],
                                    scan_base["backend"], scan_base["frontend"], out_dir)
        drift_n = n
        print(f"\n▶ 增量审计：{'🔴 ' + str(n) + ' 条漂移' if n else '🟢 无漂移'} → {audit_path}")

    yaml.safe_dump({"generated": datetime.date.today().isoformat(), "scan_base": scan_base,
                    "api_prefix": a.api_prefix, "endpoints": eps},
                   open(os.path.join(out_dir, "backend-endpoints.yaml"), "w", encoding="utf-8"),
                   allow_unicode=True, sort_keys=False)
    if routes is not None:
        yaml.safe_dump({"generated": datetime.date.today().isoformat(), "scan_base": scan_base,
                        "frontend_key": a.frontend_key, "routes": routes},
                       open(os.path.join(out_dir, "frontend-pages.yaml"), "w", encoding="utf-8"),
                       allow_unicode=True, sort_keys=False)
    yaml.safe_dump({"generated": datetime.date.today().isoformat(), "scan_base": scan_base,
                    "note": "draft——① 圈选模块相关维度进功能地图枚举维度表，并补 behavior_branch 列",
                    "dimensions": dims},
                   open(os.path.join(out_dir, "enums-draft.yaml"), "w", encoding="utf-8"),
                   allow_unicode=True, sort_keys=False)

    print(f"\n✅ draft 已刷新 {out_dir}/（scan_base={scan_base['backend']}）：圈选后进功能地图；不相关的维度显式排除（写进 note），不许静默丢")
    if a.diff and drift_n:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
