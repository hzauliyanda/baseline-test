# UI 回归 Runner 说明（纯 ego-browser）

> 2026-08-16 起 UI 段**全面 ego 化**：无 9333 Chrome、无 Playwright、无独立 CDP 工具链。
> 浏览器唯一入口 = **ego lite**（复用用户登录态）。旧 TS Playwright 版（runner.spec.ts / runner-augment.spec.ts / runner.ts）已退役，仅留作语义快照参照。

## 全量回归（标准入口）

```bash
# 一键：API + UI + 生成总览报告
npm run regression

# 仅跑 UI（纯 ego，22 场景）
python3 auto/ui/ego_ui_runner.py

# 指定场景
python3 ego_ui_runner.py S2 S15        # 子集
EGO_DEBUG=1 python3 ego_ui_runner.py   # 打印每次 ego CLI 原始输出
```

## 文件结构

| 文件 | 职责 |
|------|------|
| `ego_ui_runner.py` | 驱动内核（ego 通道/看门狗）+ 页面注入原语（antd 适配）+ 入口 |
| `ego_scenarios.py` | 22 个场景实现（S1–S9 ← runner.spec.ts；S10–S23 ← runner-augment.spec.ts；S21 原版即缺号）+ TITLES |

## 前置条件

- **ego lite 已打开**且已登录 `test-risk.inshopline.com`（登录态复用用户会话；cookie 过期在 ego 窗口手动重登）
- 任务空间：runner 自动发现（`listTaskSpaces` 取第一个）；没有则先 `useOrCreateTaskSpace('risk-normal-work-order-regression')` 建一次
- API 段 cookie 同源：api_runner.py 也是 ego-only（`RISK_COOKIE` 环境变量可临时兜底）

## 通道协议（2026-08-16 实测定型，内核已固化）

| 现象 | 对策 |
|------|------|
| 动作型 CLI 调用回包概率性丢失 | 动作一律 **fire-and-forget 注入**（`eval(atob(b64))`）+ 独立微读取轮询回读 `window.__ego` 日志 |
| `useOrCreateTaskSpace`/`js()` 会挂死 | `claimTaskSpace(<已有id>)` + `cdp()` |
| CLI 挂死 | 看门狗超时（独立进程组 `killpg` 杀干净含孙进程）+ `pkill` 残留 + 单场景 FAIL 不拖垮整轮 |
| 长 `await wait()` 在 ego CLI 里拖挂调用 | CLI 脚本秒回，**settle 全在 Python 侧** `time.sleep` |
| 中文注入脚本 | base64(ascii backslashreplace)，页面侧 `eval(atob())` |
| ego 进程被杀后任务空间清空 | 重开 ego lite → `useOrCreateTaskSpace` 重建 → runner 可继续 |

## antd 驱动要点（全部实测验证）

- **填值**：页面脚本 focus → `cdp('Input.insertText')` 原生管道（antd Form 认值）
- **tags 回车**：CDP `Input.dispatchKeyEvent` **不被 rc-select 认**；必须页面内合成 `new KeyboardEvent('keydown',{key:'Enter',keyCode:13,...,bubbles:true})`（主键字段源码即 `mode="tags" open={false}`，下拉永不打开）
- **Select**：`mousedown` 开启（不是 click）+ React native value setter 搜索 + **全名精确匹配**点击
- **模板必须全名**：搜「测试工单类型-一级」会同时命中「一级多人审批」变体，取错则字段/审批人全错
- **findItem 必须限定 `.ant-modal` 作用域**：列表页筛选表单有同名字段（工单名称），DOM 顺序在前会抢焦点（2026-08-16 踩坑实锤）

## 设计约定

- 除 S2/S5/S6/S7 有真实数据动作外，其余场景一律【取消/只读】，不提交不建数据 → 可重复跑
- S2/S6 建单后 **API 查回铁证 + 自清理**；S7 兜底清扫 `[EGO]` 残留（UI 删不动时 API 兜底）
- 条件不满足记 **SKIP**（对齐 Playwright test.skip 语义），不算 FAIL
- 单场景异常/通道挂死只记该场景 FAIL，整轮继续

## 添加新场景

在 `ego_scenarios.py` 加 `run_sN(d)`，用现有原语拼装，然后注册进 `SCENARIOS` + `TITLES`：

```python
def run_s24(d: EgoDriver):
    scene = "S24"
    print(f"\n===== {scene} 新场景名 =====")
    d.fire(js_goto(LIST_URL), settle=6)          # 导航
    d.fire(js_click_text("按钮文案"), settle=2)   # 动作（fire-and-forget）
    val = d.read(R_ROWS) or 0                     # 读取（带回包）
    s1 = shot_step(d, scene, 1, "步骤名")          # 截图
    rec(scene, "断言描述", "PASS" if val else "FAIL", f"val={val}", s1)

SCENARIOS["S24"] = run_s24
TITLES["S24"] = "S24 新场景名"
```

## 回归报告格式（已固定）

生成脚本：项目根 `gen_report.py`（2026-08-16 起读 `auto/ui-ego-exec-result.json`）
产出：`docs/reports/普通工单-全量回归总览-YYYY-MM-DD.html`

报告结构：
1. **执行摘要** — UI PASS/FAIL/SKIP + API PASS/FAIL + 🟡DB校验数/🔴人工项数
2. **UI 回归区** — 22 场景折叠列表，展开含**步骤明细**（每步状态+detail+📷标记）+ 截图
3. **API 回归区** — 5 flows 折叠，每 step 断言（path/期望/实际）+ Response Preview
4. **人工覆盖清单** — 可勾选 checkbox + 完整 SQL

## 产出

| 文件 | 说明 |
|------|------|
| `auto/screenshots/ui/{Sx}-ego-{NN}-{步骤}.png` | 每步截图（31 张/轮） |
| `auto/ui-ego-exec-result.json` | 步骤记录 JSON（scene/step/status/detail/shot + scenes 聚合含 title/ms） |

## 已知能力边界（对齐 Playwright 的差异）

| 能力 | Playwright | 纯 ego |
|------|-----------|--------|
| 每步截图 | ✅ | ✅ |
| console/网络抓取 | ✅ | ✅（cdp 域可用）|
| Trace 时间轴 | ✅ | ❌（用步骤 JSON+截图替代）|
| 录屏 | ✅(video) | ⚠️（需 macOS 录屏权限，未启用）|
