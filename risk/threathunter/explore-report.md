# 威胁猎人情报查询 — 探索报告

- 环境：`https://test-risk.inshopline.com`（测试环境）
- 模块：账号安全第三方查询 → 威胁猎人情报查询
- 抓包会话：`risk-threathunter-20260729`
- 探索账号：liyanda(liyanda)
- 日期：2026-07-29

## 覆盖的功能

| Tab | 功能 | 是否实操 | 结果 |
|-----|------|---------|------|
| 全量情报 | 筛选项盘点（含 isRisk 下拉展开） | 是 | 是/否 |
| 全量情报 | 查询（空条件 + 全条件两次） | 是 | 200，list 为空（total=0） |
| 全量情报 | 列表列头盘点 | 是 | 12 列 |
| 全量情报 | 批量验证账密 / 批量标记风险 / 批量加入黑名单 | **否** | 写操作，仅盘点入口 |
| 定向域名情报 | 筛选项盘点（domain/userType/verifyStatus 三下拉展开） | 是 | 取到枚举 |
| 定向域名情报 | 查询（空条件 + 带 domain/userType/url/emailDomain/verifyStatus） | 是 | 200，有真实泄露数据 |
| 定向域名情报 | 列表列头盘点 | 是 | 12 列 |
| 定向域名情报 | 行「验证账密」 / 批量验证账密 | **否** | 写操作，仅盘点入口 |

## 接口清单（本模块相关）

| 接口 | 方法 | 对应动作 |
|------|------|---------|
| `/mapi/analysis/threat/init` | GET | 全量情报初始化 |
| `/mapi/analysis/threat/pages` | POST | 全量情报查询 |
| `/mapi/analysis/privilege-account/init` | GET | 定向域名情报初始化（返回域名枚举 businessParties） |
| `/mapi/analysis/privilege-account/pages` | POST | 定向域名情报查询 |

鉴权：Cookie session（`armorSession` 等）+ 固定头 `appId:4`、`version:v2`，无 Bearer token。

## 安全护栏执行情况

- 本模块为「情报查询」页，全量情报 Tab 无「新增」入口、列表 total=0，**无法造自建数据**；定向域名情报 Tab 列表为真实外部泄露情报，非本人数据。
- 因此所有写操作/影响性动作（**批量验证账密、批量标记风险、批量加入黑名单、行验证账密**）一律**只盘点按钮位置，未点击执行**——这些动作会对真实泄露账号发起账密验证或写入风险标记/黑名单，属 denylist。
- 仅执行了查询类只读动作（threat/pages、privilege-account/pages）与筛选下拉展开。

## 断点 / 缺口

1. **写操作接口未抓到**：批量验证账密 / 批量标记风险 / 批量加入黑名单 / 行验证账密 的接口未录制（未实操）。如需接口自动化，需在有明确授权且可控数据前提下补录。
2. **泄露日期 `eventRange` 参数名未确认**：日期区间控件本次未实填，功能地图已标注字段 id，提交参数名待补。
3. **抓包器进程两次自动退出**（exit 0）：探索中重启一次，采用追加写未丢数据；关键查询接口均已抓到。

## 卡点问答记录

无（全程未遇登录失效/验证码/审批阻塞；未触碰需二次确认的写操作）。

## 交接

- 功能用例 → `p2-test-case-generator`，输入 `威胁猎人情报查询功能地图.md`
- UI 自动化用例 → `p3-ui-test-case-generator`，输入 功能地图 + p2 功能用例
- 接口用例 → 本 skill `flow.yaml`（执行：`runner.py flow.yaml --set cookie="<Cookie>"`）
