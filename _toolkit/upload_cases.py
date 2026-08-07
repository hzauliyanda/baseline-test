#!/usr/bin/env python3
"""批量上传接口用例到测试平台 octopuses。
读 normal/complaint/punish 的 flow+supplement，每 step 转平台用例上传。
参数化：cookie=${RISK_COOKIE}、url=测试环境、占位 {{var}}→${var}。"""
import json, yaml, urllib.request, time, sys
from config import load, abspath, octopuses_token   # 去硬编码：环境/租户/平台参数全走 config.yaml

_cfg = load()
_oc = _cfg["octopuses"]
TOKEN = octopuses_token(_cfg); SPACE_ID = _oc["space_id"]; GROUP_ID = _oc["group_id"]
PID = _oc["pid"]; CREATOR = _oc["creator"]; ENDPOINT = _oc["endpoint"]
_sys = _cfg["systems"]["risk"]
BASE = _sys["base_url"]; DEF_HEADERS = _sys.get("headers", {}) or {}
COOKIE_REF = "${" + _sys["cookie_env"] + "}"

FIXED = {"editable":True,"initCaseInfo":None,"domain":None,"cicdState":False,"shareState":False,
         "redirectState":True,"urlEncoded":False,"requestParams":[],"service":None,
         "registryCenter":{"protocol":"nacos","address":""},"processor":[],"consumerService":{},
         "configCenter":{"protocol":"nacos"},"updated":False}

FLOWS = [(u["label"], abspath(_cfg, u["flow"])) for u in _cfg.get("uploads", [])]

def placeholder(s):
    if not isinstance(s, str): return s
    return s.replace("{{base_url}}", BASE).replace("{{", "${").replace("}}", "}")

def build_case(module, step):
    req = step.get("request", {})
    method = req.get("method", "GET")
    url = placeholder(req.get("url", ""))
    headers_in = req.get("headers", {}) or {}
    rhs = [
        {"id":"h-appid","key":"appId","value":str(headers_in.get("appId",DEF_HEADERS.get("appId","4"))),"description":"","shareState":False},
        {"id":"h-ver","key":"version","value":str(headers_in.get("version",DEF_HEADERS.get("version","v2"))),"description":"","shareState":False},
        {"id":"h-ck","key":"Cookie","value":COOKIE_REF,"description":"参数化-平台环境变量配","shareState":False},
    ]
    body = ""
    ct = "JSON"
    if method in ("POST","PUT","PATCH") and "json" in req:
        body = placeholder(json.dumps(req["json"], ensure_ascii=False))
        rhs.append({"id":"h-ct","key":"Content-Type","value":"application/json","description":"","shareState":False})
    elif method in ("POST","PUT","PATCH") and "data" in req:
        body = placeholder(str(req["data"]))
        rhs.append({"id":"h-ct","key":"Content-Type","value":"application/json","description":"","shareState":False})
    case = dict(FIXED)
    case.update({
        "name": f"[{module}]{step.get('id','')} {step.get('desc','')[:40]}",
        "protocol":"HTTP","creator":CREATOR,"groupId":GROUP_ID,
        "address":url,"method":method,"requestHeaders":rhs,
        "requestBody":body,"contentType":ct,"pid":PID,"id":None,
    })
    return case

def upload(case):
    data = json.dumps(case).encode()
    r = urllib.request.Request(ENDPOINT, data=data, method="POST")
    for k,v in {"accept":"application/json","content-type":"application/json;charset=UTF-8",
                "access-token":TOKEN,"space-id":SPACE_ID}.items():
        r.add_header(k,v)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            d = json.loads(resp.read().decode())
            return d.get("code")==0, d.get("data",{}).get("id") or d.get("msg")
    except urllib.error.HTTPError as e:
        return False, f"HTTP{e.code}:"+e.read().decode()[:80]
    except Exception as e:
        return False, str(e)[:80]

ok=fail=0; fails=[]
for module, path in FLOWS:
    flow = yaml.safe_load(open(path))
    steps = flow.get("steps",[])
    print(f"\n=== [{module}] {path.split('/')[-1]} ({len(steps)} step) ===")
    for s in steps:
        case = build_case(module, s)
        success, info = upload(case)
        if success: ok+=1; print(f"  ✓ #{info} {case['name'][:50]}")
        else: fail+=1; fails.append((case['name'],info)); print(f"  ✗ {case['name'][:50]} -> {info}")
        time.sleep(0.3)
print(f"\n=== 汇总: 成功 {ok} / 失败 {fail} ===")
if fails:
    print("失败明细:")
    for n,i in fails: print(f"  {n[:50]}: {i}")
