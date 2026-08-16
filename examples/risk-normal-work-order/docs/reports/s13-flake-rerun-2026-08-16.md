# S13 FAIL 复跑取证（2026-08-16）

## 现象

全量 UI 回归（407s，22 场景）中 S13「审批与运营地区配置」唯一 FAIL：

> ego 通道挂死：ego CLI 挂死（>20s），已 killpg 恢复

（出处：`auto/ui-ego-exec-result.json` → records[scene=S13].detail）

## 复跑

- 命令：`python3 ego_ui_runner.py S13`（全量跑完后 4 分钟内，同机同环境）
- 结果：**2 PASS / 0 FAIL / 0 SKIP，耗时 12s**
- 两步断言均真过：单块运营地区 disabled=True；审批上限 toast×3

## 处置

- 全量 JSON **保留原始 FAIL 记录**（先备份 → 单跑 → 恢复），未用复跑结果覆盖全量证据
- 判定：**ego CLI 通道 flake**，非功能回归；S13 功能断言在复跑中全部通过
- 本文件 = 该判定的落盘证据，供 ④tc-verify 审查员裁决引用
