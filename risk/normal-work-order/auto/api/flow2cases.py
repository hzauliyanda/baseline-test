#!/usr/bin/env python3
"""
Convert flow yaml files to octopuses-compatible cases.json

Usage:
    python flow2cases.py                           # Generate cases.json from all flow yaml files
    python flow2cases.py --output custom.json     # Custom output path
    python flow2cases.py --flat                   # Emit {cases:[...]} instead of tree structure

Output:
    auto/api/cases.json         # Octopuses import format
    auto/api/branch_matrix.json # Branch coverage matrix (optional)
"""

import json
import os
import re
import sys
import yaml
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).parent.parent.parent
FLOW_DIR = BASE_DIR / "auto" / "api"
OUTPUT_FILE = FLOW_DIR / "cases.json"
BRANCH_MATRIX_FILE = FLOW_DIR / "branch_matrix.json"

FLOW_FILES = [
    "flow.yaml",
    "flow-all-types.yaml",
    "flow-supplement.yaml",
    "flow-paths.yaml",
    "flow-negative.yaml",
]

# Octopuses BeanShell assertion templates
ASSERTION_TEMPLATES = {
    "success": """import com.alibaba.fastjson.JSONObject;

JSONObject response = JSONObject.parseObject(responseBody);
String outerCode = response.getString("code");
boolean isSuccessCode = "SUCCESS".equals(outerCode) || "200".equals(outerCode);
if (!isSuccessCode) {{
    Failure = true;
    FailureMessage = "接口外层code=" + outerCode + ", message=" + response.getString("message");
    return;
}}

JSONObject data = response.getJSONObject("data");
if (data == null) {{
    Failure = true;
    FailureMessage = "接口返回data为空";
    return;
}}

{business_assertions}

Failure = false;""",

    "error": """import com.alibaba.fastjson.JSONObject;

JSONObject response = JSONObject.parseObject(responseBody);
String outerCode = response.getString("code");
boolean isSuccessCode = "SUCCESS".equals(outerCode) || "200".equals(outerCode);
if (isSuccessCode) {{
    Failure = true;
    FailureMessage = "应返回错误, 但返回成功";
    return;
}}

String message = response.getString("message");
if (message == null) {{ message = ""; }}
{error_assertions}

Failure = false;""",
}


def json_path_to_beanshell(path: str, condition: str, expected: Any) -> str:
    """Convert JSON path assertion to BeanShell code"""
    if not path or path == "$.code":
        return ""  # Already handled in template

    # Extract field name from path
    # e.g., "$.data.issueId" -> "issueId"
    # e.g., "$.data.list[0].issueName" -> "issueName"
    parts = path.replace("$.data.", "").replace("$.", "").split(".")
    field_name = parts[0].replace("[", "").replace("]", "")

    if condition == "exists":
        return f"""String {field_name} = data.getString("{field_name}");
if ({field_name} == null || {field_name}.isEmpty()) {{
    Failure = true;
    FailureMessage = "{field_name} 不应为空";
    return;
}}"""

    elif condition == "equals":
        return f"""String {field_name} = data.getString("{field_name}");
if (!"{expected}".equals({field_name})) {{
    Failure = true;
    FailureMessage = "{field_name} 期望值: {expected}, 实际值: " + {field_name};
    return;
}}"""

    elif condition == "contains":
        return f"""String {field_name} = data.getString("{field_name}");
if ({field_name} == null || !{field_name}.contains("{expected}")) {{
    Failure = true;
    FailureMessage = "{field_name} 应包含: {expected}, 实际值: " + {field_name};
    return;
}}"""

    return ""


def generate_beanshell_assertion(step: Dict[str, Any]) -> str:
    """Generate BeanShell assertion from step.assert config"""
    assert_cfg = step.get("assert", {})
    if not assert_cfg:
        return "// No assertion configured"

    # Determine if this is a success or error case
    expected_status = assert_cfg.get("status", 200)
    is_error_case = expected_status != 200

    template = ASSERTION_TEMPLATES["error"] if is_error_case else ASSERTION_TEMPLATES["success"]

    # Generate business assertions
    business_assertions = []
    for rule in assert_cfg.get("json", []):
        path = rule.get("path", "")
        condition = list(rule.keys() - {"path"})[0] if len(rule) > 1 else "exists"
        expected = rule.get(condition)

        assertion = json_path_to_beanshell(path, condition, expected)
        if assertion:
            business_assertions.append(assertion)

    # Handle db_check notes (add as comments)
    db_checks = step.get("db_check", [])
    if db_checks:
        business_assertions.append("\n// DB 校验（需人工确认或额外数据库查询）:")
        for check in db_checks:
            table = check.get("table", "")
            sql = check.get("sql", "")
            reason = check.get("reason", "")
            business_assertions.append(f"// Table: {table}")
            business_assertions.append(f"// SQL: {sql}")
            business_assertions.append(f"// Expect: {reason}")

    business_assertion_text = "\n".join(business_assertions) if business_assertions else "// 无额外业务断言"

    if is_error_case:
        # For error cases, add error code/message checks
        error_assertions = []
        for rule in assert_cfg.get("json", []):
            if "contains" in rule:
                error_assertions.append(f"""if (!message.contains("{rule['contains']}")) {{
    Failure = true;
    FailureMessage = "错误响应未包含预期错误信息: {rule['contains']}, 实际message: " + message;
    return;
}}""")
        error_assertion_text = "\n".join(error_assertions) if error_assertions else "// 无特定错误码检查"
        return template.format(error_assertions=error_assertion_text)

    return template.format(business_assertions=business_assertion_text)


def convert_headers(headers: Dict[str, str], case_index: int) -> List[Dict[str, Any]]:
    """Convert headers dict to octopuses format"""
    result = []
    header_id = f"h{case_index:02d}"

    # Default headers
    if not headers:
        return [
            {"id": f"{header_id}-1", "key": "Content-Type", "value": "application/json", "description": "", "shareMode": False},
        ]

    for idx, (key, value) in enumerate(headers.items(), 1):
        result.append({
            "id": f"{header_id}-{idx}",
            "key": key,
            "value": value,
            "description": "",
            "shareMode": False,
        })

    return result


def normalize_placeholders(url: str, headers: Dict[str, str], body: Any) -> tuple:
    """Normalize flow yaml placeholders to octopuses format"""
    # Replace flow yaml placeholders with octopuses format
    url = url.replace("{{base_url}}", "${risk_normal_work_order_base_url}")

    normalized_headers = {}
    for key, value in headers.items():
        if "{{cookie}}" in str(value):
            normalized_headers[key] = value.replace("{{cookie}}", "${risk_normal_work_order_token}")
        elif "{{base_url}}" in str(value):
            normalized_headers[key] = value.replace("{{base_url}}", "${risk_normal_work_order_base_url}")
        else:
            normalized_headers[key] = value

    # Replace placeholders in body
    if isinstance(body, dict):
        body_str = json.dumps(body, ensure_ascii=False)
        body_str = body_str.replace("{{base_url}}", "${risk_normal_work_order_base_url}")
        body_str = body_str.replace("{{cookie}}", "${risk_normal_work_order_token}")
        # Replace other placeholders like {{issue_id}}, {{run_id}} etc
        body_str = re.sub(r'\{\{(\w+)\}\}', r'${risk_normal_work_order_\1}', body_str)
        body = json.loads(body_str)

    return url, normalized_headers, body


def convert_step_to_case(step: Dict[str, Any], flow_name: str, case_index: int) -> Dict[str, Any]:
    """Convert a single step to octopuses case format"""
    step_id = step.get("id", "")
    desc = step.get("desc", "")
    request = step.get("request", {})

    method = request.get("method", "GET")
    url = request.get("url", "")
    headers = request.get("headers", {})
    body = request.get("json", request.get("body", {}))

    # Normalize placeholders to octopuses format
    url, headers, body = normalize_placeholders(url, headers, body)

    # Convert body to JSON string
    request_body = json.dumps(body, ensure_ascii=False) if isinstance(body, (dict, list)) else str(body) if body else ""

    # Generate BeanShell assertion
    bean_shell = generate_beanshell_assertion(step)

    # Extract extended fields if present
    branch_id = step.get("branch_id", f"{flow_name}.{step_id}")
    source_trace = step.get("source_trace", [])
    oracle_type = step.get("oracle_type", "response")
    verification_strategy = step.get("verification_strategy", "inline")
    assertion_level = step.get("assertion_level", "medium")
    assertion_targets = step.get("assertion_targets", [])
    preconditions = step.get("preconditions", [])
    postconditions = step.get("postconditions", [])

    case = {
        "name": f"{flow_name}-{step_id}: {desc}",
        "type": "CASE",
        "method": method,
        "address": url,
        "request_headers": convert_headers(headers, case_index),
        "request_body": request_body,
        "bean_shell_assertion": bean_shell,
        "description": desc,
        "tags": [],
        # Extended fields for branch tracking
        "branch_ids": [branch_id],
        "source_trace": source_trace,
        "oracle_type": oracle_type,
        "verification_strategy": verification_strategy,
        "assertion_level": assertion_level,
        "assertion_targets": assertion_targets,
        "preconditions": preconditions,
        "postconditions": postconditions,
    }

    return case


def generate_branch_matrix(steps: List[Dict[str, Any]], flow_name: str, source_summary: str) -> Dict[str, Any]:
    """Generate branch matrix from steps"""
    branches = []

    for step in steps:
        step_id = step.get("id", "")
        desc = step.get("desc", "")
        branch_id = step.get("branch_id", f"{flow_name}.{step_id}")
        source_trace = step.get("source_trace", [])
        oracle_type = step.get("oracle_type", "response")
        assertion_targets = step.get("assertion_targets", [])

        # Determine if this is a negative case
        assert_cfg = step.get("assert", {})
        expected_status = assert_cfg.get("status", 200)
        is_negative = expected_status != 200

        # Extract oracle targets
        oracle_targets = assertion_targets if oracle_type == "response" else []

        branch = {
            "branch_id": branch_id,
            "source_trace": source_trace if source_trace else [f"flow/{flow_name}.yaml:{step_id}"],
            "condition": desc,
            "expected_behavior": step.get("postconditions", ["接口返回成功"])[0] if not is_negative else f"返回错误: {desc}",
            "oracle": {
                "type": oracle_type,
                "targets": oracle_targets,
                "query": step.get("db_check", [{}])[0].get("sql", "") if oracle_type == "database" else "",
                "notes": f"verification_strategy={step.get('verification_strategy', 'inline')}"
            },
            "required": not is_negative,
            "negative": is_negative,
            "data_requirements": step.get("setup_plan", []),
        }
        branches.append(branch)

    return {
        "project": "risk-normal-work-order",
        "feature": flow_name,
        "source_summary": source_summary,
        "branches": branches,
    }


def load_flow_yaml(filepath: Path) -> Dict[str, Any]:
    """Load and parse a flow yaml file"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Failed to load {filepath}: {e}", file=sys.stderr)
        return {}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Convert flow yaml to octopuses cases.json")
    parser.add_argument("--output", "-o", default=str(OUTPUT_FILE), help="Output cases.json path")
    parser.add_argument("--flat", action="store_true", help="Emit {cases:[...]} instead of tree")
    parser.add_argument("--with-branch-matrix", action="store_true", help="Also generate branch_matrix.json")
    args = parser.parse_args()

    # Load all flow files
    all_cases = []
    all_branches = []

    for flow_file in FLOW_FILES:
        filepath = FLOW_DIR / flow_file
        if not filepath.exists():
            print(f"⚠️  Skipping {flow_file} (not found)", file=sys.stderr)
            continue

        print(f"📖 Reading {flow_file}...")
        flow_data = load_flow_yaml(filepath)
        if not flow_data:
            continue

        flow_name = flow_data.get("name", flow_file.replace(".yaml", ""))
        flow_desc = flow_data.get("desc", "")
        steps = flow_data.get("steps", [])

        print(f"   Converting {len(steps)} steps...")

        # Convert each step to a case
        case_index = 1
        for step in steps:
            # Skip db_check-only and skip_note-only steps
            if not step.get("request"):
                continue

            case = convert_step_to_case(step, flow_name, case_index)
            all_cases.append(case)
            case_index += 1

        # Generate branch matrix for this flow
        if args.with_branch_matrix:
            branch_matrix = generate_branch_matrix(steps, flow_name, flow_desc)
            all_branches.append(branch_matrix)

    print(f"\n✅ Generated {len(all_cases)} cases")

    # Generate cases.json
    output_data = {}
    if args.flat:
        output_data["cases"] = all_cases
    else:
        # Build tree structure
        output_data["tree"] = [
            {
                "name": "风控普通工单",
                "type": "DIR",
                "children": [
                    {
                        "name": "基础CRUD",
                        "type": "DIR",
                        "children": [c for c in all_cases if c["name"].startswith("risk-normal-work-order-crud-")]
                    },
                    {
                        "name": "全类型覆盖",
                        "type": "DIR",
                        "children": [c for c in all_cases if c["name"].startswith("risk-normal-work-order-all-types-")]
                    },
                    {
                        "name": "补充场景",
                        "type": "DIR",
                        "children": [c for c in all_cases if c["name"].startswith("risk-normal-work-order-supplement-")]
                    },
                    {
                        "name": "路径覆盖",
                        "type": "DIR",
                        "children": [c for c in all_cases if c["name"].startswith("risk-normal-work-order-paths-")]
                    },
                    {
                        "name": "负向用例",
                        "type": "DIR",
                        "children": [c for c in all_cases if c["name"].startswith("risk-normal-work-order-negative-")]
                    },
                ]
            }
        ]

    # Write cases.json
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"📝 Wrote: {output_path}")

    # Write branch_matrix.json if requested
    if args.with_branch_matrix and all_branches:
        branch_matrix_path = output_path.parent / "branch_matrix.json"
        with open(branch_matrix_path, "w", encoding="utf-8") as f:
            json.dump({"matrices": all_branches}, f, ensure_ascii=False, indent=2)
        print(f"📝 Wrote: {branch_matrix_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
