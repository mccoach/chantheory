# scripts/guards/run_guards.ps1
# ===============================
# 说明：Windows PowerShell 快捷执行脚本
# - 支持传入变更文件列表路径（每行一个相对路径）
# - 不传参时默认运行守护脚本（Patch Fence放行，Invariants仍执行）
# ===============================

Param(
  [string]$ChangedFilesFile = ""
)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent (Split-Path -Parent $here)

Write-Host "[RUNNER-PS1] repo-root = $repo"

if ($ChangedFilesFile -ne "") {
  python "$repo\scripts\guards\run_guards.py" --changed-files-file $ChangedFilesFile
} else {
  python "$repo\scripts\guards\run_guards.py"
}
