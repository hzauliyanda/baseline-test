# 第④步 tc-verify：审查收口

回归「跑完」≠「完成」。本步用**两层审查**收口：机算对账 + 干净上下文审查，
产出 verdict 落盘——无 verdict 或 FAIL，不得宣称回归完成。

## 两层怎么配合

| 层 | 工具 | 查什么 | 产物 |
|---|---|---|---|
| 机算 | `verify_recon.py` | 六项：产物齐全/数字独立重算vs报告HTML/恒红核对/覆盖门复跑/假覆盖扫描/audit_base | `docs/reports/verify-recon-<date>.json` |
| 干净上下文 | 只读 subagent（Claude）或新会话（Codex） | 五项对账：数字/三桶纪律/断言真实性/覆盖抽查/SKIP·FAIL理由 | `docs/reports/verify-<date>.md`（verdict） |

机算 exit 0 只是入场券；exit 1 时 findings 交审查员逐条裁决（有的是硬伤，
有的是可解释的 flake——裁决记录进 verdict）。

## 跑法

```bash
# 1) 机算（在 kit 根目录）
python3 steps/4-verify/verify_recon.py <模块根目录>

# 2) 干净上下文审查
#    Claude：派只读 Explore subagent，输入 = PROMPT-审查清单.md 全文 + 模块根路径
#    Codex ：开新会话，贴 PROMPT-审查清单.md + 模块根路径
#    审查员按清单做五项对账并落盘 verdict
```

## 完成标志

`docs/reports/verify-<date>.md` 存在且结论 ≠ FAIL。
verdict=PASS-with-notes 时，notes 里的待办（如 audit_base 回填）进下轮 ①或②。

## 已实测（2026-08-16，普通工单真模块）

- 机算六项真跑 exit 1：抓到 UI S13 FAIL 未被口径容纳 / check_coverage 不放行
  （金标准故意保留的教学缺口）/ 假覆盖行 `10已废弃` / audit_base 待回填 ×2
- 干净上下文审查真跑（10 分钟，48 次工具调用）：五项对账全做，**verdict=FAIL**
  落盘——且抓到机算没报的新问题：`3已驳回` 的用例引用是悬空散文引用
  （flow 里无 reject 步＝第二种假覆盖），以及 `--check-case-ids` 下 glob 引用
  不存在的第 8 缺口、S4/S5 口径过期漂移
- 结论验证了两层设计的价值：机算管数字与门，人审管语义与真假——**门真的会咬人**，
  这正是「无 verdict 不得宣称完成」的意义
- 金标准产物：`examples/risk-normal-work-order/docs/reports/` 下有本轮
  recon JSON / verdict / S13 复跑取证三件套可对照
