#!/usr/bin/env python3
"""验证：创建目录(拿有效data pid) → 创建用例 pid=data → 查 pidList 是否归位。
在你本地跑（能访问 platform-sg.myshopline.com 的网络）。"""
import urllib.request, json, random, time

TOKEN = "Usr-NRH1ZYv9KBeGOkwMvc6gfj-ewbWZ"
SPACE = "10001"
BASE = "https://platform-sg.myshopline.com"

def call(method, path, body=None):
    req = urllib.request.Request(BASE+path, data=json.dumps(body).encode() if body else None, method=method)
    for k,v in {"accept":"application/json","content-type":"application/json;charset=UTF-8",
                "access-token":TOKEN,"space-id":SPACE}.items():
        req.add_header(k,v)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

FIXED = {"editable":True,"initCaseInfo":None,"domain":None,"cicdState":False,"shareState":False,
         "redirectState":True,"urlEncoded":False,"requestParams":[],"service":None,
         "registryCenter":{"protocol":"nacos","address":""},"processor":[],"consumerService":{},
         "configCenter":{"protocol":"nacos"},"updated":False}

# 1. 创建目录，拿返回 data（有效 pid）
nid = str(random.randint(8*10**16, 9*10**16))
r = call("POST","/api/autotest/dir/node",{"isLeaf":False,"pid":"81979651796025344",
        "name":"风控工单自动化用例","id":nid,"nodeType":"DIR","children":[]})
dir_pid = str(r.get("data",""))
print(f"[1] 创建目录: 传入id={nid}  返回data(pid)={dir_pid}")

# 2. 创建用例，pid=目录data
case = dict(FIXED); case.update({
    "name":"_PID_VERIFY_","protocol":"HTTP","creator":10273,"groupId":10088,
    "address":"https://test-risk.inshopline.com/mapi/cs/issue/base/enums","method":"GET",
    "requestHeaders":[{"id":"h1","key":"appId","value":"4","description":"","shareState":False}],
    "requestBody":"","contentType":"JSON","pid":dir_pid,"id":None})
r = call("POST","/api/autotest/cases/case",case)
print(f"[2] 创建用例 pid={dir_pid}: {r.get('msg')} id={r.get('data')}")

# 3. 查用例 pidList（关键）
r = call("POST","/api/autotest/cases",{"groupId":10088,"pageNum":1,"pageSize":1})
c = r["data"]["pageInfo"][0]
print(f"[3] 最新用例 #{c['id']} pidList = {c.get('pidList')}")

# 4. 查新目录用例数（1=归位成功）
r = call("POST","/api/autotest/dir/cases",{"pageNum":1,"pageSize":3,"id":dir_pid})
tc = r["data"].get("totalCount")
print(f"[4] 新目录用例数 = {tc}  ({'✅ 归位成功！pid=目录data 可用' if tc==1 else '❌ 未归位，pid 不设 pidList'})")
print(f"\n有效目录 pid = {dir_pid}")
