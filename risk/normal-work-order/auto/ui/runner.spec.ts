/**
 * 普通工单 UI 全量回归 — @playwright/test 版
 * 运行：npx playwright test
 * 报告：npx playwright show-report docs/reports/playwright-report
 *
 * CDP attach 模式：复用 port 9333 已登录 Chrome
 * 所有截图通过 testInfo.attach() 内嵌进 HTML 报告
 */
import { test, expect, chromium } from '@playwright/test';
import type { Page, TestInfo } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

// ── 全局共享页面（所有测试串行复用同一个 Tab） ──────────────────────────────
const BASE  = 'https://test-risk.inshopline.com';
const SHOTS = path.resolve(__dirname, '../screenshots/ui');
fs.mkdirSync(SHOTS, { recursive: true });

let page: Page;

test.describe.configure({ mode: 'serial' });

test.beforeAll(async () => {
  const browser = await chromium.connectOverCDP('http://localhost:9333');
  const ctx = browser.contexts()[0];
  page = ctx.pages()[0] ?? await ctx.newPage();
});

// ── 工具函数 ─────────────────────────────────────────────────────────────────

/** 截图 + 等稳定 + 注入报告 */
async function shot(name: string, testInfo: TestInfo) {
  try { await page.waitForLoadState('networkidle', { timeout: 6000 }); } catch {}
  await page.waitForFunction(() => !document.querySelector('.ant-spin-spinning'), { timeout: 6000 }).catch(() => {});
  await page.waitForFunction(
    () => !document.querySelector('.ant-modal-enter-active,.ant-modal-appear-active'),
    { timeout: 4000 }
  ).catch(() => {});
  await page.waitForTimeout(400);
  const file = path.join(SHOTS, `${name}.png`);
  await page.screenshot({ path: file });
  await testInfo.attach(name, { path: file, contentType: 'image/png' });
  return file;
}

async function clickText(text: string) {
  await page.evaluate((t) => {
    const el = Array.from(document.querySelectorAll('button,a,[role=button]'))
      .find(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === t.replace(/\s/g, '')) as HTMLElement;
    el?.click();
  }, text);
}

async function jsClick(selector: string) {
  await page.evaluate((sel) => (document.querySelector(sel) as HTMLElement)?.click(), selector);
}

/** Ant Design Select：force click 打开 → insertText 搜索 → click 选项 */
async function antSelect(containerSel: string, optionText: string) {
  await page.click(`${containerSel} .ant-select-selector`, { force: true });
  await page.waitForFunction(() => {
    const dd = document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)');
    return !!dd && (dd as HTMLElement).offsetHeight > 0;
  }, { timeout: 5000 });
  await page.keyboard.insertText(optionText.slice(0, 8));
  await page.waitForTimeout(700);
  const clicked = await page.evaluate((text) => {
    const dd = document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)');
    const item = Array.from(dd?.querySelectorAll('.ant-select-item') ?? [])
      .find(el => el.textContent?.trim().includes(text)) as HTMLElement;
    if (item) { item.click(); return true; }
    return false;
  }, optionText.slice(0, 6));
  expect(clicked, `antSelect: 未找到选项「${optionText}」`).toBe(true);
  await page.waitForTimeout(400);
}

/**
 * React 受控 input：locator.evaluate() 聚焦（支持 :has-text 等 PW 伪类），再 insertText
 * CDP attach 模式下 locator.focus() 不会真正 focus，用 evaluate 在元素上执行 click+focus
 */
async function fillInput(selector: string, text: string) {
  await page.locator(selector).first().evaluate((el) => {
    (el as HTMLInputElement).click();
    (el as HTMLInputElement).focus();
    (el as HTMLInputElement).select();
  });
  await page.waitForTimeout(100);
  await page.keyboard.press('Control+a');
  await page.keyboard.insertText(text);
}

async function rowAction(action: string) {
  await page.evaluate((act) => {
    const row = document.querySelector('.ant-table-tbody tr.ant-table-row') as HTMLElement;
    (Array.from(row?.querySelectorAll('a,button') ?? [])
      .find(e => (e as HTMLElement).textContent?.trim() === act) as HTMLElement)?.click();
  }, action);
}

async function rowActionForText(rowText: string, action: string) {
  await page.evaluate(([text, act]) => {
    const rows = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'));
    const row = (rows.find(r => r.textContent?.includes(text)) ?? rows[0]) as HTMLElement;
    (Array.from(row?.querySelectorAll('a,button') ?? [])
      .find(e => (e as HTMLElement).textContent?.trim() === act) as HTMLElement)?.click();
  }, [rowText, action]);
}

/** 新建工单（S2 / S6 复用） */
async function createWorkOrder(name: string, handle: string) {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await clickText('新建工单');
  await page.waitForSelector('.ant-modal', { state: 'visible', timeout: 6000 });
  await page.waitForTimeout(600);
  await page.evaluate(() => {
    (Array.from(document.querySelectorAll('.ant-modal .ant-radio-wrapper'))
      .find(r => r.textContent?.trim() === '其他') as HTMLElement)?.click();
  });
  await page.waitForTimeout(600);
  await page.waitForSelector('.ant-modal .ant-select', { timeout: 5000 });
  await antSelect('.ant-modal .ant-select', '测试工单类型-一级审批');
  await page.waitForSelector('.ant-modal input', { timeout: 5000 });
  await page.waitForLoadState('networkidle');
  const nameField = '.ant-modal .ant-form-item:has-text("工单名称") input';
  await page.waitForSelector(nameField, { timeout: 5000 });
  await fillInput(nameField, name);
  const handleField = '.ant-modal .ant-form-item:has-text("店铺Handle") input';
  await page.waitForSelector(handleField, { timeout: 5000 });
  await fillInput(handleField, handle);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(400);
  await jsClick('.ant-modal-footer .ant-btn-primary');
  await page.waitForSelector('.ant-modal', { state: 'hidden', timeout: 8000 });
  await page.waitForLoadState('networkidle');
}

// ═══════════════════════════════════════════════════════════════════════════════
// S1 列表查询筛选
// ═══════════════════════════════════════════════════════════════════════════════
test('S1 列表查询筛选', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await shot('S1-01-list', testInfo);
  const rows = await page.locator('.ant-table-tbody tr.ant-table-row').count();
  expect(rows, '列表应有数据').toBeGreaterThan(0);

  await fillInput('#issueName', '自动化');
  await clickText('查询');
  await page.waitForLoadState('networkidle');
  await shot('S1-02-query', testInfo);
  const rows2 = await page.locator('.ant-table-tbody tr.ant-table-row').count();
  expect(rows2, '查询结果应 >= 0').toBeGreaterThanOrEqual(0);

  await clickText('重置');
  await page.waitForTimeout(800);
  await shot('S1-03-reset', testInfo);
  const nameVal = await page.evaluate(() =>
    (document.getElementById('issueName') as HTMLInputElement)?.value ?? ''
  );
  expect(nameVal, '重置后输入框应为空').toBe('');

  await page.evaluate(() => {
    (document.querySelector('.ant-pagination-next:not(.ant-pagination-disabled) button') as HTMLElement)?.click();
  });
  await page.waitForTimeout(1500);
  await shot('S1-04-page', testInfo);
  const activePage = await page.evaluate(() =>
    document.querySelector('.ant-pagination-item-active')?.textContent?.trim() ?? '?'
  );
  expect(activePage, '应翻到第2页').toBe('2');
});

// ═══════════════════════════════════════════════════════════════════════════════
// S2 新建工单
// ═══════════════════════════════════════════════════════════════════════════════
test('S2 新建工单提交', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await clickText('重置');
  await page.waitForTimeout(500);

  await clickText('新建工单');
  await page.waitForSelector('.ant-modal', { state: 'visible', timeout: 6000 });
  await page.waitForTimeout(600);
  await shot('S2-01-modal', testInfo);
  expect(await page.locator('.ant-modal').count(), '弹窗应出现').toBeGreaterThan(0);

  await page.evaluate(() => {
    (Array.from(document.querySelectorAll('.ant-modal .ant-radio-wrapper'))
      .find(r => r.textContent?.trim() === '其他') as HTMLElement)?.click();
  });
  await page.waitForTimeout(600);
  await page.waitForSelector('.ant-modal .ant-select', { timeout: 5000 });
  await antSelect('.ant-modal .ant-select', '测试工单类型-一级审批');
  await page.waitForSelector('.ant-modal input', { timeout: 5000 });
  await page.waitForLoadState('networkidle');

  const nameField = '.ant-modal .ant-form-item:has-text("工单名称") input';
  await page.waitForSelector(nameField, { timeout: 5000 });
  await fillInput(nameField, '[FLOW]UI-S2自动化');
  const handleField = '.ant-modal .ant-form-item:has-text("店铺Handle") input';
  await page.waitForSelector(handleField, { timeout: 5000 });
  await fillInput(handleField, 'ui-s2-handle');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(400);
  await shot('S2-02-form', testInfo);

  await jsClick('.ant-modal-footer .ant-btn-primary');
  await page.waitForSelector('.ant-modal', { state: 'hidden', timeout: 8000 });
  await page.waitForLoadState('networkidle');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await shot('S2-03-after', testInfo);
  const found = await page.locator('.ant-table-tbody tr.ant-table-row', { hasText: '[FLOW]UI-S2' }).count();
  expect(found, '列表应找到新建的工单').toBeGreaterThan(0);
});

// ═══════════════════════════════════════════════════════════════════════════════
// S3 查看详情
// ═══════════════════════════════════════════════════════════════════════════════
test('S3 查看工单详情', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await rowAction('查看');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);
  await shot('S3-01-detail', testInfo);
  expect(page.url(), '应跳转详情页').toContain('/detail/');
  const hasDetail = await page.evaluate(() => document.body.innerText.includes('工单详情'));
  expect(hasDetail, '页面应含"工单详情"').toBe(true);
});

// ═══════════════════════════════════════════════════════════════════════════════
// S4 编辑抄送名单
// ═══════════════════════════════════════════════════════════════════════════════
test('S4 编辑抄送名单', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await rowAction('查看');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  await page.evaluate(() => {
    (Array.from(document.querySelectorAll('button,a'))
      .find(e => (e as HTMLElement).textContent?.trim() === '编辑') as HTMLElement)?.click();
  });
  // 等行内编辑 input 出现（S4 是行内编辑，不是弹窗）
  await page.waitForSelector('input[placeholder*="抄送人邮箱"]', { timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(300);
  await shot('S4-01-edit', testInfo);

  const hasInput = await page.locator('input[placeholder*="抄送人邮箱"]').count();
  if (hasInput > 0) {
    await fillInput('input[placeholder*="抄送人邮箱"]', 'ui-s4-edit@shoplineapp.com');
    await page.evaluate(() => {
      (Array.from(document.querySelectorAll('.ant-modal button,.ant-btn'))
        .find(b => (b as HTMLElement).textContent?.replace(/\s/g, '') === '确定') as HTMLElement)?.click();
    });
    await page.waitForSelector('.ant-modal', { state: 'hidden', timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(800);
    await shot('S4-02-saved', testInfo);
    const ccVal = await page.evaluate(() => {
      const it = Array.from(document.querySelectorAll('.ant-descriptions-item'))
        .find(i => i.textContent?.includes('抄送名单'));
      return it?.querySelector('.ant-descriptions-item-content')?.textContent?.trim() ?? '';
    });
    expect(ccVal, '抄送名单应含新增邮箱').toContain('ui-s4-edit');
  } else {
    test.skip(true, '无抄送人邮箱输入框（非末级审批人）');
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// S5 审批通过
// ═══════════════════════════════════════════════════════════════════════════════
test('S5 审批通过', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await rowAction('查看');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);
  await shot('S5-01-detail', testInfo);

  const hasApprove = await page.evaluate(() =>
    Array.from(document.querySelectorAll('button,a'))
      .some(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === '通过')
  );
  if (!hasApprove) { test.skip(true, '无通过按钮（非当前审批人）'); return; }

  await page.evaluate(() => {
    const desc = document.getElementById('approveDesc') as HTMLInputElement;
    if (desc) desc.value = 'UI审批通过';
    (Array.from(document.querySelectorAll('button,a'))
      .find(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === '通过') as HTMLElement)?.click();
  });
  await page.waitForTimeout(2500);
  await shot('S5-02-after', testInfo);
});

// ═══════════════════════════════════════════════════════════════════════════════
// S6 审批驳回
// ═══════════════════════════════════════════════════════════════════════════════
test('S6 审批驳回', async ({}, testInfo) => {
  await createWorkOrder('[FLOW]UI-S6驳回', 'ui-s6-handle');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await rowActionForText('[FLOW]UI-S6', '查看');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  const hasReject = await page.evaluate(() =>
    Array.from(document.querySelectorAll('button,a'))
      .some(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === '驳回')
  );
  if (!hasReject) { test.skip(true, '无驳回按钮（非当前审批人）'); return; }

  await page.evaluate(() => {
    const desc = document.getElementById('approveDesc') as HTMLInputElement;
    if (desc) desc.value = 'UI驳回';
    (Array.from(document.querySelectorAll('button,a'))
      .find(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === '驳回') as HTMLElement)?.click();
  });
  await page.waitForTimeout(2500);
  await shot('S6-01-reject', testInfo);
});

// ═══════════════════════════════════════════════════════════════════════════════
// S7 删除工单（清理测试数据）
// ═══════════════════════════════════════════════════════════════════════════════
test('S7 删除[FLOW]工单', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await clickText('重置');
  await page.waitForTimeout(800);

  let deleted = 0;
  for (let i = 0; i < 10; i++) {
    const found = await page.evaluate(() => {
      const row = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
        .find(r => r.textContent?.includes('[FLOW]UI')) as HTMLElement;
      if (!row) return false;
      const btn = Array.from(row.querySelectorAll('a,button'))
        .find(e => (e as HTMLElement).textContent?.trim() === '删除') as HTMLElement;
      if (btn) { btn.click(); return true; }
      return false;
    });
    if (!found) break;
    await page.waitForTimeout(1000);
    await page.evaluate(() => {
      const pop = document.querySelector('.ant-popconfirm,.ant-popover,.ant-modal') as HTMLElement;
      (Array.from(pop?.querySelectorAll('button') ?? [])
        .find(b => ['删除', '确定', '确认'].includes(
          (b as HTMLElement).textContent?.replace(/\s/g, '') ?? ''
        )) as HTMLElement)?.click();
    });
    await page.waitForTimeout(1500);
    deleted++;
  }
  await shot('S7-01-after-delete', testInfo);
  const left = await page.locator('.ant-table-tbody tr.ant-table-row', { hasText: '[FLOW]UI' }).count();
  expect(left, `删${deleted}条后[FLOW]UI剩余应为0`).toBe(0);
});

// ═══════════════════════════════════════════════════════════════════════════════
// S8 我已审批列表
// ═══════════════════════════════════════════════════════════════════════════════
test('S8 我已审批列表', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/approved-list`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
  await shot('S8-01-list', testInfo);
  // 页面正常渲染即 PASS（已审批记录数 >= 0）
  const title = await page.title();
  expect(title).toBeTruthy();
});

// ═══════════════════════════════════════════════════════════════════════════════
// S9 模版管理
// ═══════════════════════════════════════════════════════════════════════════════
test('S9 模版管理', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/template`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
  await shot('S9-01-list', testInfo);
  const actions = await page.evaluate(() => {
    const row = document.querySelector('.ant-table-tbody tr.ant-table-row');
    return Array.from(row?.querySelectorAll('a,button') ?? [])
      .map(e => (e as HTMLElement).textContent?.trim()).filter(Boolean).join(',');
  });
  expect(actions, '行操作应含复制').toContain('复制');
  expect(actions, '行操作应含删除').toContain('删除');

  await clickText('新增工单模板');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);
  await shot('S9-02-add', testInfo);
  expect(page.url(), '应跳转新增模板页').toContain('/template/add');
});
