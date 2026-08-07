#!/usr/bin/env bash
# 脚手架：为一个「系统/模块」建好标准基线目录（auto/docs 二分布局）+ 种子文件。
# 用法：  bash _toolkit/new-module.sh <系统> <模块>
# 示例：  bash _toolkit/new-module.sh risk warning-handle
#         bash _toolkit/new-module.sh slop app-review
# 幂等：已存在的目录/文件不覆盖。
set -euo pipefail

SYS="${1:-}"; MOD="${2:-}"
if [[ -z "$SYS" || -z "$MOD" ]]; then
  echo "用法: bash _toolkit/new-module.sh <系统> <模块>"; exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"      # api-flows/
BASE="$ROOT/$SYS/$MOD"
DATE="$(date +%F)"

mkdir -p "$BASE"/auto/{api,ui,screenshots/explore,screenshots/ui} \
         "$BASE"/docs/{functional-cases,ui-cases,checklists,reports}
# 空目录占位，便于 git 跟踪
for d in auto/api auto/ui auto/screenshots/explore auto/screenshots/ui \
         docs/functional-cases docs/ui-cases docs/reports; do
  [[ -e "$BASE/$d/.gitkeep" ]] || touch "$BASE/$d/.gitkeep"
done

# ---- _meta.yaml：模块元信息 + 仓库指向（前端预留） ----
if [[ ! -e "$BASE/_meta.yaml" ]]; then
cat > "$BASE/_meta.yaml" <<YAML
# 模块元信息（探索前补全空字段）
system: $SYS
module: $MOD
created: $DATE
env_url: ""                # 测试环境 URL（务必测试环境），如 https://test-xxx.inshopline.com
module_base_path: ""       # 模块页面 URL 前缀，如 /risk-cooperation/cs/$MOD/

repos:                     # 代码仓库指向——用于"用例↔代码覆盖审计"
  backend: ""              #   后端仓库路径（接口用例↔后端分支审计），如 ~/Documents/project_code/go/src/armor-smart-platform
  backend_branch: master
  frontend: ""             #   ★预留：后续 git 前端代码后填此处（UI用例↔前端覆盖审计用）
  frontend_branch: ""

notes: |
  三桶信任模型：🟢机器判定 / 🟡DB兜底(SQL人工) / 🔴纯人工。
  两段式断言：assert(🟢) + db_check(🟡, runner忽略) + skip_note(🔴)。详见 api-flows/README.md。
YAML
fi

# ---- 人工校验清单模板 ----
if [[ ! -e "$BASE/docs/checklists/人工校验清单.md" ]]; then
cat > "$BASE/docs/checklists/人工校验清单.md" <<'MD'
# <模块> · 人工校验清单

> 由 auto/api/*.yaml 的 db_check(🟡) + skip_note(🔴) 生成/维护。runner 不碰这两桶，必须人工。

## 🟡 DB 校验清单（接口 SUCCESS≠数据对，SQL 人工核）
（脚本从 flow yaml 的 db_check 抽取后填入）

## 🔴 人工覆盖清单（按 Tier）
### Tier 1 —— 架构性做不了（文件上传/并发/跨系统副作用）
### Tier 2 —— 需第二个账号（越权/权限门）
### Tier 3 —— 补个前置值就能自动跑
MD
fi

# ---- reports 预留说明（含前端审计位） ----
if [[ ! -e "$BASE/docs/reports/_README.md" ]]; then
cat > "$BASE/docs/reports/_README.md" <<'MD'
# reports 目录约定

- `接口用例-代码分支覆盖审计-<日期>.md`   —— 后端 controller/service 分支 ↔ 接口用例（backend repo）
- `UI用例-前端代码覆盖审计-<日期>.md`     —— ★预留：git 前端代码后，前端组件/路由/交互 ↔ UI 用例
- `*-回归报告-<日期>.html`                —— 接口/UI 执行报告（带日期为正式版）
MD
fi

echo "✅ 已创建基线骨架：$BASE"
echo "   auto/ (api,ui,screenshots)  docs/ (functional-cases,ui-cases,checklists,reports)  _meta.yaml"
echo
echo "下一步："
echo "  1. 填 _meta.yaml 的 env_url / module_base_path / repos.backend"
echo "  2. 探索：调 api-flow-recorder（探索 ${SYS}/${MOD} ，产出功能地图.md + auto/api/flow.yaml）"
echo "  3. 用例：p2-test-case-generator → p3-ui-test-case-generator → p4 执行"
echo "  4. 信任层：后端代码审计补负向 → 两段式断言 → 生成人工校验清单"
echo "  5. （后续）git 前端代码后：填 repos.frontend，补 UI 场景 + 前端覆盖审计"
