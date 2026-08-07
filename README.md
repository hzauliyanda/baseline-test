# baseline-test · 测试基线工具箱

> 给一个系统 URL + 模块，帮你产出并长期维护一套**可信回归基线**。
> 不是让你信 AI，而是让结果由机器断言 / SQL / 人眼各司其职。

---

## 这是什么

| 传统录制回放 | 本工具 |
|---|---|
| 跑绿 = 过 | 跑绿 ≠ 过，数据真伪要 SQL 兜底 |
| 只验接口返回码 | 三桶模型：机器🟢 + DB🟡 + 人工🔴 |
| 用例烂掉没人知道 | 功能地图是唯一真源，代码改了必须回填 |
| 本地脚本各自飞 | 统一仓库，按模块协作，`_toolkit` 共享 |

**产出物**：功能地图 · 接口 flow yaml · UI 自动化用例 · 两段式断言 · 人工校验清单 · 回归报告 · 测试平台导入包（cases.json）

---

## 仓库结构

```
baseline-test/
├── _toolkit/              # 全局共享脚本（所有人共用，不要复制到模块里）
│   ├── new-module.sh      # 一键建模块骨架
│   ├── upload_cases.py    # 上传用例到 octopuses 测试平台
│   ├── cdp_type.py        # Ant Design 受控输入助手
│   └── 接口测试全链路方法论.md
├── config.example.yaml    # 配置模板（cp 后改成自己的值）
├── 使用手册.md            # 详细安装 + 配置 + 使用说明（新人必读）
├── risk/                  # 风控系统（@liyanda 维护）
│   └── normal-work-order/ # ★ 满配参考样例（新建模块照这个结构做）
└── slop/                  # 开放平台（待建）
```

> **新建自己的模块**：在对应系统目录下参考 `risk/normal-work-order/` 的布局即可，或直接用脚手架一键生成（见快速上手）。

---

## 前置要求

| 必须有 | 说明 |
|---|---|
| **Claude Code** | 本工具的引擎是 Claude Code agent 按 skill 执行，不是手敲命令 |
| Python 3 | + `pyyaml requests websocket-client` |
| Chrome 桌面版 | 探索阶段用持久化 profile 驱动 |
| 测试环境账号 | 被测系统测试环境 URL + 能登录的账号 |

可选但推荐：

| 可选 | 用途 |
|---|---|
| 后端代码仓库读权限 | 做"接口↔代码分支覆盖审计"，找出 PRD 里没有的 if/枚举守卫 |
| DB 只读权限 | 🟡 桶的 SQL 校验，没有则跳过留待人工 |

---

## 快速上手

```bash
# 1. clone 本仓库
git clone https://github.com/hzauliyanda/baseline-test.git ~/AI-TEST/api-flows
cd ~/AI-TEST/api-flows

# 2. 安装 Python 依赖
pip3 install pyyaml requests websocket-client

# 3. 配置
cp config.example.yaml config.yaml
# 编辑 config.yaml：填你的系统 base_url / appId / cookie_env

# 4. 建你的第一个模块骨架
bash _toolkit/new-module.sh <系统> <模块>   # 例：slop open-api

# 5. 在 Claude Code 里开干
# → "用 api-flow-recorder 探索 slop/open-api"
```

详细每一步的产物、规范、注意事项见 **[使用手册.md](使用手册.md)**。

---

## 已有模块（参考）

| 系统 | 模块 | 状态 | 说明 |
|---|---|---|---|
| risk | normal-work-order | ★ 满配 | 5 flow / 136 接口用例 / UI 9场景 / 双轨制导入 / 人工清单 |
| risk | complaint | 半配 | flow yaml + 功能用例，缺 UI |
| risk | punish | 半配 | flow yaml + 功能用例，缺 UI |
| risk | threathunter | 半成品 | 仅探索 + 1 flow |

> `risk/normal-work-order/` 是最完整的参考样例，新人建议先读它的目录和 flow yaml。

---

## 核心概念（3 分钟）

**三桶信任模型**：每条用例的结论由三类证据决定，缺一不可：

```
🟢 机器判定   接口层确定性判据（错误码 / status / 字段回读）    → runner 自动跑
🟡 DB 兜底    接口 SUCCESS ≠ 数据落库正确，必须 SQL 人工核     → 人跑
🔴 纯人工     跨系统联动 / 越权 / 并发 / UI 视觉               → 人做
```

**两段式断言**（写在 flow yaml 每个 step 里）：

```yaml
assert:       # 🟢 runner 唯一评分段，只放能判死的值
  status: 200
  json:
    - { path: "$.code", equals: "SUCCESS" }

db_check:     # 🟡 runner 忽略此段，永不自动通过，逼你人工核数据
  - table: t_cs_issue
    sql: "SELECT issue_status FROM t_cs_issue WHERE id=<issue_id>;"
    expect: "issue_status=1"

skip_note:    # 🔴 机器跑不了的场景，文字说明
  - "需人工验证越权场景"
```

---

## 贡献指南

1. 从 `main` 拉新分支：`git checkout -b <系统>/<模块>`
2. 用脚手架建骨架：`bash _toolkit/new-module.sh <系统> <模块>`
3. 按 playbook 走（探索 → 出用例 → 冲烟 → 信任层 → 正式回归）
4. **提 MR 前检查**：
   - `config.yaml` 没有入库（`.gitignore` 已拦，确认一下）
   - `auto/auth.json` 没有入库
   - 功能地图已回填最新逻辑
5. `_toolkit/` 有改动请单独说明（影响所有人）

---

## 相关链接

- [使用手册.md](使用手册.md) — 安装 / 配置 / 日常跑回归的详细说明
- [_toolkit/接口测试全链路方法论.md](_toolkit/接口测试全链路方法论.md) — 方法论背景
- [risk/normal-work-order/功能地图.md](risk/normal-work-order/功能地图.md) — 满配样例的功能地图
- [risk/normal-work-order/auto/api/FLOW2CASES.md](risk/normal-work-order/auto/api/FLOW2CASES.md) — 双轨制（本地回归 + 测试平台导入）说明
