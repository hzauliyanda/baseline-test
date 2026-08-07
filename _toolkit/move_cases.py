#!/usr/bin/env python3
"""把已上传的 76 个用例移到新目录（PUT 更新 pidList）。
复用 upload_cases 的 build_case，加 id + pidList，PUT /cases/case。"""
import json, yaml, urllib.request, time
from config import load, abspath, octopuses_token   # 去硬编码：走 config.yaml

_cfg=load(); _oc=_cfg["octopuses"]
TOKEN=octopuses_token(_cfg); SPACE_ID=_oc["space_id"]
GROUP_ID=_oc["group_id"]; PID=_oc["pid"]; CREATOR=_oc["creator"]
_sys=_cfg["systems"]["risk"]; BASE=_sys["base_url"]
DEF_HEADERS=_sys.get("headers",{}) or {}; COOKIE_REF="${"+_sys["cookie_env"]+"}"
NEW_DIR=str(_oc["move_target_dir"])   # 移动目标目录
START_ID=_oc["move_start_id"]         # 第一个用例 id
EP=_oc["endpoint"]

FIXED={"editable":True,"initCaseInfo":None,"domain":None,"cicdState":False,"shareState":False,
       "redirectState":True,"urlEncoded":False,"requestParams":[],"service":None,
       "registryCenter":{"protocol":"nacos","address":""},"processor":[],"consumerService":{},
       "configCenter":{"protocol":"nacos"},"updated":False}
FLOWS=[(u["label"], abspath(_cfg,u["flow"])) for u in _cfg.get("uploads",[])]
def ph(s):
    return s.replace("{{base_url}}",BASE).replace("{{","${").replace("}}","}") if isinstance(s,str) else s
def build(module,step):
    req=step.get("request",{}); method=req.get("method","GET")
    hin=req.get("headers",{}) or {}
    rhs=[{"id":"h1","key":"appId","value":str(hin.get("appId",DEF_HEADERS.get("appId","4"))),"description":"","shareState":False},
         {"id":"h2","key":"version","value":str(hin.get("version",DEF_HEADERS.get("version","v2"))),"description":"","shareState":False},
         {"id":"h3","key":"Cookie","value":COOKIE_REF,"description":"参数化","shareState":False}]
    body=""
    if method in ("POST","PUT","PATCH") and "json" in req:
        body=ph(json.dumps(req["json"],ensure_ascii=False))
        rhs.append({"id":"h4","key":"Content-Type","value":"application/json","description":"","shareState":False})
    c=dict(FIXED); c.update({"name":f"[{module}]{step.get('id','')} {step.get('desc','')[:40]}",
        "protocol":"HTTP","creator":CREATOR,"groupId":GROUP_ID,"address":ph(req.get("url","")),"method":method,
        "requestHeaders":rhs,"requestBody":body,"contentType":"JSON","pid":PID})
    return c
def put(case):
    req=urllib.request.Request(EP,data=json.dumps(case).encode(),method="PUT")
    for k,v in {"accept":"application/json","content-type":"application/json;charset=UTF-8",
                "access-token":TOKEN,"space-id":SPACE_ID}.items(): req.add_header(k,v)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            d=json.loads(r.read().decode()); return d.get("code")==0, d.get("msg","")
    except urllib.error.HTTPError as e:
        return False, f"HTTP{e.code}:"+e.read().decode()[:60]
    except Exception as e: return False, str(e)[:60]

cid=START_ID; ok=fail=0
for module,path in FLOWS:
    steps=yaml.safe_load(open(path))["steps"]
    print(f"\n[{module}] {path.split('/')[-1]}")
    for s in steps:
        case=build(module,s); case["id"]=cid; case["pidList"]=[NEW_DIR]
        success,msg=put(case)
        if success: ok+=1; print(f"  ✓ #{cid} -> 目录{NEW_DIR}")
        else: fail+=1; print(f"  ✗ #{cid} {msg[:60]}")
        cid+=1; time.sleep(0.25)
print(f"\n=== 移动完成: 成功 {ok} / 失败 {fail}，新目录={NEW_DIR}（风控工单接口自动化）===")
