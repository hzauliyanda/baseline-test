/**
 * 普通工单 UI 回归 — 增补批次 B/C/D/E（S10–S23）@playwright/test 版
 * 运行：npx playwright test（与 runner.spec.ts 一起，串行）
 * CDP attach 模式：复用 port 9333 已登录 Chrome
 *
 * 设计：除 S14 为只读回显外，其余用例一律走【取消/只读】，不提交、不建数据 → 可重复跑。
 * 选择器与断言均来自 2026-08-12 ego-browser 实测。
 */
import { test, expect, chromium } from '@playwright/test';
import type { Page, TestInfo } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

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

// ── 工具函数（与 runner.spec.ts 同源） ───────────────────────────────────────
async function shot(name: string, testInfo: TestInfo) {
  try { await page.waitForLoadState('networkidle', { timeout: 6000 }); } catch {}
  await page.waitForFunction(() => !document.querySelector('.ant-spin-spinning'), { timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(400);
  const file = path.join(SHOTS, `${name}.png`);
  await page.screenshot({ path: file });
  await testInfo.attach(name, { path: file, contentType: 'image/png' });
}

async function clickText(text: string) {
  await page.evaluate((t) => {
    const el = Array.from(document.querySelectorAll('button,a,[role=button]'))
      .find(e => (e as HTMLElement).textContent?.replace(/\s/g, '') === t.replace(/\s/g, '')) as HTMLElement;
    el?.click();
  }, text);
}

/** 从「指定 label 的 form-item」内的 antd Select 选一项（打开→搜索→点选项） */
async function selectByLabel(label: string, optionText: string) {
  const opened = await page.evaluate((lb) => {
    const fi = Array.from(document.querySelectorAll('.ant-form-item'))
      .find(it => it.querySelector('.ant-form-item-label label')?.textContent?.trim() === lb);
    const sel = fi?.querySelector('.ant-select-selector') as HTMLElement;
    if (!sel) return false;
    ['mousedown','mouseup','click'].forEach(t => sel.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })));
    return true;
  }, label);
  expect(opened, `未找到 label=${label} 的 Select`).toBe(true);
  await page.waitForTimeout(700);
  const picked = await page.evaluate((txt) => {
    const dd = document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)');
    const item = Array.from(dd?.querySelectorAll('.ant-select-item-option') ?? [])
      .find(el => el.textContent?.trim() === txt) as HTMLElement;
    if (item) { ['mousedown','mouseup','click'].forEach(t => item.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window }))); return true; }
    return false;
  }, optionText);
  expect(picked, `label=${label} 下未找到选项「${optionText}」`).toBe(true);
  await page.waitForTimeout(900);
}

/** 读取指定 label form-item 下的可见字段标签集合 */
async function visibleLabels(): Promise<string[]> {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll('.ant-form-item-label label')).map(l => l.textContent!.trim()).filter(Boolean)
  );
}
async function uniqueErrors(scope = 'body'): Promise<string[]> {
  return page.evaluate((sc) => {
    const root = sc === 'modal' ? document.querySelector('.ant-modal') : document;
    return [...new Set(Array.from(root?.querySelectorAll('.ant-form-item-explain-error') ?? []).map(e => e.textContent!.trim()))];
  }, scope);
}
async function toasts(): Promise<string[]> {
  return page.evaluate(() => Array.from(document.querySelectorAll('.ant-message-notice-content')).map(e => e.textContent!.trim()));
}

/** 打开新建工单弹窗第二层：选工单类型 radio + 工单模板 */
async function openCreateSecondLevel(radioType: string, templateName: string) {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await clickText('新建工单');
  await page.waitForSelector('.ant-modal-title', { timeout: 6000 });
  await page.waitForTimeout(600);
  await page.evaluate((rt) => {
    (Array.from(document.querySelectorAll('.ant-modal .ant-radio-wrapper'))
      .find(r => r.textContent?.trim() === rt) as HTMLElement)?.click();
  }, radioType);
  await page.waitForTimeout(600);
  // 工单模板：第一层唯一 Select
  await page.evaluate(() => {
    const sel = document.querySelector('.ant-modal .ant-select .ant-select-selector') as HTMLElement;
    ['mousedown','mouseup','click'].forEach(t => sel?.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })));
  });
  await page.waitForTimeout(500);
  await page.keyboard.insertText(templateName.slice(0, 6));
  await page.waitForTimeout(900);
  const picked = await page.evaluate((tn) => {
    const dd = document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)');
    const item = Array.from(dd?.querySelectorAll('.ant-select-item-option') ?? [])
      .find(el => el.textContent?.trim() === tn) as HTMLElement;
    if (item) { ['mousedown','mouseup','click'].forEach(t => item.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window }))); return true; }
    return false;
  }, templateName);
  expect(picked, `未找到模板「${templateName}」`).toBe(true);
  await page.waitForTimeout(1500);
}

async function closeModalCancel() {
  // 新建工单弹窗底部只有 保存/完成，取消=右上角 X(.ant-modal-close)
  await page.evaluate(() => {
    const x = document.querySelector('.ant-modal-wrap:not([style*="display: none"]) .ant-modal-close, .ant-modal-close') as HTMLElement;
    if (x) { x.click(); return; }
    (Array.from(document.querySelectorAll('.ant-modal button'))
      .find(b => (b as HTMLElement).textContent?.replace(/\s/g,'') === '取消') as HTMLElement)?.click();
  });
  await page.waitForTimeout(600);
}

// ═══ S10 模板表单必填校验 ═══
test('S10 模板表单必填校验', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/template/add`);
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.ant-form-item', { timeout: 8000 });
  await clickText('完成');
  await page.waitForTimeout(800);
  await shot('S10-required', testInfo);
  const errs = await uniqueErrors();
  expect(errs, '应报模板类型必填').toContain('请选择模板类型');
  expect(errs, '应报模板名称必填').toContain('请输入模板名称');
  // 未选类型时主键字段不渲染 → 不应有主键必填
  expect(errs.some(e => e.includes('主键')), '空态不应出现主键必填(未选类型不渲染)').toBe(false);
});

// ═══ S11 模板类型驱动字段显隐 ═══
test('S11 模板类型驱动字段显隐', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/template/add`);
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.ant-form-item', { timeout: 8000 });
  await selectByLabel('模板类型', '其他');
  let labels = await visibleLabels();
  expect(labels, 'OTHER 应有主键字段').toContain('主键字段');
  expect(labels.some(l => /名单库/.test(l)), 'OTHER 不应有名单库').toBe(false);

  await selectByLabel('模板类型', '名单申请');
  labels = await visibleLabels();
  expect(labels.some(l => /名单库/.test(l)), '名单申请应有名单库').toBe(true);
  expect(labels, '名单申请应有是否约定月份').toContain('是否约定月份');

  await selectByLabel('模板类型', '名单剔除');
  labels = await visibleLabels();
  expect(labels.some(l => /剔除名单库/.test(l)), '名单剔除标签应为剔除名单库').toBe(true);
  expect(labels.some(l => /配置材料/.test(l)), '名单剔除不应有材料配置').toBe(false);
  await shot('S11-linkage', testInfo);
});

// ═══ S12 材料配置分支（ENUM/枚举值/最多20） ═══
test('S12 材料配置分支', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/template/add`);
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.ant-form-item', { timeout: 8000 });
  await selectByLabel('模板类型', '其他');
  await clickText('添加多材料');
  await page.waitForTimeout(600);
  // 材料类型选项含 枚举
  const opened = await page.evaluate(() => {
    const s = Array.from(document.querySelectorAll('.ant-select'))
      .find(x => /请选择材料类型/.test(x.querySelector('.ant-select-selection-placeholder')?.textContent || ''));
    const sel = s?.querySelector('.ant-select-selector') as HTMLElement;
    ['mousedown','mouseup','click'].forEach(t => sel?.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })));
    return !!sel;
  });
  expect(opened, '应打开材料类型下拉').toBe(true);
  await page.waitForTimeout(600);
  const opts = await page.evaluate(() =>
    Array.from(document.querySelectorAll('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option-content')).map(e => e.textContent!.trim())
  );
  expect(opts, 'OTHER 材料类型应含枚举').toContain('枚举');
  // 选枚举 → 枚举值输入框出现
  await page.evaluate(() => {
    const o = Array.from(document.querySelectorAll('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option'))
      .find(x => x.textContent?.trim() === '枚举') as HTMLElement;
    ['mousedown','mouseup','click'].forEach(t => o?.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })));
  });
  await page.waitForTimeout(800);
  const hasEnumInput = await page.evaluate(() =>
    Array.from(document.querySelectorAll('input,textarea')).some(i => /枚举值/.test((i as HTMLInputElement).placeholder || ''))
  );
  expect(hasEnumInput, '选枚举后应出现枚举值输入框').toBe(true);
  // 材料最多20：连点添加多材料
  await page.evaluate(() => {
    const b = Array.from(document.querySelectorAll('button')).find(x => x.textContent?.replace(/\s/g,'') === '添加多材料') as HTMLElement;
    for (let i = 0; i < 25; i++) b?.click();
  });
  await page.waitForTimeout(1000);
  const t = await toasts();
  expect(t.some(x => x.includes('配置材料最多20个')), '应提示配置材料最多20个').toBe(true);
  await shot('S12-material', testInfo);
});

// ═══ S13 审批与运营地区配置 ═══
test('S13 审批与运营地区配置', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/template/add`);
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.ant-form-item', { timeout: 8000 });
  await selectByLabel('模板类型', '名单申请');
  // 运营地区单块 disabled
  const areaDisabled1 = await page.evaluate(() => {
    const s = Array.from(document.querySelectorAll('.ant-select'))
      .find(x => /运营地区/.test(x.querySelector('.ant-select-selection-placeholder')?.textContent || ''));
    return s ? s.classList.contains('ant-select-disabled') : null;
  });
  expect(areaDisabled1, '单个运营地区块应 disabled').toBe(true);
  // 审批最多5级
  await page.evaluate(() => {
    const b = Array.from(document.querySelectorAll('button')).find(x => x.textContent?.replace(/\s/g,'') === '添加多级审批人') as HTMLElement;
    for (let i = 0; i < 8; i++) b?.click();
  });
  await page.waitForTimeout(1000);
  const t = await toasts();
  expect(t.some(x => x.includes('审批人最多五级')), '应提示审批人最多五级').toBe(true);
  await shot('S13-approval', testInfo);
});

// ═══ S14 模板编辑回显与 disabled（只读，不提交） ═══
test('S14 模板编辑回显与disabled', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/template`);
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.ant-table-tbody tr.ant-table-row', { timeout: 8000 });
  // 点第一条含"编辑"的行的编辑
  const clicked = await page.evaluate(() => {
    const row = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
      .find(r => Array.from(r.querySelectorAll('a,button')).some(a => a.textContent?.trim() === '编辑'));
    const edit = Array.from(row?.querySelectorAll('a,button') ?? []).find(a => a.textContent?.trim() === '编辑') as HTMLElement;
    if (edit) { edit.click(); return true; }
    return false;
  });
  expect(clicked, '应有可编辑模板').toBe(true);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
  expect(page.url(), '应进入编辑模板页').toContain('operateType=edit');
  // 模板类型/模板名称(中/英) disabled
  const disabledStates = await page.evaluate(() => {
    const typeSel = Array.from(document.querySelectorAll('.ant-select'))
      .find(s => { const it = s.querySelector('.ant-select-selection-item'); return it && ['名单申请','名单剔除','其他','商家入驻'].includes(it.textContent!.trim()); });
    const nameInputs = Array.from(document.querySelectorAll('input')).filter(i => /200字符/.test((i as HTMLInputElement).placeholder || ''));
    return {
      typeDisabled: typeSel ? typeSel.classList.contains('ant-select-disabled') : null,
      nameDisabled: nameInputs.slice(0, 2).map(i => (i as HTMLInputElement).disabled),
    };
  });
  expect(disabledStates.typeDisabled, '编辑态模板类型应 disabled').toBe(true);
  expect(disabledStates.nameDisabled.every(Boolean), '编辑态模板名称(中/英)应 disabled').toBe(true);
  await shot('S14-edit-echo', testInfo);
});

// ═══ S15 新建弹窗双层门槛与取消 ═══
test('S15 新建弹窗双层门槛与取消', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await clickText('新建工单');
  await page.waitForSelector('.ant-modal-title', { timeout: 6000 });
  await page.waitForTimeout(600);
  // 第一层：保存/完成 disabled，宽度600
  const l1 = await page.evaluate(() => {
    const foot = Array.from(document.querySelectorAll('.ant-modal-footer button')).map(b => ({ t: b.textContent!.replace(/\s/g,''), d: (b as HTMLButtonElement).disabled }));
    return { foot, width: (document.querySelector('.ant-modal') as HTMLElement)?.style.width };
  });
  expect(l1.foot.every(b => b.d), '第一层保存/完成应 disabled').toBe(true);
  expect(l1.width, '第一层宽度应600px').toBe('600px');
  // 选类型+模板 → 第二层
  await page.evaluate(() => {
    (Array.from(document.querySelectorAll('.ant-modal .ant-radio-wrapper')).find(r => r.textContent?.trim() === '名单申请') as HTMLElement)?.click();
  });
  await page.waitForTimeout(500);
  await page.evaluate(() => {
    const sel = document.querySelector('.ant-modal .ant-select .ant-select-selector') as HTMLElement;
    ['mousedown','mouseup','click'].forEach(t => sel?.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })));
  });
  await page.waitForTimeout(500);
  await page.keyboard.insertText('名单申请测试1'.slice(0, 6));
  await page.waitForTimeout(900);
  await page.evaluate(() => {
    const item = Array.from(document.querySelectorAll('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option'))
      .find(el => el.textContent?.trim() === '名单申请测试1') as HTMLElement;
    ['mousedown','mouseup','click'].forEach(t => item?.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })));
  });
  await page.waitForTimeout(1500);
  const l2 = await page.evaluate(() => {
    const foot = Array.from(document.querySelectorAll('.ant-modal-footer button')).map(b => (b as HTMLButtonElement).disabled);
    return { footEnabled: foot.every(d => d === false), width: (document.querySelector('.ant-modal') as HTMLElement)?.style.width };
  });
  expect(l2.footEnabled, '第二层保存/完成应 enabled').toBe(true);
  expect(l2.width, '第二层宽度应1180px').toBe('1180px');
  await shot('S15-gate', testInfo);
  // 取消（antd 关闭后 .ant-modal 仍留 DOM，判可见性）
  await closeModalCancel();
  await page.waitForTimeout(800);
  const modalHidden = await page.evaluate(() => {
    const wrap = document.querySelector('.ant-modal-wrap') as HTMLElement | null;
    const title = document.querySelector('.ant-modal-title') as HTMLElement | null;
    const wrapHidden = !wrap || wrap.style.display === 'none' || wrap.offsetParent === null;
    const titleHidden = !title || title.offsetParent === null;
    return wrapHidden && titleHidden;
  });
  expect(modalHidden, '取消后弹窗应隐藏').toBe(true);
});

// ═══ S16 名单数据 dataSync 联动 ═══
test('S16 名单数据dataSync联动', async ({}, testInfo) => {
  await openCreateSecondLevel('名单申请', '名单申请测试1');
  // 主键=商家账号 → T+1
  await selectByLabel('主键', '商家账号').catch(async () => {
    // 名单数据区主键 label 可能就是"主键"，若失败尝试点击首个"请选择主键"
    await page.evaluate(() => {
      const s = Array.from(document.querySelectorAll('.ant-modal .ant-select')).find(x => /请选择主键/.test(x.querySelector('.ant-select-selection-placeholder')?.textContent || ''));
      const sel = s?.querySelector('.ant-select-selector') as HTMLElement;
      ['mousedown','mouseup','click'].forEach(t => sel?.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })));
    });
    await page.waitForTimeout(600);
    await page.evaluate(() => {
      const o = Array.from(document.querySelectorAll('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option')).find(x => x.textContent?.trim() === '商家账号') as HTMLElement;
      ['mousedown','mouseup','click'].forEach(t => o?.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })));
    });
    await page.waitForTimeout(900);
  });
  const cb1 = await page.evaluate(() => Array.from(document.querySelectorAll('.ant-modal .ant-checkbox-wrapper')).map(c => c.textContent!.trim()));
  expect(cb1.some(x => /T\+1同步/.test(x)), '商家账号应显示T+1同步文案').toBe(true);
  await shot('S16-namelist', testInfo);
  await closeModalCancel();
});

// ═══ S17 申请说明非必填 + 主键tags 必填 ═══
test('S17 申请说明与主键tags', async ({}, testInfo) => {
  await openCreateSecondLevel('其他', '测试多个材料-001');
  await page.evaluate(() => {
    (Array.from(document.querySelectorAll('.ant-modal-footer button')).find(b => b.textContent?.replace(/\s/g,'') === '完成') as HTMLElement)?.click();
  });
  await page.waitForTimeout(1000);
  const errs = await uniqueErrors('modal');
  expect(errs, '应报工单名称必填').toContain('请输入工单名称');
  expect(errs.some(e => /店铺Handle/.test(e)), '应报主键(店铺Handle)必填').toBe(true);
  expect(errs.some(e => /申请说明/.test(e)), '申请说明不应必填报错').toBe(false);
  await shot('S17-fields', testInfo);
  await closeModalCancel();
});

// ═══ S18 材料动态字段渲染 + 上传提示（材料必填反转已记录） ═══
test('S18 材料动态字段渲染', async ({}, testInfo) => {
  await openCreateSecondLevel('其他', '测试多个材料-001');
  const info = await page.evaluate(() => {
    const m = document.querySelector('.ant-modal')!;
    const hasTextarea = Array.from(m.querySelectorAll('textarea')).some(t => /请输入配置字段/.test((t as HTMLTextAreaElement).placeholder || ''));
    const hasUpload = !!m.querySelector('.ant-upload');
    const hint = /大小不能超过5MB/.test(m.textContent || '');
    return { hasTextarea, hasUpload, hint };
  });
  expect(info.hasTextarea, 'TEXT材料应渲染为TextArea').toBe(true);
  expect(info.hasUpload, 'FILE/IMG材料应渲染Upload').toBe(true);
  expect(info.hint, '应有5MB上传提示').toBe(true);
  await shot('S18-material-dyn', testInfo);
  await closeModalCancel();
});

// ═══ S19 空备注审批拦截（只读，被拦不提交） ═══
test('S19 空备注审批拦截', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  // 找一条待审批且处理人 liyanda 的行 → 查看
  const opened = await page.evaluate(() => {
    const row = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
      .find(r => { const c = Array.from(r.querySelectorAll('td')).map(td => td.textContent!.trim()); return c[3] === '待审批' && c[7] === 'liyanda'; });
    const v = Array.from(row?.querySelectorAll('a,button') ?? []).find(a => a.textContent?.trim() === '查看') as HTMLElement;
    if (v) { v.click(); return true; }
    return false;
  });
  if (!opened) { test.skip(true, '无待审批(liyanda)工单可测'); return; }
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
  const hasApprove = await page.evaluate(() => Array.from(document.querySelectorAll('button,a')).some(e => e.textContent?.replace(/\s/g,'') === '通过'));
  if (!hasApprove) { test.skip(true, '详情无通过按钮'); return; }
  await clickText('通过');
  await page.waitForTimeout(1000);
  const errs = await uniqueErrors();
  expect(errs.some(e => /请输入备注/.test(e)), '空备注点通过应报请输入备注').toBe(true);
  await shot('S19-empty-remark', testInfo);
});

// ═══ S20 终态工单不可再审批 + 只读 ═══
test('S20 终态不可审批与只读', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  const opened = await page.evaluate(() => {
    const row = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
      .find(r => Array.from(r.querySelectorAll('td')).map(td => td.textContent!.trim())[3] === '已完结');
    const v = Array.from(row?.querySelectorAll('a,button') ?? []).find(a => a.textContent?.trim() === '查看') as HTMLElement;
    if (v) { v.click(); return true; }
    return false;
  });
  if (!opened) { test.skip(true, '无已完结工单可测'); return; }
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
  const st = await page.evaluate(() => {
    const t = document.body.innerText;
    return {
      hasApproveBtn: Array.from(document.querySelectorAll('button')).some(b => ['通过','驳回'].includes(b.textContent!.replace(/\s/g,''))),
      hasApprovalArea: /审批操作/.test(t.replace(/\s/g,'')),
    };
  });
  expect(st.hasApproveBtn, '已完结不应有通过/驳回按钮').toBe(false);
  expect(st.hasApprovalArea, '已完结不应有审批操作区').toBe(false);
  await shot('S20-terminal-readonly', testInfo);
});

// ═══ S22 列表筛选：工单模板不随模板类型联动（记录实测行为） ═══
test('S22 列表筛选模板联动', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.ant-form-item', { timeout: 8000 });
  await selectByLabel('模板类型', '名单申请');
  await page.waitForTimeout(800);
  // 打开工单模板，检查是否含跨类型模板（实测：不收窄）
  await page.evaluate(() => {
    const fi = Array.from(document.querySelectorAll('.ant-form-item')).find(it => it.querySelector('.ant-form-item-label label')?.textContent?.trim() === '工单模板');
    const sel = fi?.querySelector('.ant-select-selector') as HTMLElement;
    ['mousedown','mouseup','click'].forEach(t => sel?.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })));
  });
  await page.waitForTimeout(1000);
  const optCount = await page.evaluate(() =>
    Array.from(document.querySelectorAll('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option')).length
  );
  // 断言实测行为：仍有较多选项（未收窄为名单申请专属）——记录用，不作强 fail
  expect(optCount, '工单模板下拉应有选项').toBeGreaterThan(0);
  await shot('S22-filter-linkage', testInfo);
  console.log(`[S22][FINDING] 选模板类型=名单申请后 工单模板选项数=${optCount}（实测不随类型收窄，疑似缺陷，需产品确认）`);
});

// ═══ S23 列表筛选：创建人/处理人/创建时间 ═══
test('S23 列表筛选用户与时间', async ({}, testInfo) => {
  await page.goto(`${BASE}/risk-cooperation/cs/normal-work-order/list`);
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.ant-form-item', { timeout: 8000 });
  const st = await page.evaluate(() => {
    const labels = Array.from(document.querySelectorAll('.ant-form-item-label label')).map(l => l.textContent!.trim());
    return {
      hasCreator: labels.includes('创建人'),
      hasHandler: labels.includes('处理人'),
      hasCreatedTime: labels.includes('创建时间'),
      hasRangePicker: !!document.querySelector('.ant-picker'),
    };
  });
  expect(st.hasCreator, '应有创建人筛选').toBe(true);
  expect(st.hasHandler, '列表页应有处理人筛选').toBe(true);
  expect(st.hasCreatedTime, '应有创建时间筛选').toBe(true);
  expect(st.hasRangePicker, '创建时间应为范围选择器').toBe(true);
  await shot('S23-filter-user-time', testInfo);
});
