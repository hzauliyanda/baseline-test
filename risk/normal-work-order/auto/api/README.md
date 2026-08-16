# 双轨制完成总结

## ✅ 已实现

### 1. 转换器 `flow2cases.py`
- 读取所有 flow yaml 文件（5 个文件，共 136 个步骤）
- 生成 octopuses 标准格式的 `cases.json`（树状结构）
- 生成分支覆盖矩阵 `branch_matrix.json`（可选）
- 自动生成 BeanShell 断言代码
- 处理 DB 校验（转为注释）
- 转换占位符格式：`{{base_url}}` → `${risk_normal_work_order_base_url}`

### 2. 校验通过
```
cases: 136
token placeholder: ${risk_normal_work_order_token}
base URL placeholder: ${risk_normal_work_order_base_url}
variable prefix: risk_normal_work_order_
Warnings: Authorization header missing（Cookie 认证，可忽略）
```

### 3. 文档完善
- `FLOW2CASES.md`：详细使用说明
- `auto/api/README.md`：双轨制总结
- 更新 memory `risk-normal-work-order-baseline.md`

## 🚀 使用流程

### 本地回归（不变）
```bash
# 1. 跑 API 回归
python3 auto/api/api_runner.py

# 2. 跑 UI 回归
npm test

# 3. 生成总览报告
python3 gen_report.py
```

### 生成测试平台用例（新增）
```bash
# 1. 生成 cases.json 和 branch_matrix.json
python3 auto/api/flow2cases.py --with-branch-matrix

# 2. 校验（可选）
cd ~/ai-skills-test-generator/api-test-generator
python3 scripts/validate_cases.py \
  --input /Users/liyanda/baseline-test/risk/normal-work-order/auto/api/cases.json \
  --project risk_normal_work_order

# 3. 上传到测试平台（需要 upload_cases.py）
python3 scripts/upload_cases.py \
  --input /Users/liyanda/baseline-test/risk/normal-work-order/auto/api/cases.json \
  --pid 0 \
  --pre-case-ids 12345 \
  --dry-run  # 先预检
```

## 📊 生成的文件

### cases.json
- 136 个用例，分为 5 个模块：
  - 基础CRUD（7 个）
  - 全类型覆盖（35 个）
  - 补充场景（23 个）
  - 路径覆盖（21 个）
  - 负向用例（50 个）
- 每个用例包含：
  - method、address、request_headers、request_body
  - bean_shell_assertion（自动生成）
  - 扩展字段：branch_ids、source_trace、oracle_type 等

### branch_matrix.json
- 记录每个源码分支的验证方式
- 用于覆盖率评估和代码变更影响分析

## 🔧 扩展字段（可选）

如果需要更精细的分支追踪，可以在 flow yaml 中添加扩展字段：

```yaml
steps:
  - id: create
    desc: 创建工单
    # ... request, assert, db_check ...

    # 扩展字段
    branch_id: "issue.create.success"
    source_trace: ["save.go:CreateIssue"]
    oracle_type: "follow-up-api"
    verification_strategy: "follow-up-load"
    assertion_level: "strong"
    assertion_targets: ["issueStatus", "issueId"]
    preconditions: ["用户已登录"]
    postconditions: ["工单状态=待审批"]
```

## 🎯 下一步

### 可选优化
1. **添加前置用例支持**：解析 pre-case 的 vars.put() 和 host 变量
2. **提升断言强度**：为关键用例添加 strong 断言
3. **DB 校验自动化**：把 db_check 转成真正的数据库查询用例
4. **集成上传脚本**：把 api-test-generator 的 upload_cases.py 集成进来

### 使用场景
- **每轮回归**：继续用 `api_runner.py`，不变
- **首次导入平台**：生成 `cases.json`，上传一次
- **平台维护**：新增/修改用例时，重新生成并上传

## 📝 关键点

1. **兼容性**：扩展字段都是可选的，不影响现有回归流程
2. **占位符**：`{{base_url}}`、`{{cookie}}` 等占位符会自动转换为平台格式
3. **DB 校验**：转为 BeanShell 注释，需要人工确认或额外处理
4. **Cookie 认证**：校验器的 "Authorization header missing" 警告可忽略（风控系统用 Cookie）

## 🎉 总结

成功实现了双轨制：
- ✅ 本地回归继续使用 flow yaml
- ✅ 生成测试平台可导入的 cases.json
- ✅ 校验通过，格式符合标准
- ✅ 文档完善，使用流程清晰

现在风控普通工单的用例既可以用于本地回归，也可以导入到测试平台！
