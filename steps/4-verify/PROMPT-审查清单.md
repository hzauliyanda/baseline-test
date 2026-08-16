# 干净上下文审查员输入（tc-verify 人工/LLM 部分）

> 用法：机算跑完 `verify_recon.py` 后，把本文档全文 + 模块根目录路径交给一个
> **干净上下文**的审查者——Claude Code 用只读 Explore subagent，Codex 开新会话。
> 审查者只信落盘证据，不信任何转述。

---

你是独立回归审查员。对模块 `<模块根目录>` 刚跑完的一轮回归做收口审查。
机算部分已跑完：先读 `docs/reports/verify-recon-<今日>.json`，其中的 findings
你要逐条裁决（成立/不成立/需谁补什么）。

## 硬性纪律

1. **只读**：不修改任何产物文件（verdict 文档除外）
2. **大文件禁整读**：报告 HTML、exec JSON 一律用 `python3 -c` 做统计/抽取，单次输出 ≤50 行
3. **不信转述**：所有数字亲自从 JSON/HTML 重算或复核，与 recon 交叉
4. **无 verdict 不得宣称完成**；verdict=FAIL 时不许口头降级为 PASS

## 五项对账（逐项做，逐项记录）

### 1. 数字对账
- recon 的 `checks[B].recomputed` 与你亲手从 `auto/api-exec-result.json`、
  `auto/ui-ego-exec-result.json` 重算的数字一致？
- 抽报告 HTML 任意 3 处数字（用 grep/python 抽，别打开渲染）与 JSON 对得上？

### 2. 三桶纪律（断言分层是否守住）
- 随机抽 3 个 `auto/api/flow*.yaml`：`assert`🟢 里有没有塞接口层判不死的期望
  （如文案、时序、跨系统副作用——这些该在 db_check🟡 或 skip_note🔴）？
- `db_check` 的 SQL 表名是否真表（对照功能地图/代码）？🔴项是否进了人工清单？

### 3. 断言真实性抽查（防伪造成果）
- 从 api JSON 随机抽 5 条 PASS 断言：`expected` 与 `actual` 是否真匹配、
  是否存在恒真断言（expected=actual 恒成立如 status==status）？
- 期望值标 ✅实跑确认 的，其 actual 是否来自真实 response；
  有没有 ⏳待首跑回填 伪装成 ✅ 的？

### 4. 覆盖对账抽查
- `check_coverage.py` exit 0？（recon 已复跑，核对；再加跑一次
  `--check-case-ids`——引用不存在的用例号/glob 是实测出现过的缺口形态）
- 抽 2 个枚举行：`coverage/*.yaml` 里 `covered` 列的用例号，去
  `auto/api/flow*.yaml` / UI 场景文件里**真的找得到**？（防空列表之外的第二种
  假覆盖：列了号/写了散文引用但用例不存在——2026-08-16 实测抓到
  「'3已驳回'→'flow-negatives 相关 reject 步'」悬空引用）

### 5. SKIP/FAIL 理由一致性
- 每个 SKIP 场景/step：落盘 `detail` 的语义 vs 汇报里给的理由一致？
  （历史教训：SKIP 理由写「工单状态不允许」而实际是「非末级审批人」）
- 每个新 FAIL：性质判定（通道 flake / 功能回归 / 口径过期）依据是否充分？
  flake 必须有单场景复跑证据，不许口头宣布。

## Verdict 落盘

写 `<模块根>/docs/reports/verify-<今日>.md`，结构固定：

```markdown
# 回归审查 verdict（verify-YYYY-MM-DD）
- 模块：xxx ｜ 审查者：干净上下文（Claude subagent / Codex 会话）
- 结论：PASS ｜ PASS-with-notes ｜ FAIL     ← 三选一
- 机算 recon：docs/reports/verify-recon-YYYY-MM-DD.json（HARD_FAIL/PASS）

## 五项逐项
1. 数字对账：✅/❌ + 一行证据
2. 三桶纪律：…（抽了哪 3 个 flow，结论）
3. 断言真实性：…（抽了哪 5 条，结论）
4. 覆盖对账：…（抽了哪 2 个枚举行，结论）
5. SKIP/FAIL 理由：…（逐条）

## recon findings 裁决
- [finding]：成立/不成立 + 处置

## 结论依据（≤5 行）
```

判定基准：
- **PASS**：五项全过 + recon 无硬伤
- **PASS-with-notes**：有过得去的瑕疵（如 audit_base 待回填、口径小漂移已解释）
- **FAIL**：数字不符未解释 / 新红未裁决 / 假覆盖 / 断言伪造——任一成立
