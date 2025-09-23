#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_guards.py
=============
统一运行守护脚本的入口（本地/CI皆可）。
本版改动（应“取消文件/目录白名单”的诉求）：
- 新增 --fence {off,on,auto}，默认 off：默认仅运行 Invariants，不跑 Patch Fence；
- 支持环境变量 GUARDS_FENCE 覆盖（off/on/auto），优先级高于参数；
- 其余行为保持：自动推断仓库根；自动从 git 暂存推导变更；宽松模式仍可用于 Fence（当启用 Fence 时）。

用法示例：
  # 仅跑不变量（默认）
  python scripts/guards/run_guards.py
  # 强制跑 Patch Fence + Invariants
  python scripts/guards/run_guards.py --fence on
  # 开发期宽松 + 明确跑 Fence
  GUARDS_FENCE=on GUARDS_MODE=dev python scripts/guards/run_guards.py
"""

import argparse
import os
import subprocess
import sys

def guess_repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))

def _run(cmd, cwd=None):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return 1, "", str(e)

def git_changed_staged(repo_root: str) -> list[str]:
    # 检查是否为 git 仓库
    rc, out, _ = _run(["git", "-C", repo_root, "rev-parse", "--is-inside-work-tree"])
    if rc != 0 or "true" not in out.lower():
        return []
    # 获取已暂存变更
    rc, out, _ = _run(["git", "-C", repo_root, "diff", "--name-only", "--cached"])
    if rc == 0:
        files = [x.strip().replace("\\", "/") for x in out.splitlines() if x.strip()]
        if files:
            return files
    # 回退：HEAD~1...HEAD
    rc, out, _ = _run(["git", "-C", repo_root, "diff", "--name-only", "HEAD~1...HEAD"])
    if rc == 0:
        files = [x.strip().replace("\\", "/") for x in out.splitlines() if x.strip()]
        if files:
            return files
    # 兜底：返回空
    return []

def resolve_fence_mode(cli_value: str | None) -> str:
    """解析 Fence 模式：环境变量 GUARDS_FENCE 优先，其次 CLI，默认 off。"""
    env = os.getenv("GUARDS_FENCE", "").strip().lower()
    if env in {"off", "on", "auto"}:
        return env
    val = (cli_value or "").strip().lower()
    if val in {"off", "on", "auto"}:
        return val
    return "off"  # 默认禁用 Fence

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=guess_repo_root(), help="仓库根目录（默认自动推断）")
    ap.add_argument("--changed-files", help="逗号分隔的变更文件列表")
    ap.add_argument("--changed-files-file", help="包含变更文件列表的文本文件")
    ap.add_argument("--lenient", action="store_true", help="Fence 宽松模式（仅在 Fence 启用时生效）")
    ap.add_argument("--fence", choices=["off","on","auto"], default="off", help="是否运行 Patch Fence（默认 off）")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo_root)
    print(f"[RUNNER] repo-root = {repo}")

    # 解析 Fence 模式（env 优先）
    fence_mode = resolve_fence_mode(args.fence)
    print(f"[RUNNER] fence mode = {fence_mode}")

    # 自动派生变更列表（供 Fence 与诊断使用）
    derived_changed = None
    if not args.changed_files and not args.changed_files_file:
        files = git_changed_staged(repo)
        if files:
            derived_changed = ",".join(files)
            print(f"[RUNNER] auto-derived changed files ({len(files)}):")
            for f in files[:20]:
                print(f"  - {f}")
            if len(files) > 20:
                print(f"  ... and {len(files)-20} more")

    # 1) Patch Fence（按模式运行/跳过）
    if fence_mode == "on" or (fence_mode == "auto" and (args.changed_files or args.changed_files_file or derived_changed)):
        fence_cmd = [
            sys.executable,
            os.path.join(repo, "scripts", "guards", "check_patch_fence.py"),
            "--repo-root", repo
        ]
        if args.lenient or os.getenv("GUARDS_MODE", "").strip().lower() == "dev":
            fence_cmd += ["--lenient"]
        if args.changed_files:
            fence_cmd += ["--changed-files", args.changed_files]
        elif args.changed_files_file:
            fence_cmd += ["--changed-files-file", args.changed_files_file]
        elif derived_changed:
            fence_cmd += ["--changed-files", derived_changed]

        print(">>> RUN (Fence):", " ".join(fence_cmd))
        r1 = subprocess.run(fence_cmd)
        if r1.returncode not in (0,):
            print(f"[RUNNER] Patch Fence 失败（退出码 {r1.returncode}）", file=sys.stderr)
            return r1.returncode
    else:
        print("[RUNNER] Patch Fence disabled (fence=off) — only running Invariants")

    # 2) Invariants（始终执行）
    inv_cmd = [
        sys.executable,
        os.path.join(repo, "scripts", "guards", "check_invariants.py"),
        "--repo-root", repo
    ]
    print(">>> RUN (Invariants):", " ".join(inv_cmd))
    r2 = subprocess.run(inv_cmd)
    if r2.returncode not in (0,):
        print(f"[RUNNER] Invariants 失败（退出码 {r2.returncode}）", file=sys.stderr)
        return r2.returncode

    print("[RUNNER] All guards passed")
    return 0

if __name__ == "__main__":
    sys.exit(main())
