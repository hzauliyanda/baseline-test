/**
 * S2 创建工单主流程 - Playwright TypeScript
 * CDP attach 模式：所有点击走 page.evaluate() 触发 JS click
 * 等待和截图用 Playwright 原生 API（networkidle + waitForSelector）
 */
import { chromium, Page } from 'playwright';
import * as path from 'path';
import * as fs from 'fs';

const BASE  = 'https://test-risk.inshopline.com';
const SHOTS = path.resolve(__dirname, '../screenshots/ui');
const OUT   = path.resolve(__dirname, '../ui-exec-result.json');

type StepResult = { 场景: string; 步骤: string; 状态: 'PASS' | 'FAIL' | 'SKIP'; 详情: string };
const results: StepResult[] = [];

function rec(场景: string, 步骤: string, 状态: StepResult['状态'], 详情 = '') {
  results.push({ 场景, 步骤, 状态, 详情 });
  const icon = 状态 === 'PASS' ? '✅' : 状态 === 'SKIP' ? '⏭' : '❌';
  console.log(`  ${icon} [${场景}] ${步骤}: ${状态} ${详情}`);
}

/** 截图：等 networkidle + 弹窗动画结束 */
async function shot(page: Page, name: string) {
  try { await page.waitForLoadState('networkidle', { timeout: 5000 }); } catch {}
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
  console.log(`  📸 ${name}.png`);
}

/** CDP attach 模式下用 JS click 触发 React 事件 */
async function jsClick(page: Page, selector: string) {
  await page.evaluate((sel) => {
    (document.querySelector(sel) as HTMLElement)?.click();
  }, selector);
}

/** 按文本找按钮/链接并 JS click */
async function clickText(page: Page, text: string) {
  await page.evaluate((t) => {
    const el = Array.from(document.querySelectorAll('button,a,[role=button]'))
      .find(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === t.replace(/\s/g, '')) as HTMLElement;
    el?.click();
  }, text);
}

/** Ant Design Select：force click 打开 → insertText 搜索 → JS click 选项 */
async function antSelect(page: Page, containerSel: string, optionText: string) {
  // force click 打开下拉并自然 focus 搜索 input
  await page.click(`${containerSel} .ant-select-selector`, { force: true });

  // 等下拉出现
  await page.waitForFunction(() => {
    const dd = document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)');
    return !!dd && (dd as HTMLElement).offsetHeight > 0;
  }, { timeout: 5000 });

  // 用 insertText（触发 React InputEvent）过滤
  await page.keyboard.insertText(optionText.slice(0, 8));
  await page.waitForTimeout(700);

  // 截图查一下搜索结果
  // 点第一个匹配项
  const clicked = await page.evaluate((text) => {
    const dd = document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)');
    const items = Array.from(dd?.querySelectorAll('.ant-select-item') ?? []);
    const item = items.find(el => el.textContent?.trim().includes(text)) as HTMLElement;
    if (item) { item.click(); return item.textContent?.trim() ?? ''; }
    // 打印当前所有选项供调试
    return 'NOT_FOUND:' + items.map(i => i.textContent?.trim()).join('|');
  }, optionText.slice(0, 6));

  if (!clicked || clicked.startsWith('NOT_FOUND:')) {
    throw new Error(`antSelect: 未找到选项「${optionText}」当前选项=${clicked}`);
  }
  await page.waitForTimeout(400);
}

/** React 受控 input：insertText 写入 */
async function fillInput(page: Page, selector: string, text: string) {
  const el = page.locator(selector).first();
  await el.focus();
  await page.keyboard.press('Control+a');
  await page.keyboard.insertText(text);
}

// ── S2 主流程 ────────────────────────────────────────────────────────────────
async function runS2(page: Page) {
  console.log('\n===== S2 新建工单提交 =====');

  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await clickText(page, '重置');
  await page.waitForTimeout(500);

  // 打开弹窗
  await clickText(page, '新建工单');
  await page.waitForSelector('.ant-modal', { state: 'visible', timeout: 6000 });
  await page.waitForTimeout(600);
  await shot(page, 'S2-01-modal');
  rec('S2', '打开新建弹窗', (await page.locator('.ant-modal').count()) > 0 ? 'PASS' : 'FAIL');

  // 选「其他」类型
  await page.evaluate(() => {
    const radios = Array.from(document.querySelectorAll('.ant-modal .ant-radio-wrapper'));
    const other = radios.find(r => r.textContent?.trim() === '其他') as HTMLElement;
    other?.click();
  });
  await page.waitForTimeout(600);

  // 等「其他」类型的模板下拉渲染出来
  await page.waitForSelector('.ant-modal .ant-select', { timeout: 5000 });

  // 选工单模板
  await antSelect(page, '.ant-modal .ant-select', '测试工单类型-一级审批');

  // 等表单字段渲染（选模板后动态出字段）
  await page.waitForSelector('.ant-modal input', { timeout: 5000 });
  await page.waitForLoadState('networkidle');

  // 填工单名称
  const nameField = '.ant-modal .ant-form-item:has-text("工单名称") input';
  await page.waitForSelector(nameField, { timeout: 5000 });
  await fillInput(page, nameField, '[FLOW]UI-S2自动化');

  // 填店铺 Handle
  const handleField = '.ant-modal .ant-form-item:has-text("店铺Handle") input';
  await page.waitForSelector(handleField, { timeout: 5000 });
  await fillInput(page, handleField, 'ui-s2-handle');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(400);

  await shot(page, 'S2-02-form');

  // 提交
  await jsClick(page, '.ant-modal-footer .ant-btn-primary');
  await page.waitForSelector('.ant-modal', { state: 'hidden', timeout: 8000 });
  await page.waitForLoadState('networkidle');

  // 回列表查结果
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await shot(page, 'S2-03-after');

  const found = await page.locator('.ant-table-tbody tr.ant-table-row', { hasText: '[FLOW]UI-S2' }).count();
  const total = await page.locator('.ant-table-tbody tr.ant-table-row').count();
  rec('S2', '提交并查到新单', found > 0 ? 'PASS' : 'FAIL', `[FLOW]UI-S2 行数=${found}，列表共${total}行`);
}

// ── 入口 ─────────────────────────────────────────────────────────────────────
(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });

  const browser = await chromium.connectOverCDP('http://localhost:9333');
  const ctx = browser.contexts()[0] ?? await browser.newContext();
  const page = ctx.pages()[0] ?? await ctx.newPage();

  try {
    await runS2(page);
  } catch (e) {
    console.error('❌ 未捕获异常:', e);
    await shot(page, 'S2-error');
    rec('S2', '异常中断', 'FAIL', String(e));
  } finally {
    let existing: StepResult[] = [];
    if (fs.existsSync(OUT)) existing = JSON.parse(fs.readFileSync(OUT, 'utf8'));
    existing = existing.filter(r => r.场景 !== 'S2');
    fs.writeFileSync(OUT, JSON.stringify([...existing, ...results], null, 2), 'utf8');
    console.log(`\n结果写入 ${OUT}`);
    await browser.close();
  }
})();
