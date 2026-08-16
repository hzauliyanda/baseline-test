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

## 第①步：tc-explore —— 双源探索建基线

**前置**：前后端仓本地路径 + 系统 URL + ego-browser 已登录目标系统

**跑法（四步，详见 `steps/1-explore/README.md`）**
```bash
new-module.sh <模块根> --backend <后端仓> --frontend <前端仓> --title <中文名>
#   脚手架：骨架 + baseline.yaml（audit_base=分支@HEAD 自动填）+ ③模板五件套
python3 steps/1-explore/scan_repos.py <模块根> --api-prefix /mapi/<模块> --frontend-key <关键词>
#   双源扫描 → explore/ 三份 draft（endpoint/枚举维度/前端路由 全集）
# 然后：ego 页面遍历（capture_ego.sh goto/drain 抓接口+字典API）→ 圈选合成
#   功能地图.md（枚举维度表+行为分叉列）/ baseline.yaml 核对 / flow.yaml 初版
```

**完成标志**：baseline.yaml 无⏳实值（audit_base 已锁 commit）+ 功能地图含枚举维度表
（维度×取值×code ref×行为分叉?，扫描器与字典 API 差异已下结论）+ flow.yaml 主链路
初版（断言全标 ⏳）+ explore/ 三份 draft 在仓。

**注意**：扫描器是全集（实测 168 维度/3443 值），圈选必须显式——不相关的记
「排除」，不许静默丢；这正是②枚举对账的锚。

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

## 第④步：tc-verify —— 审查收口

**前置（缺任何一项先回③）**
- ③的三个产物齐：api-exec-result.json / ui-ego-exec-result.json / 报告 HTML

**跑法（两层）**
```bash
# 1) 机算六项：产物齐全 / 数字独立重算vs报告 / 恒红核对 / 覆盖门复跑 / 假覆盖 / audit_base
python3 steps/4-verify/verify_recon.py <模块根目录>
#    → docs/reports/verify-recon-<date>.json；exit 1 时 findings 交第 2 层裁决

# 2) 干净上下文审查（五项对账：数字/三桶纪律/断言真实性/覆盖抽查/SKIP·FAIL理由）
#    Claude：派只读 subagent，输入 = steps/4-verify/PROMPT-审查清单.md + 模块根路径
#    Codex ：开新会话贴同样内容；verdict 由审查者落盘
```

**完成标志**：`docs/reports/verify-<date>.md` 落盘且结论 ≠ FAIL。
PASS-with-notes 的待办（如 audit_base 回填）指明进下轮 ①或②。

**注意**：执行会话不得自己给自己出 verdict——审查者必须干净上下文；
flake 判定必须有落盘复跑证据。

---

## 回填循环（管道是螺旋的，不是直线）

「探索一次就把用例补全」不会发生——遗漏是常态，设计上靠三层循环消化，
每层都有**机算的「还缺什么」清单**，重复执行不需要人肉记：

| 层 | 触发 | 动作 | 机算件 |
|---|---|---|---|
| ①②内循环（最频繁） | check_coverage exit 1 | 照缺口清单补用例/写 exempt → 重跑门，直到 exit 0 | `check_coverage.py`（缺值/缺 endpoint/假覆盖/悬空引用全列名） |
| ②首跑回填 | ③首跑落盘了真实响应 | ⏳待首跑回填断言 → 锁死 equals；跑出的意外行为 → 功能地图回填 → ②补增量用例 | flow yaml 的 ⏳ 标记 + exec JSON 的 actual |
| ③漂移审计（时间维） | 代码持续变更（大回归前/定期） | `scan_repos.py --diff` 重扫对比旧 draft → 新增/消失的 endpoint·枚举值·路由 → 功能地图增删 → ②增量 → 门重跑 | `scan_repos.py --diff` → `explore/audit-<date>.md`，exit 1=有漂移 |

**原则**：
- 产物全是**累加的活文件**，没有一轮是重写——功能地图/coverage/flow 只补 delta；
  coverage 用 YAML 不用文档，就是为了可机算 diff
- ④verdict 的 findings/notes 是回填入口的路标：每条指明进下轮①还是②
- 漂移报告只报增量不动作——回填决定（真需求/内部态/下线）由人+①下结论
