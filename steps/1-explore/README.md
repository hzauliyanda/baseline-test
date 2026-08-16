# 第①步 tc-explore：双源探索建基线

① 是四步里唯一没有「一键脚本」的——代码扫描和抓包可以机算，但**页面遍历、
圈选模块相关枚举、判断行为分叉是 LLM+浏览器的活**。本目录把能机算的做成工具，
其余固化成操作顺序。

## 工具

| 工具 | 干什么 |
|---|---|
| `new-module.sh <模块根> [--backend 仓] [--frontend 仓] [--title 中文名]` | 脚手架：目录骨架 + baseline.yaml（origin url 与 audit_base=分支@HEAD 自动填，消灭⏳待回填）+ ③模板五件套 + coverage 模板 |
| `scan_repos.py <模块根> [--api-prefix /mapi/xx] [--frontend-key 关键词]` | 双源扫描 → `explore/` 三份 draft：backend-endpoints / enums-draft（含前端交叉引用）/ frontend-pages |
| `capture_ego.sh <session> reload\|goto <url>\|drain` | ego-browser 抓包（cdp Network.enable + drainEvents + getResponseBody，产出 capture/*.jsonl；不依赖任何独立 CDP 工具链） |

## 操作顺序（新模块从零到①完成）

1. **脚手架**：`new-module.sh ~/my-modules/xxx --backend <后端仓> --frontend <前端仓> --title 中文名`
   - audit_base 自动取**本地仓当前分支@HEAD**——若本地在 feature 分支上，先切回
     master/main 再跑脚手架（或事后手改 baseline.yaml），否则审计基准锚在别人feature上
2. **双源扫描**：`scan_repos.py ~/my-modules/xxx --api-prefix /mapi/<模块> --frontend-key <模块路由关键词>`
   - 扫描器输出**全集**（实测后端 168 枚举维度/3443 值），圈选是下一步人的活
   - 已知形态支持：beego 注释路由（`// @Post /mapi/...`）、`_type.EnumType{Code,Desc}`
     与 const 字符串枚举（行尾注释当 desc）、前端 `config/routes.ts`；
     其它框架的仓由①人工 grep 补，draft 里 note 记一笔
3. **ego 页面遍历**（ego-browser 已登录目标系统）：
   - `capture_ego.sh <模块名> goto <入口URL>` 抓首屏接口；逐页面导航 + `drain` 收集
   - 点按钮→抓接口属交互型：agent 在 ego heredoc 里 enable→点击→drain（每动作一轮）
   - 字典 API（如 `/base/enums`）的响应必抓——它是枚举维度表的**运行时口径**
4. **合成三件产物**：
   - `功能地图.md`：页面结构（前端 draft + 实走）× 接口表（backend draft + 实抓）×
     **枚举维度表** = 从 enums-draft 圈选模块相关维度 + 字典 API 口径对照 + 补
     `behavior_branch` 列（不同值是否走不同代码分支——决定②要不要加组合用例）。
     **扫描器与字典 API 的差异本身要记录**（如状态码 5/6/7/11 只在代码里，
     字典 API 不返回——它们是内部态还是可达态，①要下结论）
   - `baseline.yaml`：脚手架已生成，核对 entry_url/title/artifacts
   - `auto/api/flow.yaml` 初版：从 capture/*.jsonl 挑主链路，参数化（`{{run_id}}` 等），
     断言先全标 ⏳待首跑回填（②/首跑后再锁，不许伪装已验证）
5. **不相关维度显式排除**：enums-draft 里圈剩的维度在 note 里记「排除：非本模块」，
   不许静默丢

## 完成标志（②的输入）

- `baseline.yaml`：repos × 2 的 url/local/audit_base 全实值（无⏳）
- `功能地图.md`：含枚举维度表（维度 × 取值 × code ref × 行为分叉?）+ 页面/接口清单
- `auto/api/flow.yaml`：主链路可执行初版
- `explore/` 三份 draft 在仓（可复算、可审计）

## 已实测（2026-08-16，普通工单金标准仓）

- scan_repos.py 真仓验证：模板类型 5 值与功能地图**逐值一致**；工单状态扫出 10 码
  （比字典 API 多 4 个内部态 5/6/7/11，desc 全中）——扫描器全集 > 运行时口径，
  差异即待确认项；主键枚举 6 值带中文；46 个 `/mapi/cs/issue` endpoint；
  前端 10 条模块路由；模板类型 code 交叉命中 src/common/cs.ts + add-template 页
- capture_ego.sh：2026-08-14 PoC + test-risk 真系统验证（7 记录/5 mapi 全
  code=SUCCESS），自 api-flow-recorder 移植，仅改输出根路径为模块目录
