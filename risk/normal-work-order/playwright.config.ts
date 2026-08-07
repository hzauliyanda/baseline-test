import { defineConfig } from '@playwright/test';
import * as path from 'path';

export default defineConfig({
  testDir: './auto/ui',
  testMatch: '**/*.spec.ts',
  workers: 1,                  // 串行：S1→S9 共享同一个浏览器 Tab，不并发
  timeout: 60_000,             // 单个 test 最长 60s
  reporter: [
    ['html', {
      outputFolder: path.join(__dirname, 'docs/reports/playwright-report'),
      open: 'never',
    }],
    ['json', { outputFile: path.join(__dirname, 'auto/ui-pw-result.json') }],
    ['list'],
  ],
  use: {
    // CDP attach 模式不能由 Playwright 管 context，视频/截图在 spec 里手动 attach
    trace: 'off',
  },
});
