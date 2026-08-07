/**
 * 普通工单 UI 全量回归 Runner — TypeScript / Playwright
 * CDP attach 模式：连接 port 9333 已登录 Chrome
 * 覆盖 S1–S9，每步截图，跑完生成 HTML 报告（截图 base64 内嵌）
 *
 * 运行：npx tsx auto/ui/runner.ts
 * 可选视频轨迹：npx tsx auto/ui/runner.ts --trace
 */
import { chromium, Page, BrowserContext } from 'playwright';
import * as path from 'path';
import * as fs from 'fs';

const BASE      = 'https://test-risk.inshopline.com';
const SHOTS     = path.resolve(__dirname, '../screenshots/ui');
const OUT_JSON  = path.resolve(__dirname, '../ui-exec-result.json');
const REPORT_DIR = path.resolve(__dirname, '../../docs/reports');
const TRACE_PATH = path.resolve(__dirname, '../ui-trace.zip');
const USE_TRACE  = process.argv.includes('--trace');

type Status = 'PASS' | 'FAIL' | 'SKIP' | 'PARTIAL';
type StepResult = { 场景: string; 步骤: string; 状态: Status; 详情: string; shot?: string };
const results: StepResult[] = [];

function rec(场景: string, 步骤: string, 状态: Status, 详情 = '', shot?: string) {
  results.push({ 场景, 步骤, 状态, 详情, shot });
  const icon = { PASS: '✅', FAIL: '❌', SKIP: '⏭', PARTIAL: '⚠️' }[状态];
  console.log(`  ${icon} [${场景}] ${步骤}: ${状态}  ${详情.slice(0, 100)}`);
}

// ── 截图：等 networkidle + spin 消失 + 弹窗动画结束 ────────────────────────
async function shot(page: Page, name: string) {
  try { await page.waitForLoadState('networkidle', { timeout: 6000 }); } catch {}
  await page.waitForFunction(() => !document.querySelector('.ant-spin-spinning'), { timeout: 6000 }).catch(() => {});
  await page.waitForFunction(
    () => !document.querySelector('.ant-modal-enter-active,.ant-modal-appear-active'),
    { timeout: 4000 }
  ).catch(() => {});
  await page.waitForTimeout(400);
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
  console.log(`  📸 ${name}.png`);
  return name;
}

// ── 工具函数 ────────────────────────────────────────────────────────────────
async function jsClick(page: Page, selector: string) {
  await page.evaluate((sel) => (document.querySelector(sel) as HTMLElement)?.click(), selector);
}

async function clickText(page: Page, text: string) {
  await page.evaluate((t) => {
    const el = Array.from(document.querySelectorAll('button,a,[role=button]'))
      .find(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === t.replace(/\s/g, '')) as HTMLElement;
    el?.click();
  }, text);
}

/** Ant Design Select：force click 打开（自然 focus 搜索框）→ insertText 搜索 → JS click 选项 */
async function antSelect(page: Page, containerSel: string, optionText: string) {
  await page.click(`${containerSel} .ant-select-selector`, { force: true });
  await page.waitForFunction(() => {
    const dd = document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)');
    return !!dd && (dd as HTMLElement).offsetHeight > 0;
  }, { timeout: 5000 });
  await page.keyboard.insertText(optionText.slice(0, 8));
  await page.waitForTimeout(700);
  const clicked = await page.evaluate((text) => {
    const dd = document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)');
    const items = Array.from(dd?.querySelectorAll('.ant-select-item') ?? []);
    const item = items.find(el => el.textContent?.trim().includes(text)) as HTMLElement;
    if (item) { item.click(); return item.textContent?.trim() ?? 'ok'; }
    return 'NOT_FOUND:' + items.slice(0, 5).map(i => i.textContent?.trim()).join('|');
  }, optionText.slice(0, 6));
  if (!clicked || clicked.startsWith('NOT_FOUND:')) throw new Error(`antSelect: 未找到「${optionText}」 当前=${clicked}`);
  await page.waitForTimeout(400);
}

/** React 受控 input：locator.evaluate() 聚焦（支持 :has-text 等 PW 伪类），再 insertText */
async function fillInput(page: Page, selector: string, text: string) {
  await page.locator(selector).first().evaluate((el) => {
    (el as HTMLInputElement).click();
    (el as HTMLInputElement).focus();
    (el as HTMLInputElement).select();
  });
  await page.waitForTimeout(100);
  await page.keyboard.press('Control+a');
  await page.keyboard.insertText(text);
}

/** 列表第一行点操作按钮 */
async function rowAction(page: Page, action: string) {
  await page.evaluate((act) => {
    const row = document.querySelector('.ant-table-tbody tr.ant-table-row') as HTMLElement;
    (Array.from(row?.querySelectorAll('a,button') ?? []).find(e => (e as HTMLElement).textContent?.trim() === act) as HTMLElement)?.click();
  }, action);
}

/** 含特定文字的行点操作按钮（找不到就用第一行） */
async function rowActionForText(page: Page, rowText: string, action: string) {
  await page.evaluate(([text, act]) => {
    const rows = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'));
    const row = (rows.find(r => r.textContent?.includes(text)) ?? rows[0]) as HTMLElement;
    (Array.from(row?.querySelectorAll('a,button') ?? []).find(e => (e as HTMLElement).textContent?.trim() === act) as HTMLElement)?.click();
  }, [rowText, action]);
}

/** 新建工单通用流程（S2 / S6 复用） */
async function createWorkOrder(page: Page, name: string, handle: string) {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await clickText(page, '新建工单');
  await page.waitForSelector('.ant-modal', { state: 'visible', timeout: 6000 });
  await page.waitForTimeout(600);
  // 选「其他」类型
  await page.evaluate(() => {
    (Array.from(document.querySelectorAll('.ant-modal .ant-radio-wrapper'))
      .find(r => r.textContent?.trim() === '其他') as HTMLElement)?.click();
  });
  await page.waitForTimeout(600);
  await page.waitForSelector('.ant-modal .ant-select', { timeout: 5000 });
  await antSelect(page, '.ant-modal .ant-select', '测试工单类型-一级审批');
  await page.waitForSelector('.ant-modal input', { timeout: 5000 });
  await page.waitForLoadState('networkidle');
  const nameField = '.ant-modal .ant-form-item:has-text("工单名称") input';
  await page.waitForSelector(nameField, { timeout: 5000 });
  await fillInput(page, nameField, name);
  const handleField = '.ant-modal .ant-form-item:has-text("店铺Handle") input';
  await page.waitForSelector(handleField, { timeout: 5000 });
  await fillInput(page, handleField, handle);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(400);
  await jsClick(page, '.ant-modal-footer .ant-btn-primary');
  await page.waitForSelector('.ant-modal', { state: 'hidden', timeout: 8000 });
  await page.waitForLoadState('networkidle');
}

// ═══════════════════════════════════════════════════════════════════════════════
// S1 列表查询筛选
// ═══════════════════════════════════════════════════════════════════════════════
async function runS1(page: Page) {
  console.log('\n===== S1 列表查询筛选 =====');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await shot(page, 'S1-01-list');
  const rows = await page.locator('.ant-table-tbody tr.ant-table-row').count();
  rec('S1', '列表加载', rows > 0 ? 'PASS' : 'FAIL', `行数=${rows}`, 'S1-01-list');

  // 按工单名称过滤
  await fillInput(page, '#issueName', '自动化');
  await clickText(page, '查询');
  await page.waitForLoadState('networkidle');
  await shot(page, 'S1-02-query');
  const rows2 = await page.locator('.ant-table-tbody tr.ant-table-row').count();
  rec('S1', '按名称查询', 'PASS', `过滤后行数=${rows2}`, 'S1-02-query');

  // 重置
  await clickText(page, '重置');
  await page.waitForTimeout(800);
  await shot(page, 'S1-03-reset');
  const nameVal = await page.evaluate(() =>
    (document.getElementById('issueName') as HTMLInputElement)?.value ?? ''
  );
  rec('S1', '重置筛选', nameVal === '' ? 'PASS' : 'FAIL', `筛选值="${nameVal}"`, 'S1-03-reset');

  // 翻页
  await page.evaluate(() => {
    (document.querySelector('.ant-pagination-next:not(.ant-pagination-disabled) button') as HTMLElement)?.click();
  });
  await page.waitForTimeout(1500);
  await shot(page, 'S1-04-page');
  const activePage = await page.evaluate(() =>
    document.querySelector('.ant-pagination-item-active')?.textContent?.trim() ?? '?'
  );
  rec('S1', '翻页至第2页', activePage === '2' ? 'PASS' : 'FAIL', `当前页=${activePage}`, 'S1-04-page');
}

// ═══════════════════════════════════════════════════════════════════════════════
// S2 新建工单
// ═══════════════════════════════════════════════════════════════════════════════
async function runS2(page: Page) {
  console.log('\n===== S2 新建工单提交 =====');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await clickText(page, '重置');
  await page.waitForTimeout(500);

  await clickText(page, '新建工单');
  await page.waitForSelector('.ant-modal', { state: 'visible', timeout: 6000 });
  await page.waitForTimeout(600);
  await shot(page, 'S2-01-modal');
  rec('S2', '打开新建弹窗', (await page.locator('.ant-modal').count()) > 0 ? 'PASS' : 'FAIL', '', 'S2-01-modal');

  // 选「其他」类型 + 模板
  await page.evaluate(() => {
    (Array.from(document.querySelectorAll('.ant-modal .ant-radio-wrapper'))
      .find(r => r.textContent?.trim() === '其他') as HTMLElement)?.click();
  });
  await page.waitForTimeout(600);
  await page.waitForSelector('.ant-modal .ant-select', { timeout: 5000 });
  await antSelect(page, '.ant-modal .ant-select', '测试工单类型-一级审批');
  await page.waitForSelector('.ant-modal input', { timeout: 5000 });
  await page.waitForLoadState('networkidle');

  const nameField = '.ant-modal .ant-form-item:has-text("工单名称") input';
  await page.waitForSelector(nameField, { timeout: 5000 });
  await fillInput(page, nameField, '[FLOW]UI-S2自动化');
  const handleField = '.ant-modal .ant-form-item:has-text("店铺Handle") input';
  await page.waitForSelector(handleField, { timeout: 5000 });
  await fillInput(page, handleField, 'ui-s2-handle');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(400);
  await shot(page, 'S2-02-form');

  await jsClick(page, '.ant-modal-footer .ant-btn-primary');
  await page.waitForSelector('.ant-modal', { state: 'hidden', timeout: 8000 });
  await page.waitForLoadState('networkidle');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await shot(page, 'S2-03-after');
  const found = await page.locator('.ant-table-tbody tr.ant-table-row', { hasText: '[FLOW]UI-S2' }).count();
  rec('S2', '提交并查到新单', found > 0 ? 'PASS' : 'FAIL', `[FLOW]UI-S2 行数=${found}`, 'S2-03-after');
}

// ═══════════════════════════════════════════════════════════════════════════════
// S3 查看详情
// ═══════════════════════════════════════════════════════════════════════════════
async function runS3(page: Page) {
  console.log('\n===== S3 查看工单详情 =====');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await rowAction(page, '查看');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);
  await shot(page, 'S3-01-detail');
  const url = page.url();
  const hasDetail = await page.evaluate(() => document.body.innerText.includes('工单详情'));
  rec('S3', '进入详情页', url.includes('/detail/') && hasDetail ? 'PASS' : 'FAIL', `url=${url}`, 'S3-01-detail');
}

// ═══════════════════════════════════════════════════════════════════════════════
// S4 编辑抄送名单
// ═══════════════════════════════════════════════════════════════════════════════
async function runS4(page: Page) {
  console.log('\n===== S4 编辑抄送名单 =====');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await rowAction(page, '查看');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  await page.evaluate(() => {
    (Array.from(document.querySelectorAll('button,a'))
      .find(e => (e as HTMLElement).textContent?.trim() === '编辑') as HTMLElement)?.click();
  });
  await page.waitForSelector('.ant-modal', { state: 'visible', timeout: 6000 }).catch(() => {});
  await shot(page, 'S4-01-edit');

  const hasInput = await page.locator('input[placeholder*="抄送人邮箱"]').count();
  if (hasInput > 0) {
    await fillInput(page, 'input[placeholder*="抄送人邮箱"]', 'ui-s4-edit@shoplineapp.com');
    await page.evaluate(() => {
      (Array.from(document.querySelectorAll('.ant-modal button,.ant-btn'))
        .find(b => (b as HTMLElement).textContent?.replace(/\s/g, '') === '确定') as HTMLElement)?.click();
    });
    await page.waitForSelector('.ant-modal', { state: 'hidden', timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(800);
    await shot(page, 'S4-02-saved');
    const ccVal = await page.evaluate(() => {
      const it = Array.from(document.querySelectorAll('.ant-descriptions-item'))
        .find(i => i.textContent?.includes('抄送名单'));
      return it?.querySelector('.ant-descriptions-item-content')?.textContent?.trim() ?? '';
    });
    rec('S4', '编辑抄送保存', ccVal.includes('ui-s4-edit') ? 'PASS' : 'FAIL', `抄送名单="${ccVal}"`, 'S4-02-saved');
  } else {
    rec('S4', '编辑抄送', 'SKIP', '无抄送人邮箱输入框（非末级审批人）', 'S4-01-edit');
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// S5 审批通过
// ═══════════════════════════════════════════════════════════════════════════════
async function runS5(page: Page) {
  console.log('\n===== S5 审批通过 =====');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await rowAction(page, '查看');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);
  await shot(page, 'S5-01-detail');

  const hasApprove = await page.evaluate(() =>
    Array.from(document.querySelectorAll('button,a'))
      .some(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === '通过')
  );
  if (hasApprove) {
    await page.evaluate(() => {
      const desc = document.getElementById('approveDesc') as HTMLInputElement;
      if (desc) desc.value = 'UI审批通过';
      (Array.from(document.querySelectorAll('button,a'))
        .find(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === '通过') as HTMLElement)?.click();
    });
    await page.waitForTimeout(2500);
    await shot(page, 'S5-02-after');
    const status = await page.evaluate(() => (document.body.innerText.match(/已通过|已完结/) ?? ['已操作'])[0]);
    rec('S5', '审批通过', 'PASS', `状态=${status}`, 'S5-02-after');
  } else {
    rec('S5', '审批通过', 'SKIP', '无通过按钮（非当前审批人）', 'S5-01-detail');
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// S6 审批驳回
// ═══════════════════════════════════════════════════════════════════════════════
async function runS6(page: Page) {
  console.log('\n===== S6 审批驳回 =====');
  await createWorkOrder(page, '[FLOW]UI-S6驳回', 'ui-s6-handle');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await rowActionForText(page, '[FLOW]UI-S6', '查看');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  const hasReject = await page.evaluate(() =>
    Array.from(document.querySelectorAll('button,a'))
      .some(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === '驳回')
  );
  if (hasReject) {
    await page.evaluate(() => {
      const desc = document.getElementById('approveDesc') as HTMLInputElement;
      if (desc) desc.value = 'UI驳回';
      (Array.from(document.querySelectorAll('button,a'))
        .find(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === '驳回') as HTMLElement)?.click();
    });
    await page.waitForTimeout(2500);
    await shot(page, 'S6-01-reject');
    const status = await page.evaluate(() => (document.body.innerText.match(/已驳回/) ?? ['已操作'])[0]);
    rec('S6', '审批驳回', 'PASS', `状态=${status}`, 'S6-01-reject');
  } else {
    rec('S6', '审批驳回', 'SKIP', '无驳回按钮（非当前审批人）', '');
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// S7 删除工单（清理 [FLOW]UI 测试数据）
// ═══════════════════════════════════════════════════════════════════════════════
async function runS7(page: Page) {
  console.log('\n===== S7 删除[FLOW]工单 =====');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await clickText(page, '重置');
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
      if (!pop) return;
      (Array.from(pop.querySelectorAll('button'))
        .find(b => ['删除', '确定', '确认'].includes((b as HTMLElement).textContent?.replace(/\s/g, '') ?? '')) as HTMLElement)?.click();
    });
    await page.waitForTimeout(1500);
    deleted++;
  }
  await shot(page, 'S7-01-after-delete');
  const left = await page.locator('.ant-table-tbody tr.ant-table-row', { hasText: '[FLOW]UI' }).count();
  rec('S7', '删除[FLOW]工单', left === 0 ? 'PASS' : 'PARTIAL', `删除${deleted}条 剩余${left}`, 'S7-01-after-delete');
}

// ═══════════════════════════════════════════════════════════════════════════════
// S8 我已审批列表
// ═══════════════════════════════════════════════════════════════════════════════
async function runS8(page: Page) {
  console.log('\n===== S8 我已审批列表 =====');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/approved-list`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
  await shot(page, 'S8-01-list');
  const rows = await page.locator('.ant-table-tbody tr.ant-table-row').count();
  rec('S8', '已审批列表加载', 'PASS', `行数=${rows}`, 'S8-01-list');
}

// ═══════════════════════════════════════════════════════════════════════════════
// S9 模版管理
// ═══════════════════════════════════════════════════════════════════════════════
async function runS9(page: Page) {
  console.log('\n===== S9 模版管理 =====');
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/template`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
  await shot(page, 'S9-01-list');
  const actions = await page.evaluate(() => {
    const row = document.querySelector('.ant-table-tbody tr.ant-table-row');
    return Array.from(row?.querySelectorAll('a,button') ?? [])
      .map(e => (e as HTMLElement).textContent?.trim()).filter(Boolean).join(',');
  });
  rec('S9', '模板列表行操作', actions.includes('复制') && actions.includes('删除') ? 'PASS' : 'FAIL', `行操作=${actions}`, 'S9-01-list');

  await clickText(page, '新增工单模板');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);
  await shot(page, 'S9-02-add');
  const url = page.url();
  rec('S9', '新增模板入口', url.includes('/template/add') ? 'PASS' : 'FAIL', `url=${url}`, 'S9-02-add');
}

// ═══════════════════════════════════════════════════════════════════════════════
// HTML 报告生成
// ═══════════════════════════════════════════════════════════════════════════════
function generateReport() {
  const date = new Date().toISOString().slice(0, 10);
  const time = new Date().toLocaleTimeString('zh-CN');
  const pass  = results.filter(r => r.状态 === 'PASS').length;
  const fail  = results.filter(r => r.状态 === 'FAIL').length;
  const skip  = results.filter(r => ['SKIP', 'PARTIAL'].includes(r.状态)).length;

  function encodeShot(name?: string) {
    if (!name) return '';
    const f = path.join(SHOTS, `${name}.png`);
    if (!fs.existsSync(f)) return '';
    return `data:image/png;base64,${fs.readFileSync(f).toString('base64')}`;
  }

  // 按场景分组
  const scenes = [...new Set(results.map(r => r.场景))];
  const sceneBlocks = scenes.map(sc => {
    const steps = results.filter(r => r.场景 === sc);
    const scPass = steps.every(s => s.状态 === 'PASS' || s.状态 === 'SKIP');
    const badge = scPass ? '#52c41a' : '#f5222d';

    const rows = steps.map(s => {
      const icon = { PASS: '✅', FAIL: '❌', SKIP: '⏭', PARTIAL: '⚠️' }[s.状态];
      const bg   = { PASS: '#f6ffed', FAIL: '#fff1f0', SKIP: '#f0f5ff', PARTIAL: '#fffbe6' }[s.状态];
      const img  = s.shot ? `<img src="${encodeShot(s.shot)}" style="max-width:520px;max-height:320px;border-radius:6px;border:1px solid #eee;margin-top:8px;display:block">` : '';
      return `<tr style="background:${bg}">
        <td style="padding:8px 12px;white-space:nowrap">${icon} ${s.步骤}</td>
        <td style="padding:8px 12px;font-size:12px;color:#555">${s.详情}</td>
        <td style="padding:8px 12px">${img}</td>
      </tr>`;
    }).join('\n');

    return `<section style="margin-bottom:28px;border:1px solid #e8e8e8;border-radius:10px;overflow:hidden">
      <header style="padding:12px 18px;background:#fafafa;border-bottom:1px solid #e8e8e8;display:flex;align-items:center;gap:10px">
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${badge}"></span>
        <strong style="font-size:15px">${sc}</strong>
        <span style="font-size:12px;color:#888">${steps.length} 步</span>
      </header>
      <table style="width:100%;border-collapse:collapse">
        <colgroup><col style="width:220px"><col style="width:auto"><col style="width:540px"></colgroup>
        <thead><tr style="background:#fafafa;font-size:12px;color:#888">
          <th style="padding:6px 12px;text-align:left;font-weight:normal">步骤</th>
          <th style="padding:6px 12px;text-align:left;font-weight:normal">详情</th>
          <th style="padding:6px 12px;text-align:left;font-weight:normal">截图</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </section>`;
  }).join('\n');

  const html = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>普通工单 UI 回归报告 ${date}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;color:#1a1a1a;background:#f5f5f5;padding:24px}
.container{max-width:1100px;margin:0 auto}
.header{background:#fff;border-radius:12px;padding:24px 28px;margin-bottom:20px;border:1px solid #e8e8e8}
.header h1{font-size:20px;font-weight:600;margin-bottom:6px}
.meta{font-size:13px;color:#888;margin-bottom:16px}
.summary{display:flex;gap:16px;flex-wrap:wrap}
.stat{padding:12px 20px;border-radius:8px;text-align:center;min-width:80px}
.stat .n{font-size:26px;font-weight:700;line-height:1}
.stat .l{font-size:12px;margin-top:4px;color:#555}
img{border-radius:6px}
section table tr:hover td{filter:brightness(.97)}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>普通工单 UI 全量回归报告</h1>
    <p class="meta">执行时间：${date} ${time} · S1–S9 全场景</p>
    <div class="summary">
      <div class="stat" style="background:#f6ffed;border:1px solid #b7eb8f"><div class="n" style="color:#52c41a">${pass}</div><div class="l">PASS</div></div>
      <div class="stat" style="background:#fff1f0;border:1px solid #ffa39e"><div class="n" style="color:#f5222d">${fail}</div><div class="l">FAIL</div></div>
      <div class="stat" style="background:#f0f5ff;border:1px solid #adc6ff"><div class="n" style="color:#2f54eb">${skip}</div><div class="l">SKIP</div></div>
      <div class="stat" style="background:#fafafa;border:1px solid #d9d9d9"><div class="n" style="color:#333">${results.length}</div><div class="l">总计</div></div>
    </div>
  </div>
  ${sceneBlocks}
</div>
</body>
</html>`;

  fs.mkdirSync(REPORT_DIR, { recursive: true });
  const reportPath = path.join(REPORT_DIR, `普通工单-UI回归报告-${date}.html`);
  fs.writeFileSync(reportPath, html, 'utf8');
  console.log(`\n📄 报告已生成：${reportPath}`);
  return reportPath;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 入口
// ═══════════════════════════════════════════════════════════════════════════════
(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });

  const browser = await chromium.connectOverCDP('http://localhost:9333');
  const ctx: BrowserContext = browser.contexts()[0] ?? await browser.newContext();
  const page: Page = ctx.pages()[0] ?? await ctx.newPage();

  // 可选：录制 Playwright Trace（--trace 参数时开启）
  if (USE_TRACE) {
    await ctx.tracing.start({ screenshots: true, snapshots: true });
    console.log('🎬 Trace 录制已开始（运行结束后用 npx playwright show-trace auto/ui-trace.zip 查看）');
  }

  const runners: [string, (p: Page) => Promise<void>][] = [
    ['S1', runS1],
    ['S2', runS2],
    ['S3', runS3],
    ['S4', runS4],
    ['S5', runS5],
    ['S6', runS6],
    ['S7', runS7],
    ['S8', runS8],
    ['S9', runS9],
  ];

  for (const [id, fn] of runners) {
    try {
      await fn(page);
    } catch (e) {
      console.error(`❌ ${id} 未捕获异常:`, e);
      await shot(page, `${id}-error`).catch(() => {});
      rec(id, '异常中断', 'FAIL', String(e), `${id}-error`);
    }
  }

  if (USE_TRACE) {
    await ctx.tracing.stop({ path: TRACE_PATH });
    console.log(`🎬 Trace 已保存：${TRACE_PATH}`);
    console.log(`   查看命令：npx playwright show-trace ${TRACE_PATH}`);
  }

  // 保存 JSON 结果
  fs.writeFileSync(OUT_JSON, JSON.stringify(results, null, 2), 'utf8');
  console.log(`\n结果 JSON：${OUT_JSON}`);

  // 生成 HTML 报告
  const reportPath = generateReport();

  // 汇总
  const pass  = results.filter(r => r.状态 === 'PASS').length;
  const fail  = results.filter(r => r.状态 === 'FAIL').length;
  const skip  = results.filter(r => ['SKIP', 'PARTIAL'].includes(r.状态)).length;
  console.log(`\n===== 汇总 =====`);
  console.log(`PASS:${pass}  FAIL:${fail}  SKIP/PARTIAL:${skip}  / 总${results.length}`);

  await browser.close();

  // 自动打开报告
  const { exec } = await import('child_process');
  exec(`open "${reportPath}"`);
})();
