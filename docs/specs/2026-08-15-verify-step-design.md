# ⑩执行审查（verify）设计文档

- 日期：2026-08-15
- 状态：待用户审阅
- 归属：测试开发 Agent 全链路体系（执行 → **verify⑩** → baseline-sync⑨）
- 方案：A（纯 subagent 审查，干净上下文 + 固定 checklist；确定性问题靠现有脚本门禁，不新增审计脚本）

## 1. 问题与目标

全链路回归的执行段已经是确定性脚本（regression_runner.py / TS Playwright / gen_report.py），
但**"跑完之后"没有任何 Sensor**：主 agent 汇报结果时的上下文已被整轮执行污染（希望结果是绿的），
可能出现虚标完成、🟡 偷偷标绿、断言语义漂移、覆盖静默缩水、执行中改断言重试到绿等问题。

verify 补的是后置控制（Sensors）：**用干净上下文的只读 subagent，拿执行器落盘的原始产物，
对账主 agent 的汇报与事实是否一致**。

目标用户不止本人——skill 将推广给其他人使用，约束必须跟着 skill 分发走，
不依赖任何人的个人 memory 或记性。

## 2. 非目标

- 不做执行中实时监视（执行段是脚本，无决策可盯；中途篡改转化为事后 git diff 检测）
- 不做确定性审计脚本（对账 subagent 顺手完成；避免"答不出补哪个短板"的过度工程）
- 不外接第二个大模型（主要矛盾是上下文污染而非模型偏见）
- 不改 baseline-sync⑨ 已有的"用例↔结果映射异常清单"（那是基线层，verify 在其上游）
- Hook 系统强制（Stop hook）本期不做，留作后续可选加固

## 3. 架构与组件

```
回归执行（脚本，不改）
   ↓ 产物：auto/*-exec-result.json、auto/ui-pw-result.json、docs/reports/*.html、git 工作区
主 agent 按 regression-runner / ui-run SKILL.md 末步指令派 verify subagent
   ↓ Agent 工具（Explore 类型 = 只读，有 Bash/Read，无 Write/Edit）
verify subagent（干净上下文）
   读 JSON 产物 + 功能地图 + HTML 报告 + git diff → 按 checklist 审查 → 返回 verdict 文本
   ↓
主 agent 落盘 verdict 到 docs/reports/verify-<日期>.md，消化后再宣称"完成"
   ↓（verdict 为 PASS / PASS-with-notes）
baseline-sync⑨ 正常回写（消费 verdict 作为迭代报告输入之一）
```

新增文件（2 个）：

| 文件 | 职责 |
|---|---|
| `~/.claude/skills/verify/SKILL.md` | 触发条件（"跑完回归""审查这轮结果"自动命中）+ 派发 subagent 的指令模板 + verdict 落盘规则 |
| `~/.claude/skills/verify/references/checklist.md` | 审查清单全文（即 subagent 提示词正文）。改清单只改这一个文件 |

改动现有 skill（2 个，各加流程末步一段）：

- `regression-runner/SKILL.md`：报告生成后必须派 verify；未过 verdict 不得宣称完成、不得进入 baseline-sync
- `ui-run/SKILL.md`：同上

关键设计点：

1. **审查者用 Explore（只读）类型 subagent**——有 Bash/Read 能真抽查（重读 JSON、跑 git diff、
   用 python 解析），但物理上无 Write/Edit，不可能顺手改产物。verdict 文件由主 agent 落盘。
2. **审查输入是执行器落盘的原始 JSON**，不是主 agent 的转述——数据保真。
3. **执行器无关**：只吃 `auto/*-exec-result.json` 等目录约定产物，不关心是谁生成的
   （不受第三执行器 api_runner.py 合并悬案影响）。

## 4. 五项审查清单（checklist.md 骨架）

| # | 检查 | 怎么做 | 抓什么 |
|---|---|---|---|
| 1 | 对账 | 主 agent 总结里的 pass/fail/skip 数字 vs `api-exec-result.json` / `ui-exec-result.json` 逐线对 | 虚标完成 |
| 2 | 三桶纪律 | 所有 `db_check` 步骤状态必须停在"待人工"；每个 skip 必须有理由且理由读得通 | 🟡 偷偷标绿、无理由跳过 |
| 3 | 断言抽查 | 随机抽 2-3 条 PASS + 全部 FAIL，回读 `resp_preview` 人工重判断言 | 断言语义漂移、误判 |
| 4 | 覆盖对账 | 本轮实跑的 flow/场景清单 vs `功能地图.md` 声明的场景全集 | 静默缩水 |
| 5 | 篡改检测 | `git diff` 本轮执行的 flow.yaml / 用例文件 vs HEAD：断言放宽、步骤注释 → 🔴 | 执行中改断言重试到绿 |

每项产出结构化结论，沿用三桶话术：🔴 实锤 / 🟡 存疑待人工 / 🟢 过。
结论必须引用具体证据（JSON 字段、diff hunk、报告数字），禁止"看起来没问题"式表述。

## 5. verdict 形态与失败处理

- 路径：verdict 落在**本轮报告所在目录**——api-flows 模块为 `<模块>/docs/reports/verify-<日期>.md`，ui-run（testcase-baseline）为 `reports/<日期>/verify-<日期>.md`；原则：baseline-sync 到它读本轮报告的地方就能找到 verdict
- 顶部硬结论三选一：`PASS` / `PASS-with-notes` / `FAIL`，其下按五项列证据
- FAIL：主 agent 必须先处理（解释清楚或修复重跑）才能宣称"完成"
- 上游纪律（写在 verify + regression-runner + ui-run 三个 SKILL.md 里）：
  **无 verdict 或 verdict=FAIL 的轮次，baseline-sync⑨ 拒绝消费**
- baseline-sync⑨ 的迭代报告增加一行"本轮审查结论"，数据来自 verdict 文件

## 6. 降级与错误处理

| 情形 | 行为 |
|---|---|
| exec-result JSON 不存在 | verdict 直接 FAIL："无本轮产物" |
| JSON 的 mtime 早于 HTML 报告（旧数据） | 同上，FAIL："产物过期" |
| 功能地图.md 不存在 | 跳过第 4 项，verdict 中显式标注"覆盖对账未执行"，不静默 |
| 主 agent 无法派 subagent（环境异常） | 明确告知用户"本轮未审查"，不得默默跳过 |

## 7. 通用性与推广

- 只依赖 new-module.sh 脚手架的目录约定：`auto/*-exec-result.json`、`功能地图.md`、`docs/reports/`
- verify 与 regression-runner / ui-run 同包分发；其他用户说"跑回归"时，审查随流程自动发生，
  用户无需知道 verify 存在，也无需任何个人配置
- 用户也可显式 `/verify` 或说"审查这轮回归"单独调用

## 8. 验收方式（金标准埋雷）

在风控普通工单模块人工埋三个错，验证 verify 全部抓得住：

1. 把汇报里的 FAIL 数说少一个 → 第 1 项对账应抓到
2. 手动把一个 db_check 步骤标成已通过 → 第 2 项三桶纪律应抓到
3. 注释掉 flow.yaml 里一个步骤再跑 → 第 4/5 项覆盖+篡改应抓到

三雷全中 → 上线；抓漏 → 修 checklist 后重验。

## 9. 后续可选（本期不做）

- Stop hook 系统强制（settings.json 层拦截"未 verify 就宣称完成"）
- verify_audit.py 确定性脚本（若 checklist 中某项被证明 subagent 判不稳，再下沉为代码）
- 外接第二个大模型复核 L2（仅当同模型抽查被证明有系统性盲区）
