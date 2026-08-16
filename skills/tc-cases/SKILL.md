---
name: tc-cases
description: >
  四步管道第②步：用例派生 + 覆盖对账。从功能地图生成功能用例(P0-P2/TC-ID)、
  API 用例(两段式断言)、UI 场景(S↔TC 追溯)、人工清单，并维护 coverage/*.yaml
  覆盖矩阵；用 check_coverage.py 机算放行（缺值/缺口不放行）。
  Use when: 用户说"生成用例""补用例""覆盖对账""补缺口"“tc-cases”，或 ①tc-explore
  完成后顺位进入。前置：baseline.yaml + 功能地图.md（含枚举维度表），缺了先回①。
  完整流程见 kit 仓库 docs/SOP-四步.md 第②步 —— 本 skill 是触发壳，逻辑以 SOP 为准。
---

# tc-cases：用例派生 + 覆盖对账（第②步）

**先读 `<kit根>/docs/SOP-四步.md` 第②节并严格照做**——本文件只记壳内要点：

1. 前置检查：`baseline.yaml`（repos.url + audit_base 已填）+ `功能地图.md`（含枚举维度表）。缺 → 告知用户回 ①tc-explore，不要硬跑。
2. 按 SOP 生成四类产物（功能用例 / flow*.yaml / UI 场景+traceability / 人工清单）。
3. 同步维护 `coverage/api-coverage.yaml` + `ui-coverage.yaml`（schema 见 `steps/schema/`）。
4. 跑放行门：
   ```bash
   python3 <kit根>/steps/2-cases/check_coverage.py <模块根目录> --check-case-ids
   ```
   退出码 1 = 有缺口：补用例，或与用户确认后写 exempt（必须带理由）。**不许为了放行把缺口标成 covered**。
5. 放行后告知用户可进 ③tc-run。

## 纪律（硬性）

- 期望值没见过真实响应 → 断言只能 ⏳待回填，不许伪装已验证
- covered 但用例列表空 = 假覆盖，check 脚本会抓，别写
- 每个枚举值至少 1 条正向（功能地图标"行为分叉"的维度才加组合）
