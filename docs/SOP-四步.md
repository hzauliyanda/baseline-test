# SOP：测试基线四步管道（工具无关主文档）

> 本文档是推广版 baseline-test kit 的**主操作手册**，对任何 AI 工具（Claude Code / Codex）同样适用。
> 设计决策见 `SPEC.md`；与本文件冲突时以 SPEC.md 为准。
> Claude Code 用户：可安装 `skills/` 下的薄壳 skill 触发同样流程；不装也行，直接照本文档喊。

## 总览

| 步 | 名字 | 干什么 | 完成标志（不达成不进下一步） |
|---|---|---|---|
| ① | tc-explore 探索建基线 | UI 遍历 + 前后端代码扫描 | `baseline.yaml`（含前后端 git 地址与 audit_base）+ `功能地图.md`（含枚举维度表）+ `flow.yaml` 初版 |
| ② | tc-cases 用例派生 | 功能/UI/API 用例生成 + **覆盖对账补全** | `coverage/*.yaml` 里 `uncovered`/`gaps` 全空（或显式 `exempt` 带理由），`check_coverage.py` 退出码 0 |
| ③ | tc-run 执行回归 | 一键 API+UI 回归 + 报告 | 回归全绿（基线口径，恒红须注明原因），总览 HTML 生成 |
| ④ | tc-verify 审查收口 | 干净上下文对账汇报 vs 产物 | verdict 落盘且非 FAIL |

管道铁律：上一步产物 = 下一步输入；②对着①的枚举表/endpoint 清单补全；③不绿不进④；
④无 verdict 不得宣称回归完成。

## 前置条件（所有步骤通用）

1. `python3 ≥3.9` + `pyyaml`
2. `git`（读代码仓做覆盖对账）
3. 浏览器通道：ego-browser（ego lite）已装且登录目标系统（①探索和③UI 回归都要）
4. 模块目录 = 一份「基线包」（结构见 SPEC.md 第三节），由脚手架或①生成

---

## 第②步：tc-cases —— 用例派生 + 覆盖对账

**输入（缺任何一项先回①）**
- `baseline.yaml`：`repos.*.url` 非空、`audit_base` 已填
- `功能地图.md`：含「枚举维度表」节（维度 × 取值 × code ref × 行为分叉?）

**产出**
- `docs/functional-cases/<模块>-功能测试用例.md`（P0/P1/P2 分级，TC-ID 编号）
- `auto/api/flow*.yaml`（两段式断言，见 SPEC.md 第六节）
- `docs/ui-cases/<模块>-UI测试用例.md` + UI 场景（S 编号）+ `traceability.json`（S↔TC）
- `coverage/api-coverage.yaml` + `coverage/ui-coverage.yaml`（schema 见 `steps/schema/`）
- `docs/checklists/<模块>-人工校验清单.md`（🟡SQL + 🔴人工项）

**流程**

1. **功能用例**：从功能地图逐页面/交互派生，P0（主链路/资损）P1（常用分支）P2（边界/权限变体）分级，每条标 TC-ID 与功能地图出处。
2. **API 用例**：
   - 每个 endpoint 至少 1 条正向（对齐 coverage endpoints 清单）
   - 负向/边界：必填缺失、非法枚举值、越权、重复操作
   - **枚举规则**：每个枚举值至少 1 条正向真实走过；功能地图标「行为分叉=是」的维度才加组合
   - 断言两段式：`assert`🟢只放接口层能判死的（期望值标 ✅实跑确认 / ⏳待回填）；`db_check`🟡真表 SQL；`skip_note`🔴进人工清单
3. **UI 用例/场景**：每页面 × 每交互至少 1 场景（对齐 coverage pages/interactions）；枚举值=弹窗/控件走查至少各 1 条；状态机每个可达状态至少被 1 条场景到达或显式 exempt。
4. **覆盖对账（机算放行门）**：
   ```bash
   python3 steps/2-cases/check_coverage.py <模块根目录>
   ```
   退出码 0 = 放行；非 0 = 缺口清单在输出里，补用例或写 exempt（带理由）后重跑。
5. **人工清单**：把所有 skip_note/manual 汇总成清单（🔴项写明手动怎么做、期望什么）。

**诚实纪律**
- 期望值没见过真实响应 → 只能写 ⏳ 待回填断言，不许伪装成已验证
- 覆盖不了的写 exempt + 理由（verify 会逐条过），禁止静默缺口
- 「未覆盖清单」和「已覆盖」同等重要，都是交付物

---

## 第①步：tc-explore（建设中）

双源探索（ego 页面遍历 + 前后端代码扫描）+ 枚举维度表 + baseline.yaml 落盘。设计见 SPEC.md，实现在 `steps/1-explore/`（待建）。

## 第③步：tc-run —— 执行回归 + 完整报告

**前置（缺任何一项先回②）**
- `coverage/*.yaml` 已过 `check_coverage.py` 放行（exit 0）
- 模块根已装配 `steps/3-run/templates/` 五件套（装配表见 `steps/3-run/README.md`）

**跑法**
```bash
python3 run_regression.py --dry-run    # 先全量预检（ego/flow/场景/文件齐全性）
python3 run_regression.py              # 全量：API → UI → 报告 → 对账
```

**完成标志**：三个产物齐（api-exec-result.json / ui-ego-exec-result.json / 总览 HTML），
对账打印的实际数字与 `baseline.yaml` 基线口径一致（恒红须是口径里注明的那几个）。
**全绿判定不在这一步**——数字与口径不符、或口径本身要过期，都交给 ④tc-verify 审查。

**注意**：`--dry-run` 与全量跑之间不要改代码；报告 HTML 单文件离线可发，
内嵌截图与断言明细，是 ④审查的对账证据源。

## 第④步：tc-verify（建设中）

干净上下文 subagent 五项对账（数字/三桶纪律/断言抽查/覆盖对账/篡改检测）。实现在 `steps/4-verify/`（待建）。
