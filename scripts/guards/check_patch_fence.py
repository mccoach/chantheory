# scripts/guards/check_patch_fence.py
# ===============================
# 说明：Patch Fence（改动范围护栏）
# - 支持精确文件与目录白名单；支持本地覆盖 fence.local.json
# - 宽松模式：--lenient 或 FENCE_LENIENT=1 或 GUARDS_MODE=dev
# - 变更列表来源：--changed-files 或 --changed-files-file
# ===============================

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import sys

def norm_path(p: str) -> str:
    return p.replace("\\", "/").strip()

def load_json_safe(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def ensure_slash_suffix(d: str) -> str:
    d = norm_path(d)
    if not d.endswith("/"):
        d = d + "/"
    return d

def is_lenient(args) -> bool:
    if args.lenient:
        return True
    if os.getenv("FENCE_LENIENT", "").strip() in ("1", "true", "yes"):
        return True
    if os.getenv("GUARDS_MODE", "").strip().lower() == "dev":
        return True
    return False

def guess_repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=guess_repo_root(), help="仓库根目录（默认自动推断）")
    ap.add_argument("--config", default="scripts/guards/fence.json", help="主 fence.json 路径")
    ap.add_argument("--local-config", default="scripts/guards/fence.local.json", help="本地覆盖 fence.local.json 路径（可选）")
    ap.add_argument("--changed-files", help="以逗号分隔的变更文件列表（相对仓库根，正斜杠）")
    ap.add_argument("--changed-files-file", help="包含变更文件列表的文本文件（每行一个路径）")
    ap.add_argument("--lenient", action="store_true", help="宽松模式：越界仅警告、不拦截")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo_root)
    cfg_path = os.path.join(repo, args.config)
    cfg = load_json_safe(cfg_path)
    if not cfg:
        print(f"[FENCE] 配置文件不存在或解析失败: {cfg_path}", file=sys.stderr)
        return 3

    allow_add = set(norm_path(p) for p in (cfg.get("allowAdd") or []))
    allow_mod = set(norm_path(p) for p in (cfg.get("allowModify") or []))
    allow_del = set(norm_path(p) for p in (cfg.get("allowDelete") or []))

    allow_add_dirs = [ensure_slash_suffix(d) for d in (cfg.get("allowAddDirs") or [])]
    allow_mod_dirs = [ensure_slash_suffix(d) for d in (cfg.get("allowModifyDirs") or [])]
    allow_del_dirs = [ensure_slash_suffix(d) for d in (cfg.get("allowDeleteDirs") or [])]

    local_cfg_path = os.path.join(repo, args.local_config)
    local = load_json_safe(local_cfg_path) or {}
    allow_add |= set(norm_path(p) for p in (local.get("allowAdd") or []))
    allow_mod |= set(norm_path(p) for p in (local.get("allowModify") or []))
    allow_del |= set(norm_path(p) for p in (local.get("allowDelete") or []))
    allow_add_dirs += [ensure_slash_suffix(d) for d in (local.get("allowAddDirs") or [])]
    allow_mod_dirs += [ensure_slash_suffix(d) for d in (local.get("allowModifyDirs") or [])]
    allow_del_dirs += [ensure_slash_suffix(d) for d in (local.get("allowDeleteDirs") or [])]

    changed = []
    if args.changed_files:
        changed = [norm_path(x) for x in args.changed_files.split(",") if norm_path(x)]
    elif args.changed_files_file:
        list_path = args.changed_files_file
        if not os.path.isabs(list_path):
            list_path = os.path.join(repo, list_path)
        if not os.path.exists(list_path):
            print(f"[FENCE] 变更文件列表不存在: {list_path}", file=sys.stderr)
            return 3
        with open(list_path, "r", encoding="utf-8") as f:
            changed = [norm_path(x) for x in f.read().splitlines() if norm_path(x)]
    else:
        print("[FENCE] 未提供变更文件列表，默认放行（仅提示）。", file=sys.stderr)
        return 0

    if not changed:
        print("[FENCE] 变更文件列表为空，放行。")
        return 0

    violations = []

    def allowed(rel: str) -> bool:
        if rel in allow_add or rel in allow_mod or rel in allow_del:
            return True
        for d in (allow_add_dirs + allow_mod_dirs + allow_del_dirs):
            if rel.startswith(d):
                return True
        return False

    for rel in changed:
        if not allowed(rel):
            violations.append(rel)

    if violations:
        print("==== PATCH FENCE WARNING/FAIL ====", file=sys.stderr)
        for v in violations:
            print(f"[越界] 非白名单文件或目录：{v}", file=sys.stderr)
        print("（建议：开发期加入 fence.local.json 的 allowModifyDirs；交付前在主 fence.json 调整白名单。）", file=sys.stderr)
        print("==================================", file=sys.stderr)
        if is_lenient(args):
            return 0
        return 3

    print("[FENCE] All OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
