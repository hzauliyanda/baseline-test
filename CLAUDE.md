# baseline-test kit（测试基线四步管道）

本仓库是可分发的测试全链路工具包：①探索建基线 → ②用例派生 → ③执行回归 → ④审查收口。

**任何 AI 工具（Claude Code / Codex）的入口都是 `docs/SOP-四步.md`**——先读它，
按用户所处步骤干活；设计决策与契约见 `SPEC.md`（冲突时以 SPEC 为准）。

当前进度：四步全部落地 ✅——schema 定稿 / ①tc-explore（双源扫描+ego抓包+脚手架，真仓逐值验证）/ ②tc-cases（放行门）/ ③tc-run（真模块实测）/ ④tc-verify（verdict=FAIL 正确咬人）。
