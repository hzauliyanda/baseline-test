# Flow to Cases 转换器说明

## 功能

`flow2cases.py` 将 flow yaml 文件转换为可导入 octopuses 测试平台的 `cases.json` 和 `branch_matrix.json`。

## 使用方法

### 1. 生成测试平台用例

```bash
# 生成 cases.json（树状结构）
python3 auto/api/flow2cases.py

# 生成 cases.json（扁平结构）
python3 auto/api/flow2cases.py --flat

# 同时生成分支覆盖矩阵
python3 auto/api/flow2cases.py --with-branch-matrix

# 自定义输出路径
python3 auto/api/flow2cases.py --output /path/to/custom.json
```

### 2. 输出文件

- **`auto/api/cases.json`**：octopuses 测试平台导入格式
  - 树状结构：风控普通工单 → 基础CRUD/全类型覆盖/补充场景/路径覆盖/负向用例
  - 每个用例包含：method、address、request_headers、request_body、bean_shell_assertion
  - 扩展字段：branch_ids、source_trace、oracle_type、verification_strategy、assertion_level

- **`auto/api/branch_matrix.json`**（可选）：分支覆盖矩阵
  - 记录每个源码分支、条件、预期行为和验证方式
  - 用于评估覆盖率和追踪代码变更影响

### 3. 导入测试平台

```bash
# 使用 api-test-generator 的上传脚本
python3 ~/ai-skills-test-generator/api-test-generator/scripts/upload_cases.py \
  --input auto/api/cases.json \
  --pid 0 \
  --pre-case-ids 12345 \
  --dry-run  # 先预检，不实际上传
```

## 字段映射

### Flow YAML → Cases JSON

| Flow YAML 字段 | Cases JSON 字段 | 说明 |
|----------------|-----------------|------|
| `step.id` | `case.name` | 用例名称：`{flow_name}-{step_id}: {desc}` |
| `request.method` | `case.method` | GET/POST/PUT/DELETE/PATCH |
| `request.url` | `case.address` | 接口地址（保留占位符如 `{{base_url}}`） |
| `request.headers` | `case.request_headers` | 请求头数组 |
| `request.json` | `case.request_body` | 请求体（JSON 字符串） |
| `assert` | `bean_shell_assertion` | 自动生成 BeanShell 断言代码 |
| `db_check` | `bean_shell_assertion` 注释 | DB 校验转为注释，需人工确认 |
| `branch_id`（新增） | `branch_ids` | 源码分支标识 |
| `source_trace`（新增） | `source_trace` | 源码位置追踪 |
| `oracle_type`（新增） | `oracle_type` | 验证方式：response/follow-up-api/database/side-effect |
| `assertion_level`（新增） | `assertion_level` | 断言强度：weak/medium/strong |
| `assertion_targets`（新增） | `assertion_targets` | 断言目标字段列表 |

## BeanShell 断言生成

### 成功案例模板

```java
import com.alibaba.fastjson.JSONObject;

JSONObject response = JSONObject.parseObject(responseBody);
String outerCode = response.getString("code");
boolean isSuccessCode = "SUCCESS".equals(outerCode) || "200".equals(outerCode);
if (!isSuccessCode) {
    Failure = true;
    FailureMessage = "接口外层code=" + outerCode + ", message=" + response.getString("message");
    return;
}

JSONObject data = response.getJSONObject("data");
if (data == null) {
    Failure = true;
    FailureMessage = "接口返回data为空";
    return;
}

// 业务字段断言（从 assert.json 自动生成）
String issueId = data.getString("issueId");
if (issueId == null || issueId.isEmpty()) {
    Failure = true;
    FailureMessage = "issueId 不应为空";
    return;
}

// DB 校验注释（从 db_check 自动生成）
// Table: t_cs_issue
// SQL: SELECT issue_status FROM t_cs_issue WHERE id=<issue_id>;
// Expect: 工单真的进入待审批状态

Failure = false;
```

### 错误案例模板

```java
import com.alibaba.fastjson.JSONObject;

JSONObject response = JSONObject.parseObject(responseBody);
String outerCode = response.getString("code");
boolean isSuccessCode = "SUCCESS".equals(outerCode) || "200".equals(outerCode);
if (isSuccessCode) {
    Failure = true;
    FailureMessage = "应返回错误, 但返回成功";
    return;
}

String message = response.getString("message");
if (message == null) { message = ""; }
// 错误信息检查（从 assert.json contains 自动生成）
if (!message.contains("PARAMETER_EXCEPTION")) {
    Failure = true;
    FailureMessage = "错误响应未包含预期错误信息: PARAMETER_EXCEPTION, 实际message: " + message;
    return;
}

Failure = false;
```

## 扩展 Flow YAML（可选）

如果需要更精细的分支追踪和断言控制，可以在 step 中添加扩展字段：

```yaml
steps:
  - id: create
    desc: 创建工单
    request:
      method: POST
      url: "{{base_url}}/mapi/cs/issue/normal/save"
      # ...
    assert:
      status: 200
      json:
        - { path: "$.code", equals: "SUCCESS" }
        - { path: "$.data.issueId", exists: true }
    db_check:
      - table: t_cs_issue
        sql: "SELECT issue_status FROM t_cs_issue WHERE id=<issue_id>;"
        expect: "issue_status=1"
        reason: "工单真的进入待审批状态"

    # === 扩展字段（可选）===
    branch_id: "issue.create.success"              # 对应源码分支
    source_trace: ["save.go:CreateIssue"]          # 源码位置
    oracle_type: "follow-up-api"                   # 验证方式
    verification_strategy: "follow-up-load"        # 验证策略
    assertion_level: "strong"                      # 断言强度
    assertion_targets: ["issueStatus", "issueId"]  # 断言目标字段
    preconditions: ["用户已登录", "模板存在"]
    postconditions: ["工单状态=待审批", "日志表有记录"]
    setup_plan: ["创建模板", "准备用户"]
    cleanup_plan: ["删除工单", "恢复配置"]
```

## 双轨制流程

### 本地回归（现有方式，不变）

```bash
# 1. 跑 API 回归
python3 auto/api/api_runner.py

# 2. 生成回归报告
python3 gen_report.py
```

### 生成测试平台用例（新增）

```bash
# 3. 生成 cases.json
python3 auto/api/flow2cases.py --with-branch-matrix

# 4. 上传到测试平台（可选）
python3 ~/ai-skills-test-generator/api-test-generator/scripts/upload_cases.py \
  --input auto/api/cases.json \
  --pid 0 \
  --pre-case-ids 12345
```

## 注意事项

1. **兼容性**：扩展字段都是可选的，不影响现有回归流程
2. **占位符保留**：`{{base_url}}`、`{{cookie}}` 等占位符会保留到 cases.json，上传时由 pre-case 或环境变量替换
3. **DB 校验**：db_check 会转为 BeanShell 注释，需要人工确认或额外数据库查询
4. **BeanShell 禁止**：不能使用 `response.getIntValue("code")`，必须用 `getString` 模板
5. **断言强度**：默认为 medium，可以通过扩展字段提升为 strong
