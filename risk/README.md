# 普通工单模块 · 测试交付与复用手册

> 本手册既是普通工单（normal-work-order）模块的完整交付记录，也是**延伸到其他模块的复用模板**。
> 系统：test-risk.inshopline.com ｜ 仓库：armor-smart-platform(master) ｜ 完成日期：2026-08-01

---

## 一、整体方法论（四阶段，可复用于任何模块）

```
① 探索录制 ──▶ ② 读源码补全 ──▶ ③ 实跑验证 ──▶ ④ 沉淀报告
  CDP驱动+抓包     controller/service      runner跑接口      可视化HTML
  +爬真实数据      /vo/enum 补漏+分支       +cdp跑UI场景      +执行报告
```

| 阶段 | 工具/产物 | 产出 |
|------|----------|------|
| ① 探索 | api-flow-recorder（cdp.py/recorder.py/to_curl.py）+ cdp_type.py | 功能地图、capture 抓包、真实数据池 |
| ② 读码 | 3 个 Agent 并行读 controller/service/vo/enum | 接口全集差距、校验/分支/状态流转 |
| ③ 实跑 | runner.py（接口）+ ui_runner.py（UI） | flow 全绿、UI 截图、执行报告 |
| ④ 报告 | 可视化 HTML | 测试报告、UI 执行报告、缺陷清单 |

---

## 二、探索阶段：如何获取真实数据（关键，其他模块照做）

### 2.1 环境准备
- **持久化 Chrome**：`bash ~/.claude/skills/api-flow-recorder/scripts/launch_chrome.sh 9333 <URL>`
  - 独立 profile（`~/AI-TEST/api-flows/.chrome-profile`），登录态长期复用，首次手动登录，之后免登录。
- **后台抓包**：`nohup python3 scripts/recorder.py <session> &`（探索全程常驻；注意 ws 约 2 分钟超时，关键动作前重启）。
- **确认登录态**：`python3 scripts/cdp.py url`

### 2.2 Cookie 提取（接口用例鉴权用）
鉴权模型 = Cookie + 固定头（`appId:4`、`version:v2`），无 Bearer token。
```python
# CDP 拿完整 Cookie（含 HttpOnly，JS 取不到）
from cdplib import connect
cdp,_,_=connect()
r=cdp.cmd("Network.getCookies",{"urls":["https://test-risk.inshopline.com"]})
cookie="; ".join(f'{c["name"]}={c["value"]}' for c in r["cookies"])
open("/tmp/risk_cookie.txt","w").write(cookie)
# 8 字段：riskAccountUid/riskAccountId/riskAppId/armorPlatform/armorSession/riskUserId/platformLanguage/riskSessionId
```
执行时：`RISK_COOKIE=$(cat /tmp/risk_cookie.txt) python3 runner.py flow.yaml`

### 2.3 真实业务数据池（绕过"搜索接口空数据"卡点）
UI 主键值搜索（`/primary/search`）在测试环境返回空 → 改**爬列表已有工单的 primaryInfo** 拿真实主键，接口层 save 时直传（不依赖搜索）：
```python
# 爬 normal/list 多页（NAMELIST_APPLY + BRAND_PROTECT 两种 listType）
for lt in ["NAMELIST_APPLY","BRAND_PROTECT"]:
    for page in range(1,4):
        d=call("POST","/mapi/cs/issue/normal/list",{"listType":lt,"pageNum":page,"pageSize":50})
        for it in d["data"]["list"]:
            for k,v in (it.get("primaryInfo") or {}).items(): pool[k].add(v)
```
**普通工单真实主键池**：`storeHandle=liyanda6` ｜ `merchantId=li0106@123.com` ｜ `merchantName=739166802@qq.com` ｜ `email=213@wqec.com`

### 2.4 探索踩坑与解法（其他模块大概率会再遇）
| 坑 | 解法 |
|----|------|
| antd Select 普通 click 不打开 | 在 `.ant-select-selector` 派发 `mousedown+mouseup` |
| 弹窗字段 id 与列表筛选框冲突（#issueName） | 用 `.ant-modal` 作用域定位，或先 eval 打独立 id |
| React 受控输入合成 fill 不进 Form state | CDP 真实键盘：`select()全选 + Input.insertText`（中文必须 insertText）→ 已封装 `~/AI-TEST/api-flows/_toolkit/cdp_type.py` |
| tags 输入（店铺Handle） | insertText 后在元素上派发 Enter |
| recorder ws 超时退出 | 关键抓包前 `nohup python3 recorder.py <session> &` 重启（追加写不丢） |
| 弹窗底部按钮点不中 | `.ant-modal-footer .ant-btn-primary` |

---

## 三、读源码补全阶段（master 代码）

### 3.1 接口全集来源
路由文件 `web/router/cs/cs_router.go`（PC）/ `cs_h5_router.go`（H5）。普通工单模块 = 4 域共 29 接口：
- normal(7) / base(8) / config(9) / notify(5)

### 3.2 三 Agent 并行读（结构化输出）
| Agent | 读 | 输出 |
|-------|----|------|
| A | controller + vo + enum | 每接口入参出参结构、枚举 code、binding 校验 |
| B | base/config/notify service | 模板 CRUD 校验链、通知配置、文件上传、删除状态门 |
| C | normal save/query/sync service | submitType、MULTI 多人审批、并发锁、状态流转、同步补偿 |

**关键产出**：模板 save 校验链（NO_AUTH→NAMELIST_CONFIG_MUST_PRIMARY→地区重复→名称不可改）、审批 MULTI 首/末签判定、`approve/notify` 同步补偿、6 项代码缺陷。

### 3.3 接口差距（代码 vs 探索抓到）
代码 29 接口，探索只抓到 15 个，漏抓 14 个（模板 save/delete、文件上传、通知配置全套、同步补偿、角色查询等）—— 全部由读码补进 flow-supplement。

---

## 四、参数记录（其他模块替换这些即可复用）

| 参数 | 值 | 说明 |
|------|----|----|
| base_url | `https://test-risk.inshopline.com` | 换模块改这里 |
| 鉴权头 | `appId:4`、`version:v2` + Cookie | Cookie 走 `{{ENV:RISK_COOKIE}}` |
| 操作人 | riskUserId=253 (liyanda) | approvalList/creatorId 用 |
| 审批人 | 253 (liyanda，运营 RISK_OPERATOR) | 单级审批默认 |
| 模板 configId | 动态建（每次 flow-all-types 自建自删） | 名单库 code=SLM00304 |
| 真实主键池 | 见 2.3 | 爬列表所得 |
| 名单库 code | SLM00304（从 config/103 读到） | nameListConfig 用 |
| run_id | runner 自动注入（时间戳） | 实体名唯一 |
| 提交类型 | submitType=ADD(待审批)/SUBMIT(待提交) | ADD 可直接审批 |
| 审批结果 | approveStatus=SUCCESS/REJECT | （代码未严格校验，传 ABC 也走通过——缺陷） |

### 链式提取坑（重要）
- `save` 响应 `$.data` 返回**数字** issueId；`edit/approve` 的 body issueId 后端要 **string**。
- 解法：detail 步骤 `extract issue_id: "$.data.issueId"`（详情里是字符串）覆盖成 string。
- 模板 save 响应 `data:true`**不返回 id** → 用 list 按名称查回 configId。
- 模板编辑是「软删旧+插新版本」，原 configId 失效 → edit 后重新 list 查最新 id 再 delete。

---

## 五、接口用例全景（65 step，全绿）

| flow | step | 覆盖 | 状态 |
|------|------|------|------|
| `flow.yaml` | 7 | 主链路 CRUD（其他类型）：enums→create→detail→list→edit→approve→delete | ✅ 7/7 |
| `flow-supplement.yaml` | 23 | 14 漏抓接口 happy-path + 负向（NO_AUTH/地区重复/并发锁/非末级改抄送/非法枚举） | ✅ 23/23 |
| `flow-all-types.yaml` | 35 | **5 种 subIssueType 全枚举**：每类型建专属模板→建工单(真实主键)→审批完结→清理 | ✅ 35/35 |

### 5 类型差异（flow-all-types 参数化）
| subIssueType | 模板主键 | 工单主键值 | 完结行为 |
|---|---|---|---|
| OTHER | storeHandle | liyanda6 | 不同步 |
| NAME_LIST_APPLY | merchantId,merchantName,storeHandle | li0106@123.com | BatchAddWords 写名单库 |
| NAME_LIST_DELETE | merchantId | li0106@123.com | BatchDeleteWords |
| MERCHANT_ONBOARDING | merchantId,merchantName | li0106@123.com + merchantName | BatchAddWords |
| BRAND_PROTECTION | sellerId,merchantId,merchantName | li0106@123.com + brandType/品牌名/有效期 | 品牌授权(若 IsWriteQualification=1) |

**复跑**：`RISK_COOKIE=$(cat /tmp/risk_cookie.txt) python3 runner.py flow-all-types.yaml`

---

## 六、UI 用例全景（9 场景）

### 执行器 `ui/ui_runner.py`（可复用，封装了 antd 操作 helper）
helper：`nav/wait/ev/shot/click_text/open_select_nth/select_opt/type_real(真实键盘)/tag_enter/footer_primary/row_action`。
→ 这些 helper 是**通用的**，换模块只需改 BASE/路径/场景步骤。

### 9 场景执行结果（13 PASS / 0 FAIL / 1 PARTIAL）
| 场景 | 结果 | 截图 |
|---|---|---|
| S1 列表查询筛选 | ✅ 4/4 | S1-01~04 |
| S2 新建工单（弹窗+下拉+真实输入+tags） | ✅ 2/2 | S2-01~03 |
| S3 查看详情 | ✅ | S3-01 |
| S4 编辑抄送 | ✅ | S4-01~02 |
| S5 审批通过 | ✅ | S5-01~02 |
| S6 审批驳回 | ✅ | S6-01 |
| S7 删除 | ⚠️ PARTIAL（确认弹窗时序；接口层已验证+残留已清理） | S7-01 |
| S8 我已审批 | ✅ | S8-01 |
| S9 模版管理 | ✅ 2/2 | S9-01~02 |

---

## 七、过程记录与产物清单

### 7.1 执行证据
- `reports/执行报告-flow-all-types.md`（233 行，每步请求+响应+PASS）— 接口层证据链
- `tests/ui-exec-result.json` + 17 张 UI 截图（`screenshots//`）— UI 层证据
- `普通工单-测试报告.html`（综合：概览/接口矩阵/5类型/探索截图墙/缺陷）
- `普通工单-UI执行报告.html`（UI 执行结果+实跑截图）

### 7.2 探索过程截图（10 张，`screenshots/_shot_*.png（各模块自己的 screenshots/ 下）`）
nwo_init(列表) / newform~3(新建弹窗) / detail(详情) / mydetail / edit / tpl(模板列表) / newtpl(模板表单) / dd1(枚举)

### 7.3 留痕样本（未删，待核对）
工单 **6166**(名单申请,已完结) / **6167**(品牌保护,已完结) + 模板 **826/827**。
核对：`/list/detail/6166`、`/list/detail/6167`，或模版管理搜 `[KEEP]`。核对后删除。

### 7.4 数据清理记录
- 接口跑建过：工单 6147/6148/6149/6150/6151~6167、模板 802~827 —— **全部已清理删除**（仅留 6166/6167/826/827 作留痕）。
- 规则：所有自建数据带 `[FLOW]`/`[KEEP]` 标记，跑完即删，零残留。

---

## 八、发现的代码缺陷（6 项，建议提单）
1. `issue_approve_status_enum.go` pendingApproveEnum.Desc 写成"已驳回"（应为待审批）
2. 通知配置 VO 字段 `taskTame`（应为 taskName）贯穿全栈
3. 通知配置 save 的 IssueType 硬编码 PUNISH
4. 通知配置 save 几乎无校验（可造脏数据）
5. approve approveStatus 未严格枚举校验（传 ABC 也通过）
6. 文件上传无大小/MIME/数量白名单

---

## 九、功能用例（108 条）
`普通工单-功能测试用例-2026-08-01.md` / `.xlsx`（P0×33 / P1×50 / P2×25）
- 001~051：探索所得（列表/新建/详情/编辑/审批/删除/模板，8 模块）
- 052~097：代码补充（MULTI审批/并发锁/状态门/权限门/模板校验链/同步补偿）
- 098~108：5 类型差异（名单同步/品牌字段/商家入驻拼接/同步周期/brandAuthorize）

---

## 十、★ 延伸到其他模块的 Checklist

**可直接复用（不用改）**：
- `~/AI-TEST/api-flows/_toolkit/cdp_type.py`（antd 受控输入助手）
- `ui/ui_runner.py` 的 helper 函数集（nav/click_text/open_select/type_real/...）
- flow.yaml 的参数化结构（base_url/cookie/run_id/extract 链式）
- 四阶段方法论

**按模块替换**：
1. `base_url` + 路径前缀（如换成 `/risk-cooperation/cs/punish-issue`）
2. Cookie（重新 CDP 提取，或同 profile 已登则复用）
3. 爬该模块列表拿**该模块的真实业务数据池**（主键/商家/店铺等）
4. 读该模块的 `router` → 接口全集；Agent 读该域 `service/vo/enum` → 校验分支
5. flow-all-types 的**枚举类型**换成该模块的（如处罚工单的子类型）
6. UI 场景的页面 URL + 元素描述

**标准步骤**：
```
1. launch_chrome + recorder + cdp 探索 → 功能地图 + 抓包
2. CDP 提 cookie / 爬列表拿真实数据池
3. 读 router + 3 Agent 读 service/vo/enum → 接口差距 + 分支清单
4. 编 flow.yaml(主链路) + flow-supplement(漏接口+负向) + flow-all-types(枚举覆盖)
5. runner 跑接口全绿（先 dry-run 验渲染，再实跑）
6. ui_runner 跑 UI 9 场景 + 截图
7. 生成 HTML 报告 + 执行报告 + 清理残留
```

**下一个模块建议**：同在 cs 平台的 **处罚工单(punish-issue)** 或 **外部投诉工单(complaint)**，路由已在 `cs_router.go` 读到（punish 19 接口 / complaint 7 接口），复用本手册的 cookie/工具/方法论，只需换路径+爬该模块数据池+读对应 service。
