# AI-TEST / api-flows —— 多系统测试基线目录规范 + playbook

> 每个**系统**（risk 风控、slop 开放平台…）单独维护一套自包含目录。根目录只放跨系统共享基建。
> **标杆样板**：`risk/normal-work-order/`（满配 + 已迁 auto/docs 新布局）。

## 顶层布局

```
api-flows/
├── _toolkit/          # ★ 全局共享代码（所有系统引用，只此一份）
│   ├── new-module.sh          # ★ 脚手架：一键建模块骨架
│   ├── cdp_type.py            # antd 受控输入助手
│   ├── upload_cases.py        # octopuses 用例上传（内含硬编码 flow 路径清单，移文件后须同步改）
│   └── 接口测试全链路方法论.md
├── .chrome-profile/   # 共享持久化登录态（skill 硬编码，勿移）
├── .chrome-port       # 共享调试端口
├── capture/           # 共享抓包（session 命名 <system>-<module>-<日期>）
├── README.md          # ← 本文件
├── risk/              # 系统①：风控（自包含）
└── slop/ …            # 系统②：以后新建，同构
```

## 模块内部规范（新标准：auto/docs 二分）

```
<system>/<module>/
├── _meta.yaml            # 模块元信息 + 仓库指向（backend/frontend）
├── 功能地图.md           # 探索总源（含 action→api 映射），喂 p2/p3
├── explore-report.md
├── auto/                 # 🤖 机器/AI 执行
│   ├── api/              # flow*.yaml（接口用例，runner 跑）
│   ├── ui/              # ui_runner.py + s*.yaml + traceability（UI 自动化）
│   ├── screenshots/     # explore/ + ui/
│   └── _created.yaml     # 实体台账（清理清单）
└── docs/                 # 👀 人读 / 人工执行
    ├── functional-cases/ # 功能用例 md/xlsx
    ├── ui-cases/         # UI 用例文档 md
    ├── checklists/       # 人工校验清单（🟡DB SQL + 🔴Tier）
    └── reports/          # 代码审计 + 执行报告
```

> **迁移状态**：`normal-work-order` 已是 auto/docs；`punish`/`complaint`/`threathunter` 仍是旧扁平布局（flow.yaml 等在模块根），后续按需迁移。**新建模块一律用 auto/docs**（`new-module.sh` 直接建好）。

## 铁律

1. **截图只进 `<module>/auto/screenshots/`**（explore/ 探索 + ui/ 执行），绝不倒在 `api-flows/` 根。
2. **移动 flow/功能地图 后，同步改掉硬编码引用**：`_toolkit/upload_cases.py` 有一张 `FLOWS` 绝对路径表；runner.py / api-flow-recorder 是路径当参数传、不受影响。（教训：8/2 迁 normal-work-order 时漏改这张表导致 upload 断，已修。）
3. 报告里图片引用一律相对路径 `../../auto/screenshots/xxx.png`（从 docs/reports/ 起算）。
4. 新系统/模块照 `new-module.sh` 建；共享代码统一走 `_toolkit/`，不各自复制。
5. 三桶信任模型 + 两段式断言是**每个模块的必做项**（见下），不是可选。
6. **功能地图是唯一、活的、最终完整真源**：功能/UI/接口用例全从它派生。凡发现新逻辑——不止 CDP 探索，**代码审计/探索挖出的新接口、新守卫分支、新枚举、新状态流转，也必须回填功能地图**（不能只补进 flow yaml 就算完）。回填标出处、推断标 ⏳。终态：覆盖 页面结构 + action→api + 分支级场景，据以判断"还差哪些场景"。

---

## Playbook：建一套可信基线的流程

### 0. 起手建骨架
```bash
bash _toolkit/new-module.sh <系统> <模块>      # 例：risk warning-handle
```
建好 auto/docs 空目录 + `_meta.yaml` + 清单模板。**先填 `_meta.yaml`**：`env_url`（测试环境）、`module_base_path`、`repos.backend`。

> ⚠️ **执行分两种，别混**：**冲烟自测**（边生成边跑，验用例可用 + 回填 ⏳）要**早**；**正式回归 + 出正式报告**要**晚**（用例补全后一次到位，别在不成熟用例集上出报告——否则重演"30步/136步两份报告打架"）。

### 1. 生成用例（现成 skill）
| 步 | 干啥 | skill | 产出 |
|---|---|---|---|
| 1 | CDP 探索，边探边写功能地图 + 抓接口串 flow.yaml | `api-flow-recorder` | 功能地图.md、auto/api/flow.yaml、_created.yaml |
| 2 | 功能地图 → 功能测试用例（TC-ID） | `p2-test-case-generator` | docs/functional-cases/ |
| 3 | 功能地图+功能用例 → UI 自动化用例 | `p3-ui-test-case-generator` | auto/ui/s*.yaml + traceability |

> 一键串完 1→3：`ai-web-test-pipeline`（断点续跑）。skill 默认吐扁平布局，跑完收口到 auto/docs。

### 2. 冲烟自测（早，不出正式报告）
用 `p4-browser-test-runner-devtools` / `runner.py` 把生成的用例跑一遍，只为：**验选择器/登录/接口可达** + **回填两段式断言的 ⏳**（分页路径、负向真实拒绝码等只能靠真跑锁死）。这一步是开发期反馈，不是里程碑。

### 3. 后端信任层 →【里程碑① 后端正式回归】
1. **接口↔后端代码分支覆盖审计**：拉 `_meta.yaml.repos.backend` 的 controller/service，逐个 if/switch 守卫对照 flow，产出 `docs/reports/接口用例-代码分支覆盖审计-<日期>.md`，据空白补 `flow-negative/supplement/paths`。**审计挖出的新逻辑同时回填功能地图**（铁律6）。
2. **两段式断言**（每 case）：`assert:`🟢（runner 判死，⚠️不渲染变量只静态串）+ `db_check:`🟡（真表名 SQL，runner 忽略→永不自动过）+ `skip_note:`🔴。出处标 `✅实跑确认`/`⏳待回填`；**读代码推断的码绝不写成硬 equals**。
3. **人工校验清单**：脚本从 yaml 的 db_check/skip_note 抽 → `docs/checklists/`（🟡DB SQL + 🔴Tier1/2/3）。
4. **【里程碑① 正式回归】**：用例补全后跑一次正式回归、出正式报告。三桶收口：🟢机器 + 🟡SQL(人工) + 🔴人工，都过才算真过。
   > **后端别等前端**——后端到此即可独立出正式报告，不被前端阻塞。

### 4. 前端线 →【里程碑② 前端+全量回归】（★git 前端代码后）
后端做完后 UI 侧对称做——**结构已预留**：
1. git 前端仓库后，填 `_meta.yaml.repos.frontend` / `frontend_branch`。
2. **UI 用例↔前端代码覆盖审计**：对照前端路由/组件/交互分支/表单校验，找 UI 没覆盖的场景（弹窗时序、边界态、权限渲染、错误提示…），产出 `docs/reports/UI用例-前端代码覆盖审计-<日期>.md`。**挖出的新逻辑同样回填功能地图**（铁律6）。
3. 补 UI 场景 → 追加 `auto/ui/s*.yaml` + 更新 `traceability.json`（UI 场景 ↔ 功能 TC-ID 追溯不断）。
4. **【里程碑② 正式回归】**：UI 侧同样三桶（🟢断言 元素/文案/跳转 + 🟡数据副作用 SQL + 🔴视觉/时序人工），补完 UI 场景后触发一次全量正式回归。

---

## 模块完整度现状（risk 系统）
| 模块 | 布局 | 功能地图 | 接口用例 | UI 用例 | 人工清单 | 状态 |
|---|---|---|---|---|---|---|
| normal-work-order | **auto/docs** | ✅(全) | ✅ 5 flow/136 case | ✅ 9 场景 | ✅ | **满配（标杆）** |
| punish | 扁平(待迁) | ✅ | ✅ 2 flow | ❌ | ❌ | 半配（缺 UI + 迁移） |
| complaint | 扁平(待迁) | ✅ | ✅ 2 flow | ❌ | ❌ | 半配（缺 UI + 迁移） |
| threathunter | 扁平(待迁) | ✅ | ✅ 1 flow | ❌ | ❌ | 半成品（仅探索） |
