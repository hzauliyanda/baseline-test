#!/usr/bin/env bash
# capture_ego.sh —— ego-browser 版抓包（替代 recorder.py + launch_chrome.sh 的独立 CDP 通道）
# 用 ego-browser 自身 runtime 的 cdp('Network.enable')+drainEvents()+getResponseBody 抓当前 tab 的接口，
# 产出与 recorder.py 同 schema 的 capture/<session>.jsonl，再交给 to_curl.py 出三件套。
#
# 用法：
#   capture_ego.sh <session> reload            # 重载当前 tab 并抓（首屏/刷新型）
#   capture_ego.sh <session> goto <url>        # 导航到 url 并抓
#   capture_ego.sh <session> drain             # 只 drain 当前已排队事件（配合 agent 先点击后收集）
# 说明：
#   - 抓取“点击某按钮触发的接口”属交互型，由 agent 在 ego-browser heredoc 里 enable→点击→本脚本 drain；
#     或直接把 references/ego-capture.md 的抓包函数贴进 agent 自己的 heredoc（方案 A：每动作一轮）。
#   - jsonl 追加写（同 recorder），capture/ 已 gitignore（含 cookie 不入库）。
set -euo pipefail
SESSION="${1:-session}"
MODE="${2:-reload}"
URL="${3:-}"
ROOT="${TC_CAPTURE_ROOT:-$PWD}"
S="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/capture"
OUT="$ROOT/capture/$SESSION.jsonl"

# TAB_JS：enable 之前先把目标 tab 开好/选中（否则 Network.enable 绑到旧 tab）
# NAV_JS：enable 之后强制导航/reload，触发接口
TAB_JS="" ; NAV_JS=""
case "$MODE" in
  reload) TAB_JS="await ensureRealTab();"                              NAV_JS="const info=await pageInfo(); const nav=gotoAndWait(info.url,{timeout:30});" ;;
  goto)   TAB_JS="await openOrReuseTab(\"$URL\",{wait:true,timeout:30});" NAV_JS="const nav=gotoAndWait(\"$URL\",{timeout:30});" ;;
  drain)  TAB_JS="await ensureRealTab();"                              NAV_JS="const nav=Promise.resolve();" ;;
  *) echo "未知 MODE: $MODE（reload|goto|drain）" >&2; exit 2 ;;
esac

# 注：cliLog 输出走 stderr，故 2>&1；task space 用 session 名（登录/探索/抓包同一空间，tab 才在）
ego-browser nodejs <<EOF 2>&1 | grep '^__JSONL__' | sed 's/^__JSONL__//' >> "$OUT" || true
const task = await useOrCreateTaskSpace("$SESSION")
const KEEP=new Set(['XHR','Fetch','Document','EventSource'])
const NOISE=['/log','/track','/report','/metrics','/heartbeat','/ping','beacon','/collect','/rum','google-analytics','googletagmanager','sentry','hotjar']
const reqs={}, finished=[]
function ingest(evs){ for(const m of evs){ const md=m.method,p=m.params||{}
  if(md==='Network.requestWillBeSent'){const r=p.request||{}
    reqs[p.requestId]={wallTime:p.wallTime,type:p.type,method:r.method,url:r.url,headers:{...(r.headers||{})},post_data:r.postData||'',has_post:!!r.hasPostData,status:null,mime:null,response_body:null}}
  else if(md==='Network.requestWillBeSentExtraInfo'){if(reqs[p.requestId])Object.assign(reqs[p.requestId].headers,p.headers||{})}
  else if(md==='Network.responseReceived'){if(reqs[p.requestId]){reqs[p.requestId].status=(p.response||{}).status;reqs[p.requestId].mime=(p.response||{}).mimeType}}
  else if(md==='Network.loadingFinished'){finished.push(p.requestId)} } }

$TAB_JS
await cdp('Network.enable',{maxPostDataSize:262144})
await drainEvents()
$NAV_JS
for(let i=0;i<16;i++){ await wait(0.5); ingest(await drainEvents()) }
await nav.catch(()=>{}); ingest(await drainEvents())
for(const rid of finished){ const r=reqs[rid]; if(!r||!KEEP.has(r.type))continue
  try{const b=await cdp('Network.getResponseBody',{requestId:rid}); r.response_body=(b.base64Encoded?'':(b.body||'')).slice(0,20000)}catch(e){} }
let n=0
for(const rid of Object.keys(reqs)){ const r=reqs[rid]
  if(!KEEP.has(r.type)) continue
  if(NOISE.some(x=>r.url.includes(x))) continue
  cliLog('__JSONL__'+JSON.stringify(r)); n++ }
cliLog('[capture_ego] '+n+' 条 -> $OUT')
EOF

echo "[capture_ego] jsonl 追加完成 -> $OUT" >&2
python3 "$S/to_curl.py" "$SESSION"
