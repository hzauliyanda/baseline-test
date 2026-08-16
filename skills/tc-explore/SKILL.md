---
name: tc-explore
description: >
  四步管道第①步：双源探索建基线。scan_repos.py 扫前后端仓（注释路由/枚举维度/
  前端路由 + 枚举交叉引用）出 draft，ego-browser 页面遍历实抓接口与字典 API，
  合成 baseline.yaml（audit_base 自动取当前 HEAD）+ 功能地图.md（含枚举维度表）+
  flow.yaml 初版。
  Use when: 用户说"探索这个模块""建基线""新模块接入""tc-explore""摸清这个系统"，
  或拿到一个没基线的新系统/新模块要开始测。前置：前后端仓本地路径 + 系统 URL +
  ego-browser 已登录。操作细节见 kit 仓库 steps/1-explore/README.md——本 skill 是
  触发壳，逻辑以它为准。
---

# tc-explore：双源探索建基线（第①步）

**先读 `<kit根>/steps/1-explore/README.md` 并照做**——壳内要点：

1. `new-module.sh <模块根> --backend <仓> --frontend <仓> --title <中文名>` 脚手架
2. `scan_repos.py <模块根> --api-prefix /mapi/<模块> --frontend-key <关键词>` 双源扫描
3. ego 页面遍历：`capture_ego.sh <session> goto|reload|drain` 抓接口；字典 API 必抓
4. 合成：功能地图（枚举维度表=圈选+补行为分叉列）/ baseline.yaml 核对 / flow.yaml
   初版（断言全标 ⏳，不伪装已验证）
5. 完成标志自查（README「完成标志」节）后才交给 ②tc-cases

## 纪律（硬性）

- 扫描器输出的是全集，圈选必须显式：不相关维度在 draft note 记「排除」，不许静默丢
- 扫描器与字典 API 的枚举差异（代码有/接口不回）必须记录并下结论（内部态 or 可达态）
- behavior_branch 列不许空着交②——判断不了就写「待定：原因」，②按待定处理
- flow.yaml 初版断言一律 ⏳待首跑回填；见过真实响应才能锁（②两段式断言规则）
