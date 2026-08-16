#!/usr/bin/env bash
# new-module.sh —— 新模块基线包脚手架（tc-explore 第 0 动作）
#
# 用法：
#   new-module.sh <模块根目录> [--backend <本地后端仓>] [--frontend <本地前端仓>] [--title <中文名>]
#
# 做五件事：
#   1. 建目录骨架（docs/{functional-cases,ui-cases,checklists,reports} auto/{api,ui,screenshots/ui} coverage explore）
#   2. baseline.yaml 从 schema 模板生成；给了本地仓则自动填 url（origin）与 audit_base（当前分支@HEAD）
#   3. 拷 ③tc-run 五件套模板到对应位置（ego_scenarios.py 拷成骨架，场景自己写）
#   4. coverage 两份模板就位
#   5. .gitignore：抓包/截图/每轮重生成的报告与 exec JSON 不入库（模块仓只沉淀资产）
#
# ego_scenarios.py 是普通工单参考实现，含真实场景代码——拷过去后必须整个换成自己模块的。
set -euo pipefail
KIT="$(cd "$(dirname "$0")/../.." && pwd)"

ROOT=""; BACKEND=""; FRONTEND=""; TITLE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --backend) BACKEND="$2"; shift 2 ;;
    --frontend) FRONTEND="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    *) ROOT="$1"; shift ;;
  esac
done
[ -n "$ROOT" ] || { echo "用法: new-module.sh <模块根目录> [--backend 仓] [--frontend 仓] [--title 中文名]"; exit 2; }
MODULE="$(basename "$ROOT")"
TITLE="${TITLE:-$MODULE}"

if [ -e "$ROOT/baseline.yaml" ]; then
  echo "⚠️  $ROOT/baseline.yaml 已存在——脚手架只建一次，不覆盖（要重来先手动清）" >&2
  exit 1
fi
mkdir -p "$ROOT"/docs/{functional-cases,ui-cases,checklists,reports} \
         "$ROOT"/auto/{api,ui,screenshots/ui} "$ROOT"/coverage "$ROOT"/explore

# ── baseline.yaml：schema 模板 + 能自动填的自动填 ──────────────────
BL_TMP="$(mktemp)"
sed -e "s|^module: .*|module: $MODULE|" \
    -e "s|^title: .*|title: $TITLE|" \
    -e "s|^updated: .*|updated: $(date +%F)|" "$KIT/steps/schema/baseline.yaml" > "$BL_TMP"
fill_repo() {  # $1=backend|frontend $2=本地仓
  local url br hash
  url="$(git -C "$2" remote get-url origin 2>/dev/null || echo "")"
  br="$(git -C "$2" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
  hash="$(git -C "$2" rev-parse --short HEAD 2>/dev/null || echo "待回填")"
  python3 - "$BL_TMP" "$1" "$2" "$url" "$br@$hash" <<'PY'
import sys, yaml
path, side, local, url, audit = sys.argv[1:6]
d = yaml.safe_load(open(path, encoding="utf-8"))
repos = d.setdefault("repos", {}).setdefault(side, {})
if url:   repos["url"] = url
repos["local"] = local
repos["audit_base"] = audit
yaml.safe_dump(d, open(path, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
PY
}
[ -n "$BACKEND" ]  && fill_repo backend  "$BACKEND"
[ -n "$FRONTEND" ] && fill_repo frontend "$FRONTEND"
mv "$BL_TMP" "$ROOT/baseline.yaml"

# ── ③ 模板五件套 + coverage 模板 ──────────────────────────────────
cp "$KIT/steps/3-run/templates/run_regression.py" "$ROOT/"
cp "$KIT/steps/3-run/templates/api_runner.py"     "$ROOT/auto/api/"
cp "$KIT/steps/3-run/templates/ego_ui_runner.py"  "$ROOT/auto/ui/"
cp "$KIT/steps/3-run/templates/ego_scenarios.py"  "$ROOT/auto/ui/"   # ⚠️ 参考实现，必须整个换成自己模块的场景
cp "$KIT/steps/3-run/templates/gen_report.py"     "$ROOT/"
cp "$KIT/steps/3-run/templates/package.json"      "$ROOT/"
cp "$KIT/steps/schema/api-coverage.yaml" "$ROOT/coverage/"
cp "$KIT/steps/schema/ui-coverage.yaml"  "$ROOT/coverage/"

# ── .gitignore：不入库的都是「每轮重新生成」或「含敏感信息」──────────
# capture/ 含登录 cookie 的抓包；报告 HTML 内嵌截图（~9MB/份）；exec JSON 每轮覆盖
cat > "$ROOT/.gitignore" <<'EOF'
# 抓包含登录态/cookie，绝不入库
capture/
# 截图与执行中间产物（每轮回归重新生成）
auto/screenshots/
auto/api-exec-result.json
auto/ui-ego-exec-result.json
# 报告 HTML 内嵌截图体积大，每轮重新生成；verdict/审查记录（.md/.json）保留入库
docs/reports/*.html
# 其它
__pycache__/
*.pyc
package-lock.json
.DS_Store
EOF

echo "✅ 骨架就位：$ROOT"
echo "   下一步：scan_repos.py $ROOT [--api-prefix ...] [--frontend-key ...]   # 双源扫描"
[ -n "$BACKEND" ] || [ -n "$FRONTEND" ] && grep -A2 "repos:" "$ROOT/baseline.yaml" | head -8
