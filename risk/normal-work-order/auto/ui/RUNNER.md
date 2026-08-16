# UI 回归 Runner 说明

## 全量回归（标准入口）

```bash
# 一键：API + UI + 生成总览报告
npm run regression

# 仅跑 UI（生成 Playwright HTML report + ui-pw-result.json）
npx playwright test

# 查看 Playwright 交互式报告
npx playwright show-report docs/reports/playwright-report

# 带 Trace 录制
npx playwright test --trace on
npx playwright show-trace test-results/<测试名>/trace.zip
```

> **ui_runner.py 已废弃**，不再维护。所有 UI 用例统一在 `runner.spec.ts`。

## 回归报告格式（已固定）

报告生成脚本：项目根 `gen_report.py`
产出：`docs/reports/普通工单-全量回归总览-YYYY-MM-DD.html`

报告结构：
1. **执行摘要** — UI PASS/FAIL/SKIP + API PASS/FAIL + 🟡DB校验数/🔴人工项数
2. **UI 回归区** — S1–S9 折叠列表 + 截图；右上角「打开 Playwright Report」按钮
3. **API 回归区** — 5 flows 折叠，每 step 断言（path/期望/实际）+ Response Preview
4. **DB 校验清单** — 可勾选 checkbox + 完整 SQL

---

## 添加新用例

在 `runner.ts` 末尾加一个函数，然后加进 `runners` 数组：

```typescript
async function runS10(page: Page) {
  console.log('\n===== S10 xxx =====');
  await page.goto(`${BASE}/...`);
  await page.waitForLoadState('networkidle');
  await shot(page, 'S10-01-xxx');
  // 验证 ...
  rec('S10', '步骤描述', 'PASS', '详情', 'S10-01-xxx');
}

// runners 数组末尾加：
['S10', runS10],
```

---

## 核心工具函数

| 函数 | 用途 |
|------|------|
| `shot(page, name)` | 截图（等 networkidle + spin 消失 + 弹窗动画结束）|
| `clickText(page, text)` | 按文本找 button/a 并 JS click |
| `jsClick(page, selector)` | CSS selector JS click |
| `antSelect(page, containerSel, optionText)` | Ant Design Select（force click 打开 + insertText 搜索）|
| `fillInput(page, selector, text)` | React 受控 input（insertText）|
| `rowAction(page, action)` | 列表第一行点操作按钮 |
| `rec(scene, step, status, detail, shot)` | 记录一步结果 |

---

## Ant Design Select 的正确姿势

```typescript
// ❌ 错误：JS dispatchEvent 打开，但不 focus 搜索框
trigger.dispatchEvent(new MouseEvent('mousedown', ...));

// ✅ 正确：force click 打开（跳过 stability 检查，同时 focus 搜索框）
await page.click(`${containerSel} .ant-select-selector`, { force: true });
// 再用 insertText 搜索（keyboard.type 不触发 React onChange）
await page.keyboard.insertText(text.slice(0, 8));
```

---

## 前置条件

**仅 UI 段**需要 Chrome CDP。API 段（api_runner.py）自 2026-08-15 起从 **ego-browser** 抓 cookie，不再依赖此 Chrome。

antd 表单驱动能力（2026-08-16 ego 实测更新）：
- ❌ ego **高层 helpers**（typeText/insertText/setNativeValue，元素级合成事件）无法同步 antd Form state——2026-08-12 实测，维持
- ✅ ego **raw cdp 通道可以完整跑通 S2 建单全链路**（2026-08-16 纯 ego 实跑：radio 选其他 → 模板全名搜索精确选中「测试工单类型-一级审批」(configId=21) → `Input.insertText` 原生打入工单名称 → 店铺Handle tags 回车成 token → 提交弹窗关闭零校验错误 → API 查回 issueId 6356/storeHandle 真值 → 删除清理）
- ⚠️ 回车成 tag 的正确姿势：**CDP `Input.dispatchKeyEvent` 不会被 rc-select tokenizer 认**（试过带 text:'\r' 也无效）；必须页面内合成 `new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true})` 派发到搜索 input（React 根节点收合成事件即触发）。主键字段源码即证：`mode="tags"` + `open={false}`（下拉永不打开，纯回车成 token）
- ⚠️ 模板选项必须**全名精确匹配**：搜「测试工单类型-一级」会同时命中「一级多人审批」变体，取错则字段/审批人全错（多人版主键是选项式「商家账号」Select、预填双人审批）
- ⚠️ ego CLI 响应通道仍不稳（动作型调用回包概率性丢失，须 fire-and-forget+微读取轮询模式；useOrCreateTaskSpace/js() 挂死，claimTaskSpace+cdp() 可用）——**技术上 UI 段已可全迁 ego**，量产回归暂仍用 TS Playwright，待 ego 通道修复后即可切换（迁移=把 runner.spec.ts 的动作重写为上述 cdp 脚本模式）

Chrome 需以 CDP 模式启动并已登录：

```bash
open -a 'Google Chrome' --args \
  --remote-debugging-port=9333 \
  --user-data-dir=$HOME/.chrome-test-profile
```

---

## 产出

| 文件 | 说明 |
|------|------|
| `auto/screenshots/ui/Sx-xx.png` | 每步截图 |
| `auto/ui-exec-result.json` | 步骤结果 JSON |
| `docs/reports/普通工单-UI回归报告-YYYY-MM-DD.html` | 内嵌截图的 HTML 报告 |
| `auto/ui-trace.zip` | Playwright Trace（`--trace` 时生成）|
