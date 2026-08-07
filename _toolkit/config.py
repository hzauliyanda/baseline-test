#!/usr/bin/env python3
"""api-flows 配置加载器。
脚本统一 `from config import load, abspath, octopuses_token` 读环境/租户/平台参数，去硬编码。
config.yaml 在 api-flows 根（本文件的上一级目录）。"""
import os, yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(os.path.dirname(_HERE), "config.yaml")   # api-flows/config.yaml


def load(path=CONFIG_PATH):
    if not os.path.exists(path):
        raise SystemExit(f"缺配置文件 {path}\n  → cp config.example.yaml config.yaml 后填值")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    r = cfg.get("root", "auto")
    cfg["_root"] = os.path.dirname(os.path.abspath(path)) if r in (None, "auto", "") else os.path.expanduser(r)
    return cfg


def abspath(cfg, rel):
    """相对 root 的路径 → 绝对路径；已是绝对路径则原样返回。"""
    return rel if os.path.isabs(rel) else os.path.join(cfg["_root"], rel)


def octopuses_token(cfg):
    """token 优先取环境变量，回退到 config。"""
    oc = cfg.get("octopuses", {}) or {}
    return os.environ.get(oc.get("token_env", "OCTOPUSES_TOKEN"), oc.get("token", ""))


if __name__ == "__main__":
    c = load()
    print("root =", c["_root"])
    print("systems =", list((c.get("systems") or {})))
    print("uploads =", len(c.get("uploads", [])), "条")
    print("octopuses.token =", ("<env/config 已设>" if octopuses_token(c) else "<空>"))
