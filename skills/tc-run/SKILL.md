---
name: tc-run
description: >
  四步管道第③步：执行回归 + 生成完整报告。run_regression.py 编排
  API(api_runner) → UI(ego_ui_runner) → 报告(gen_report)，ego-browser 统一通道，
  末尾对账实际数字 vs baseline.yaml 基线口径。
  Use when: 用户说"跑回归""执行回归""全量回归""tc-run""生成报告"，或 ②tc-cases
  放行后顺位进入。前置：check_coverage.py 已放行 + steps/3-run/templates 五件套已装配。
  装配表与产物说明见 kit 仓库 steps/3-run/README.md —— 本 skill 是触发壳，逻辑以它为准。
---

# tc-run：执行回归 + 完整报告（第③步）

**先读 `<kit根>/steps/3-run/README.md` 并照做**——壳内要点：

1. 未装配五件套 → 按 README 装配表拷模板（ego_scenarios.py 必须是该模块自己的场景）
2. `python3 run_regression.py --dry-run` 全量预检，缺什么补什么
3. `python3 run_regression.py` 全量跑（不要中途改代码）
4. 看对账段：实际 vs baseline.yaml 口径；不符时**不要自行改口径**，带数字进 ④tc-verify
5. 完成后告知用户报告路径，提醒 ④tc-verify 是收口（无 verdict 不得宣称完成）

## 纪律（硬性）

- 恒红只有 baseline.yaml 口径里注明的才允许存在，新出现的红 = 回归，先查再报
- 跑挂单段（API 或 UI）不静默跳过——编排器已跑完的段保留产物，如实报告哪段没跑
- 报告数字一律以落盘 JSON 为准，不凭终端滚动输出转述
