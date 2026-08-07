#!/usr/bin/env python3
"""API flow runner：从 CDP Chrome 抓 cookie → 逐步执行 flow yaml → 保存含 response 的结果到 api-exec-result.json"""
import sys, os, json, re, time, copy, requests, yaml
from jsonpath_ng.ext import parse as jp_parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT  = os.path.join(BASE_DIR, "..", "..")
OUT_FILE = os.path.join(PROJECT, "auto", "api-exec-result.json")
CDP_PORT = 9333
BASE_URL = "https://test-risk.inshopline.com"

FLOW_FILES = [
    "flow.yaml",
    "flow-all-types.yaml",
    "flow-supplement.yaml",
    "flow-paths.yaml",
    "flow-negative.yaml",
]

# ── 1. 从 CDP Chrome 抓 Cookie ──────────────────────────────────────────────
def get_cookie_from_cdp():
    sys.path.insert(0, "/Users/liyanda/.claude/skills/api-flow-recorder/scripts")
    try:
        from cdplib import connect
        cdp, _, _ = connect()
    except Exception as e:
        print(f"❌ 无法连接 CDP port {CDP_PORT}：{e}")
        print("   请先启动 Chrome：")
        print(f"   open -a 'Google Chrome' --args --remote-debugging-port={CDP_PORT} --user-data-dir=$HOME/.chrome-test-profile")
        sys.exit(1)

    result = cdp.cmd("Network.getCookies", {"urls": [BASE_URL]})
    cookies = result.get("cookies", [])
    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

    if not cookie_str:
        print("❌ Cookie 为空，请先在 Chrome(port 9333) 登录 test-risk.inshopline.com"); sys.exit(1)
    print(f"✅ 抓到 Cookie（{len(cookies)} 条）")
    return cookie_str


# ── 2. 变量替换 ──────────────────────────────────────────────────────────────
def render(val, ctx):
    if isinstance(val, str):
        def repl(m):
            k = m.group(1)
            if k.startswith("ENV:"):
                return os.environ.get(k[4:], "")
            return str(ctx.get(k, m.group(0)))
        return re.sub(r"\{\{([^}]+)\}\}", repl, val)
    if isinstance(val, dict):
        return {k: render(v, ctx) for k, v in val.items()}
    if isinstance(val, list):
        return [render(i, ctx) for i in val]
    return val


# ── 3. JSONPath 取值 ────────────────────────────────────────────────────────
def jp_get(data, path):
    try:
        expr = jp_parse(path)
        matches = [m.value for m in expr.find(data)]
        return matches[0] if matches else None
    except Exception:
        return None


# ── 4. 单条 assert 校验 ────────────────────────────────────────────────────
def check_assert(assert_cfg, status_code, resp_json, ctx):
    results = []
    if not assert_cfg:
        return results

    # status check
    exp_status = assert_cfg.get("status")
    if exp_status:
        ok = (status_code == int(exp_status))
        results.append({"type":"status","expected":exp_status,"actual":status_code,"pass":ok})

    # json path checks
    for rule in assert_cfg.get("json", []):
        path   = rule.get("path","")
        actual = jp_get(resp_json, path)
        passed = False
        detail = {}
        if "equals" in rule:
            passed = (str(actual) == str(rule["equals"]))
            detail = {"type":"equals","path":path,"expected":rule["equals"],"actual":actual,"pass":passed}
        elif "contains" in rule:
            passed = (rule["contains"] in str(actual or ""))
            detail = {"type":"contains","path":path,"expected":rule["contains"],"actual":actual,"pass":passed}
        elif "exists" in rule:
            passed = (actual is not None) if rule["exists"] else (actual is None)
            detail = {"type":"exists","path":path,"expected":rule["exists"],"actual":actual is not None,"pass":passed}
        elif "not_exists" in rule:
            passed = (actual is None)
            detail = {"type":"not_exists","path":path,"actual":actual is not None,"pass":passed}
        results.append(detail)

    return results


# ── 5. 执行单个 flow yaml ─────────────────────────────────────────────────
def run_flow(filepath, cookie):
    with open(filepath) as f:
        flow = yaml.safe_load(f)

    run_id = str(int(time.time()))
    ctx = {
        "run_id": run_id,
        "base_url": flow.get("base_url", BASE_URL),
        "cookie": cookie,
    }
    # 注入 flow 级 variables（跳过 ENV: 占位符由 render 处理）
    for k, v in (flow.get("variables") or {}).items():
        if not str(v).startswith("{{"):
            ctx[k] = str(v)

    flow_name = flow.get("name", os.path.basename(filepath))
    step_results = []

    for step in flow.get("steps", []):
        sid   = step.get("id", "?")
        sdesc = step.get("desc", step.get("description", ""))
        req   = step.get("request", {})

        # db_check / skip_note 步骤不执行
        if not req:
            continue

        method  = render(req.get("method","GET"), ctx).upper()
        url     = render(req.get("url",""), ctx)
        headers = render(req.get("headers",{}), ctx)
        body    = render(req.get("json", req.get("body", None)), ctx)

        print(f"  [{sid}] {method} {url}")

        # 发请求
        t0 = time.time()
        try:
            resp = requests.request(
                method, url,
                headers=headers,
                json=body if isinstance(body, (dict, list)) else None,
                data=body if isinstance(body, str) else None,
                timeout=15, verify=False
            )
            elapsed_ms = int((time.time()-t0)*1000)
            status_code = resp.status_code
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = {"_raw": resp.text[:500]}
            resp_body_preview = json.dumps(resp_json, ensure_ascii=False)[:800]
        except Exception as e:
            step_results.append({
                "id":sid,"desc":sdesc,"method":method,"url":url,
                "status":0,"resp_preview":str(e),"asserts":[],"pass":False,
                "elapsed_ms":0
            })
            continue

        # extract 变量
        for var, path in (step.get("extract") or {}).items():
            val = jp_get(resp_json, path)
            if val is not None:
                ctx[var] = str(val)
                print(f"    → extract {var} = {val}")

        # 断言
        assert_results = check_assert(step.get("assert"), status_code, resp_json, ctx)
        all_pass = all(r.get("pass", False) for r in assert_results) if assert_results else True

        req_body_preview = json.dumps(body, ensure_ascii=False)[:800] if body else None
        step_results.append({
            "id":sid,"desc":sdesc,"method":method,"url":url,
            "req_body":req_body_preview,
            "status":status_code,"elapsed_ms":elapsed_ms,
            "resp_preview":resp_body_preview,
            "asserts":assert_results,
            "pass":all_pass,
            "db_check": step.get("db_check"),
        })

        status_label = "✅ PASS" if all_pass else "❌ FAIL"
        print(f"    {status_label} ({status_code}, {elapsed_ms}ms)")

    flow_pass = all(s["pass"] for s in step_results)
    return {"flow":flow_name,"file":os.path.basename(filepath),"steps":step_results,"pass":flow_pass,"run_id":run_id}


# ── 6. 主流程 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import urllib3; urllib3.disable_warnings()

    cookie = get_cookie_from_cdp()
    all_results = []

    for fn in FLOW_FILES:
        fp = os.path.join(BASE_DIR, fn)
        if not os.path.exists(fp):
            print(f"⚠️  跳过不存在的文件：{fn}"); continue
        print(f"\n{'='*55}\n▶ {fn}\n{'='*55}")
        result = run_flow(fp, cookie)
        all_results.append(result)
        label = "✅ PASS" if result["pass"] else "❌ FAIL"
        print(f"  {label} （{sum(s['pass'] for s in result['steps'])}/{len(result['steps'])} steps passed）")

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已写入：{OUT_FILE}")
