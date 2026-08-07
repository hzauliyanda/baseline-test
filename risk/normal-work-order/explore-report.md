# 普通工单模块 探索报告

- 系统/环境：test-risk.inshopline.com（测试环境）
- 模块：普通工单 normal-work-order
- session：risk-normal-work-order-20260801
- 探索时间：2026-08-01
- 探索人：liyanda

## 一、功能覆盖

| 页面/功能 | 覆盖情况 | 关键接口 |
|----------|---------|---------|
| 名单申请列表（筛选/查询/翻页/列） | ✅ 全 | POST /mapi/cs/issue/normal/list |
| 筛选下拉枚举（状态/类型/模板/创建人/处理人） | ✅ 全 | GET /base/enums、/config/list/options、/user/creator/NORMAL、/user/handler |
| 新建工单弹窗（类型/模板/动态字段） | ✅ 全 | GET /config/list/normal/group/{TYPE}、GET /config/{id}、GET /base/primary/search、POST /normal/save |
| 工单详情 | ✅ 全 | GET /normal/{id} |
| 编辑（改抄送名单） | ✅ 实操 | POST /normal/edit |
| 审批 通过 | ✅ 实操 | POST /normal/approve (SUCCESS) |
| 审批 驳回 | ⚠️ 推断 | approveStatus=REJECT（未实跑） |
| 删除 | ✅ 实操 | DELETE /base/{id} |
| 我已审批列表 | ✅ 结构+接口 | POST /normal/approve/list |
| 模版管理列表（含行操作入口） | ✅ 结构+接口 | POST /config/list（复制/编辑/删除入口确认，未深入） |
| 新增/编辑工单模板表单 | ❌ 未深入 | 模板配置较复杂，未实操 |

## 二、卡点与处置

### 卡点 1：主键值远程搜索无数据
- 现象：`GET /mapi/cs/issue/base/primary/search?primaryKeyFieldName=merchantId&primaryKeyValue=…` 对 test/a/li0106/li0106@123.com 均返回 `primaryKeyValueList:[]`。
- 影响：「名单申请」类工单（需真实商家主键）无法走完创建。
- 处置：改用 **「其他」类型 + 店铺Handle 模板(configId=21)**。店铺Handle 是 tags 自由输入（回车确认，不走搜索接口），可填任意值，成功绕过并完成全 CRUD+审批链路。
- 建议：若需覆盖「名单申请」真实主键链路，需业务方提供一个测试环境有效的 merchantId/merchantName。

### 卡点 2：recorder ws 周期性超时断开
- 现象：`recorder.py` 后台运行约 2 分钟后 ws `timed out` 退出（探索期间重复 3 次）。
- 处置：按 skill 指引重启（追加写，不丢已抓）。关键动作前均重启一次保证窗口期内抓到。**建议后续给 recorder.py 加 ws 重连/心跳保活。**

### 卡点 3：弹窗字段 id 与列表筛选框冲突 + React 受控输入
- 现象：列表筛选框 `#issueName` 与「新建工单」弹窗「工单名称」字段 id 冲突；且该弹窗输入框为 React 受控组件，合成 fill / insertText 不进 Form store（onChange 未触发），提交时静默校验失败。
- 处置：① 用 `.ant-modal` 作用域给弹窗字段打独立 id（`#modal_issueName`）；② 写 `cdp_type.py` 用 CDP 真实鼠标聚焦 + 逐字符 `Input.dispatchKeyEvent` 输入，React 正常捕获。脚本已留在 `~/AI-TEST/api-flows/cdp_type.py`，可复用于同类 antd 表单。
- 同类坑：Cmd+A 全选清空在该输入上不生效（值会累积），编辑抄送邮箱时也出现；自动化填值需先清空再输入。

## 三、安全护栏执行情况
- 仅操作**自建数据**（issueId=6147，[FLOW] 标记），未触碰他人记录的编辑/删除/审批。
- 详情页「通过/驳回」仅在自有工单(6147，审批人=自己)上实操；他人工单(如 6146 lujiabao 建)只读查看。
- 探索结束已**删除自建工单 6147**（清理完成）。

## 四、自建实体台账
见 `_created.yaml`（issueId=6147，已删除）。

## 五、产物清单
- `普通工单功能地图.md` —— 功能地图（含 action→api 映射）→ 喂 p2/p3
- `flow.yaml` —— 参数化接口流程（7 步全链路）→ 喂 runner.py
- `capture/risk-normal-work-order-20260801.requests.json` / `.curl-log.md` / `.curls.sh` —— 抓包
- `cdp_type.py` —— React 受控输入辅助脚本（工具，非用例）
