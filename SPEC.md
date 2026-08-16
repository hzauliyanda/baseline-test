# baseline-test 设计定稿（2026-08-16）

> 推广版测试开发全链路工具包。使用者为混用 Claude Code / Codex 的测试同事。
> 本文件是设计决策的唯一真源；实现与它冲突时，要么改实现、要么改这里并留记录。

## 一、目标与形态

- **4 步管道**，每步一个 skill（`tc-` 前缀），顺位执行，上一步产物 = 下一步输入
- **厚核薄壳**：全部逻辑在脚本 + SOP 文档（工具无关），skill 只是 Claude 的触发壳；
  Codex 同事 clone 本仓库后读 `AGENTS.md` → `docs/SOP-四步.md` 干同样的事
- 每步有**硬性完成标志**，不达成不进下一步

## 二、四步管道

| 步 | skill | 里程碑（完成标志） | 产物 |
|---|---|---|---|
| ①探索建基线 | `tc-explore` | 模块全页面摸清 + 前后端代码扫完 | `baseline.yaml`、`功能地图.md`、`flow.yaml`（初版）、枚举维度表 |
| ②用例派生 | `tc-cases` | **覆盖矩阵无裸缺口**（缺值/缺 endpoint 必须显式记录原因） | 功能用例、UI 用例、API 用例（两段式断言）、`coverage/*.yaml`、人工清单 |
| ③执行回归 | `tc-run` | 回归全绿（基线口径，恒红需注明） | `*-exec-result.json`、总览 HTML 报告、截图 |
| ④审查收口 | `tc-verify` | verdict 落盘且非 FAIL | `verify-<日期>.md` |

管道保障「顺位」：② 对着 ① 的枚举表/endpoint 清单补全；③ 不绿不进 ④；
④ 无 verdict 不得宣称回归完成。

## 三、基线包结构（每模块一份，自我完整）

```
<模块>/
├── baseline.yaml            模块元数据：系统入口、前后端 git 地址、审计基准 commit、产物索引、回归基线口径
├── 功能地图.md               活真源（UI 探索 + 前后端代码扫描双源合成，含枚举维度表）
├── docs/functional-cases/   功能用例
├── docs/ui-cases/           UI 用例
├── auto/api/*.yaml          API 用例（两段式断言：assert🟢 + db_check🟡 + skip_note🔴）
├── auto/ui/                 UI 场景 + traceability.json
└── coverage/
    ├── api-coverage.yaml    后端 endpoint/枚举 ↔ API step 对账（可机算）
    └── ui-coverage.yaml     前端页面/交互/枚举 ↔ UI 场景对账（可机算）
```

## 四、覆盖契约（诚实口径）

「API 覆盖后端所有场景 / UI 覆盖前端所有场景」落地为**场景级契约**：

- **承诺**：后端全部对外 endpoint（含负向）各有 API step 或显式 skip_note；
  前端全部页面 × 全部可触发交互（含权限/空态变体）各有 UI 场景或显式未覆盖记录；
  **每个枚举值至少 1 条正向用例真实走过** + 维度级负向
- **不承诺**：代码分支 100% 等价覆盖（那是单测的事）；不默认笛卡尔积，
  仅功能地图标注「行为分叉=是」的维度做组合
- 覆盖不了的进「未覆盖清单」**带原因**，verify 时逐条过——禁止静默缺口

## 五、枚举维度机制（防"只测了一个类型"）

来源三通道：后端枚举常量（Go const/iota）、前端 options（Select/Radio）、字典接口（如 /base/enums）。

1. ①扫描落表 → 功能地图「枚举维度表」（维度 × 取值 × code ref × 行为分叉?）
2. ②生成规则：每值至少 1 正向 + 维度负向；对着表 diff，**缺值 = 完成标志不达成**
3. `coverage/*.yaml` 的 `enums` 节可机算：代码扫出的 values × 用例实际用到 values → 缺值表
4. ④抽查：随机挑一个枚举维度，核矩阵行数 = 代码值数、用例 id 真实存在

## 六、断言严谨性（两段式 + 三桶）

- `assert` 🟢 机器判定：status / $.code / contains / exists；期望值标注出处
  （✅实跑确认可锁死 / ⏳待首跑回填仅代码推断）
- `db_check` 🟡 runner 永不判过，SQL 人工核验（真表名真列名）
- `skip_note` 🔴 runner 跑不了的（跨系统/越权/并发/上传）进人工清单
- UI 断言：每步结构化回读值（非截图自证）+ 截图留痕

## 七、分发

```
baseline-test/
├── SPEC.md / AGENTS.md / CLAUDE.md   # AGENTS.md 与 CLAUDE.md 内容相同：指路 SOP
├── docs/SOP-四步.md                   # 工具无关主文档（Codex 主入口）
├── steps/schema/                      # 三份 schema 模板（本目录，见下）
├── new-module.sh                      # 脚手架（后续）
├── skills/tc-{explore,cases,run,verify}/  # Claude 薄壳（后续）
└── examples/risk-normal-work-order/   # 金标准实例（普通工单真实数据首填）
```

- 执行器纯 Python，不依赖任何 AI 工具
- ego-browser 不打包：对话层工具各人自装，SOP 写前置条件

## 八、明确不推广（砍掉）

impact-analysis（依赖 impact-go 编译，留原作者自用）、baseline-sync⑨闭环沉淀、
octopuses 平台导入（skill 已删）、superpowers 元技能。

## 九、schema 定稿（2026-08-16，本日里程碑）

三份 schema 模板见 `steps/schema/`，金标准实例见 `examples/risk-normal-work-order/`：

- `baseline.yaml`：repos(前后端 url/local/audit_base) + artifacts 索引 + regression 基线口径
- `api-coverage.yaml`：endpoints[]（endpoint/handler/cases/status/note）+ enums{}（values/covered/gaps）
- `ui-coverage.yaml`：pages[]（page/interactions×cases）+ enums{} 同构

status 取值固定四态：`covered` / `skip_note`（带 note）/ `uncovered`（=缺口，②不放行）/ `manual`（🔴人工项）。

## 十、工程顺序与状态

1. ✅ schema 定稿（本文件 + steps/schema + 金标准实例首填）
2. ✅ tc-cases（SOP② + check_coverage.py + skills/tc-cases）
3. ⬜ tc-run
4. ⬜ tc-verify
5. ⬜ tc-explore（最难：api-flow-recorder 的 ego 化 + 双源扫描，最后攻）

git 已接原 remote（github.com/hzauliyanda/baseline-test，HEAD=kit）；旧仓内容三层保险：git 历史 + 本地 baseline-test-old-2026-08-16/ + zip 备份。
