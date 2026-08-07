#!/usr/bin/env python3
"""CDP 真实输入：select() 全选 + Input.insertText 替换（支持中文，触发 React onChange）。
用法: python3 cdp_type.py "<css选择器>" "<文本>" [enter]   # 第三个参数任意值则末尾按回车(tags 选择器用)"""
import sys, json, os
# 去硬编码：可用 API_FLOW_RECORDER_SCRIPTS 覆盖，默认取当前用户 ~/.claude 下的 skill 脚本
sys.path.insert(0, os.environ.get("API_FLOW_RECORDER_SCRIPTS",
                os.path.expanduser("~/.claude/skills/api-flow-recorder/scripts")))
from cdplib import connect

def main():
    sel = sys.argv[1]
    text = sys.argv[2]
    press_enter = len(sys.argv) > 3
    cdp, _port, _page = connect()
    # 真实鼠标点击中心聚焦
    rect = cdp.evaluate(
        "(function(){const el=document.querySelector(%r);if(!el)return 'null';"
        "el.scrollIntoView({block:'center'});el.focus();"
        "if(el.select)el.select();"      # 全选，insertText 会替换
        "const r=el.getBoundingClientRect();"
        "return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});})()" % sel
    )
    if not (isinstance(rect, str) and rect != 'null'):
        print("NOT FOUND"); cdp.close(); return
    box = json.loads(rect)
    cdp.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box["x"], "y": box["y"]})
    cdp.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": box["x"], "y": box["y"], "button": "left", "clickCount": 1})
    cdp.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": box["x"], "y": box["y"], "button": "left", "clickCount": 1})
    # 真实文本插入（替换当前选区，支持中文，React 必捕获）
    cdp.cmd("Input.insertText", {"text": text})
    if press_enter:
        cdp.cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        cdp.cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    val = cdp.evaluate("(function(){const el=document.querySelector(%r);return el?(el.value||el.textContent||''):'NF';})()" % sel)
    print("typed ->", val)
    cdp.close()

if __name__ == "__main__":
    main()
