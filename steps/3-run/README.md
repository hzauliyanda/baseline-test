# 第③步 tc-run：执行回归 + 完整报告

## 装配（新模块一次性动作）

从 `templates/` 拷 5 个文件到模块根对应位置：

| 模板 | 拷到 | 改什么 |
|---|---|---|
| `run_regression.py` | `<模块>/run_regression.py` | 不改 |
| `api_runner.py` | `<模块>/auto/api/api_runner.py` | 不改（BASE_URL 自动读 baseline.yaml；`TC_FLOWS` 环境变量可选子集） |
| `ego_ui_runner.py` | `<模块>/auto/ui/ego_ui_runner.py` | 只改头部【模块配置区】5 行 URL |
| `ego_scenarios.py` | `<模块>/auto/ui/ego_scenarios.py` | **整个换成你模块的场景**（本文件是普通工单 22 场景参考实现，含 S2 建单-查回-清理、[EGO] 清扫等范式） |
| `gen_report.py` | `<模块>/gen_report.py` | 不改（模块名/报告路径/清单自动读 baseline.yaml） |
| `package.json` | `<模块>/package.json` | 可选（`npm run regression` 别名） |

## 跑法

```bash
python3 run_regression.py             # 全量：API + UI + 报告
python3 run_regression.py --api-only  # 只 API + 报告
python3 run_regression.py --ui-only   # 只 UI + 报告
python3 run_regression.py --dry-run   # 全量预检不执行（ego/flow/场景/文件齐全性）
```

- 预检失败会给出缺什么、从哪拷；`--dry-run` 做的是**全量**预检
- 跑完打印对账：实际数字 vs `baseline.yaml` 的 `regression.baseline` 口径——
  **全绿判定不在这里**，与口径不符时进 ④tc-verify 审查
- 前置：ego-browser 在 PATH 且已登录目标系统（cookie 自动抓，`RISK_COOKIE`/`TC_BASE_URL` 环境变量可临时覆盖）

## 产物

| 文件 | 说明 |
|---|---|
| `auto/api-exec-result.json` | API 每 step 断言+response（④审查证据） |
| `auto/ui-ego-exec-result.json` | UI 场景/步骤记录 + scenes 聚合 |
| `auto/screenshots/ui/*.png` | UI 每步截图 |
| `docs/reports/<title>-全量回归总览-YYYY-MM-DD.html` | 总览（路径由 baseline.yaml `regression.report` 决定） |

## 已实测（2026-08-16，普通工单真模块）

- dry-run 全量预检 ✅；API-only 真跑 51s → 136/138，2 恒红与基线口径一致 ✅
- UI 全量真跑 407s：22 场景 48 PASS / 1 FAIL / 0 SKIP。唯一 FAIL = S13
  「ego CLI 挂死 >20s」**通道 flake**，单场景复跑 2/2 PASS 确认非功能回归
  ——这正是对账段数字与口径不符时的标准处理路径：先定位（全量 JSON 里查 FAIL 记录）
  → 判性质（flake/回归/口径过期）→ 复跑取证 → 如实记录，**不静默重跑覆盖证据**
- 实测抓出并修复：编排器 ROOT 多剥一层 / 报告路径叠双 / 报告名丢显示名（补 `title` 字段）
