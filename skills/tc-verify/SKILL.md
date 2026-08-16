---
name: tc-verify
description: >
  四步管道第④步：审查收口。机算对账（verify_recon.py 六项：产物/数字独立重算/
  恒红核对/覆盖门复跑/假覆盖/audit_base）+ 干净上下文审查（五项对账），
  verdict 落盘——无 verdict 或 FAIL 不得宣称回归完成。
  Use when: 用户说"审查""收口""verify""回归完成了吗""tc-verify"，或 ③tc-run
  跑完后对账段数字与口径不符、或需要给这轮回归出正式结论。前置：③已产出
  api/ui exec JSON + 报告 HTML。操作细节见 kit 仓库 steps/4-verify/README.md
  —— 本 skill 是触发壳，逻辑以它为准。
---

# tc-verify：审查收口（第④步）

**先读 `<kit根>/steps/4-verify/README.md` 并照做**——壳内要点：

1. `python3 steps/4-verify/verify_recon.py <模块根>`：机算六项，读 findings
2. 派**干净上下文**只读审查（Claude 用 Explore/general-purpose subagent，
   Codex 开新会话）：输入 = `steps/4-verify/PROMPT-审查清单.md` 全文 + 模块根路径，
   唯一可写文件 = verdict 文档
3. 检查 verdict 落盘且结论 ∈ {PASS, PASS-with-notes}；FAIL 则如实上报，不许口头降级
4. 向用户汇报：结论 + findings 裁决 + notes 待办（audit_base 回填等进下轮①②）

## 纪律（硬性）

- 机算 exit 1 的 findings 必须逐条裁决（成立/不成立/需补什么），不许跳过
- flake 判定必须有落盘复跑证据（口头"我重跑过了"不算）
- 审查员与执行者必须是不同上下文——执行会话不得自己给自己出 verdict
- verdict=PASS-with-notes 时，notes 待办要指明进管道哪一步
