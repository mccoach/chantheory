# scripts/guards/check_invariants.py
# ===============================
# 说明：关键不变量机检（静态包含，不使用正则）
# - 任何文件不存在或缺失关键片段 → 失败（退出码 2）
# - 默认自动推断仓库根；配置文件默认 scripts/guards/invariants.json
# ===============================

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import sys

def norm(p: str) -> str:
    return p.replace("\\", "/")

def guess_repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))

def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=guess_repo_root(), help="仓库根目录路径（默认自动推断）")
    ap.add_argument("--config", default="scripts/guards/invariants.json", help="invariants.json 路径")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo_root)
    cfg_path = os.path.join(repo, args.config)
    if not os.path.exists(cfg_path):
        print(f"[INVARIANTS] 配置文件不存在: {cfg_path}", file=sys.stderr)
        return 2

    cfg = load_json(cfg_path)
    files = cfg.get("files") or []
    if not files:
        print("[INVARIANTS] 配置中无 files 条目", file=sys.stderr)
        return 2

    failed = []
    for item in files:
        rel = norm((item.get("path") or "").strip())
        must = item.get("mustContain") or []
        if not rel:
            failed.append("配置项缺少 path")
            continue
        abs_path = os.path.join(repo, rel)
        if not os.path.exists(abs_path):
            failed.append(f"[缺文件] {rel}")
            continue
        try:
            content = read_text(abs_path)
        except Exception as e:
            failed.append(f"[读失败] {rel}: {e}")
            continue
        for token in must:
            if token not in content:
                failed.append(f"[缺标记] {rel} :: {token}")

    if failed:
        print("==== INVARIANTS CHECK FAIL ====", file=sys.stderr)
        for msg in failed:
            print(msg, file=sys.stderr)
        print("================================", file=sys.stderr)
        return 2

    print("[INVARIANTS] All OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
