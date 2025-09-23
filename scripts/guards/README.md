# Guards 使用说明（本地/CI 统一 · 以内容机检为主）

本项目提供一套“提交前/手动可执行”的守护脚本，用于在改动落库前进行两类机检：

- **内容不变量（Invariants）**：以“文件路径 + 必须包含的字符串片段”守护关键实现点，防止功能被删除或改坏。
- **改动范围护栏（Patch Fence）**：以白名单约束“本次改动可以触达的文件/目录”，控制变更范围（支持严格/宽松/禁用）。

本说明覆盖：

- 统一入口 run_guards.py（本轮更新：默认仅跑 Invariants，Fence 默认关闭）
- Patch Fence：check_patch_fence.py
- Invariants：check_invariants.py
- Windows 快捷脚本：run_guards.ps1
- 相关环境变量、返回码、典型用法、常见问答

> 你可以选择把约束重心放在**内容机检**：默认只跑 Invariants。当你需要在冻结/交付时收紧改动范围，再开启 Patch Fence 的严格模式。

---

## 快速开始

- 本地严格机检（仅内容不变量，默认 Fence 关闭）

```bash
python scripts/guards/run_guards.py
```

- 开启 Fence（严格）+ Invariants（交付/冻结期推荐）

```bash
python scripts/guards/run_guards.py --fence on
```

- 开发期：开启 Fence 但宽松（越界仅警告）

```bash
GUARDS_FENCE=on GUARDS_MODE=dev python scripts/guards/run_guards.py
# Windows PowerShell:
# $env:GUARDS_FENCE="on"; $env:GUARDS_MODE="dev"; python scripts/guards/run_guards.py
```

- 指定变更文件列表运行（CI/自定义脚本）

```bash
python scripts/guards/run_guards.py --fence on --changed-files "frontend/chan-theory-ui/src/components/features/MainChartPanel.vue,scripts/guards/invariants.json"
# 或
python scripts/guards/run_guards.py --fence on --changed-files-file ./changed.txt
```

---

## 统一入口：scripts/guards/run_guards.py

- 作用
  - **统一入口**：按顺序运行 Patch Fence（可选）与 Invariants（强制）。
  - **默认行为（本轮改���）**：Fence 默认关闭（仅跑 Invariants），除非你显式开启。

- 命令行参数
  - `--repo-root PATH`
    - 仓库根目录，默认自动推断为“脚本所在目录的上上级”。
  - `--changed-files CSV`
    - 逗号分隔的变更文件列表（相对仓库根，正斜杠）。
  - `--changed-files-file PATH`
    - 文本文件（每行一个相对路径），优先级低于 `--changed-files`。
  - `--lenient`
    - 宽松模式开关，仅当 Fence 被启用时生效（对 Invariants 无效）。开启后 Fence 越界仅警告不拦截。
  - `--fence {off,on,auto}`
    - 是否运行 Patch Fence：
      - off：**默认**，跳过 Fence，仅运行 Invariants。
      - on：强制运行 Fence。
      - auto：保留旧行为（当存在变更时跑 Fence）。

- 相关环境变量（优先级高于 CLI）
  - `GUARDS_FENCE=off|on|auto`（高于 `--fence`）
  - `GUARDS_MODE=dev`（当 Fence 启用时等价传递 `--lenient` 给下游 Fence）

- 变更列表来源优先级
  - `--changed-files` > `--changed-files-file` > 自动从 git 暂存推导 > 空集合

- 返回码
  - 0：全部通过。
  - 非 0：某一步失败（stderr 展示详细失败原因）。

- 典型用法

```bash
# 仅跑 Invariants（默认）
python scripts/guards/run_guards.py

# 强制跑 Fence + Invariants（严格）
python scripts/guards/run_guards.py --fence on

# 开发期宽松 + 开启 Fence
GUARDS_FENCE=on GUARDS_MODE=dev python scripts/guards/run_guards.py
```

---

## 改动范围护栏：scripts/guards/check_patch_fence.py

- 作用
  - **白名单校验**：只允许对 fence.json / fence.local.json 中允许的文件/目录进行“新增/修改/删除”。
  - **目的**：控制变更范围，防止提交扩散到无关目录。

- 命令行参数
  - `--repo-root PATH`：仓库根目录，默认自动推断。
  - `--config PATH`：主白名单（默认 `scripts/guards/fence.json`）。
  - `--local-config PATH`：本地覆盖白名单（默认 `scripts/guards/fence.local.json`），**不入库**，用于开发期临时放行。
  - `--changed-files CSV`：逗号分隔变更文件列表。
  - `--changed-files-file PATH`：包含变更文件列表的文本文件。
  - `--lenient`：宽松模式（越界仅警告）。

- 环境变量
  - `FENCE_LENIENT=1|true|yes`：等价于 `--lenient`
  - `GUARDS_MODE=dev`：也会触发宽松模式（与 `--lenient` 等价）

- 配置字段（fence.json / fence.local.json）
  - `allowAdd / allowModify / allowDelete`：精确文件白名单
  - `allowAddDirs / allowModifyDirs / allowDeleteDirs`：目录白名单（前缀匹配）

- 返回码
  - 0：通过（或宽松模式下仅警告）
  - 3：越界且处于严格模式

- 示例

```bash
# 严格期：使用主白名单校验
python scripts/guards/check_patch_fence.py --repo-root . --changed-files-file ./changed.txt

# 开发期：本地覆盖白名单 + 宽松模式
python scripts/guards/check_patch_fence.py --repo-root . --lenient
```

---

## 内容不变量：scripts/guards/check_invariants.py

- 作用
  - **静态包含检查**：不使用正则，仅以“文件路径 + 必须包含的字符串片段”校验关键要点是否存在。
  - **重点**：当前仓库把“设置窗双页（display/chan）与确认分型设置行”等要点纳入不变量，防回归。

- 命令行参数
  - `--repo-root PATH`：仓库根目录，默认自动推断。
  - `--config PATH`：不变量配置（默认 `scripts/guards/invariants.json`）。

- 返回码
  - 0：全部命中。
  - 2：任意文件缺失或任一关键片段缺失。

- 示例

```bash
python scripts/guards/check_invariants.py
python scripts/guards/check_invariants.py --config scripts/guards/invariants.json
```

---

## Windows 快捷脚本：scripts/guards/run_guards.ps1

- 作用
  - **Windows 快捷调用**：封装 `python scripts/guards/run_guards.py`，便于传入变更列表文件。

- 参数
  - `-ChangedFilesFile PATH`：包含变更文件列表的文本文件路径（每行一个相对路径）。

- 行为
  - 传入 `ChangedFilesFile` 时：调用 `run_guards.py --changed-files-file`。
  - 未传入时：直接调用 `run_guards.py`（Fence 默认 off，仅跑 Invariants）。

- 示例（PowerShell）

```powershell
.\scripts\guards\run_guards.ps1
.\scripts\guards\run_guards.ps1 -ChangedFilesFile .\changed.txt
```

---

## 默认值与优先级（总表）

- run_guards.py
  - 默认：`--fence off`（仅跑 Invariants）
  - 变更列表：`--changed-files` > `--changed-files-file` > 自动从 git 暂存推导 > 空
  - 环境变量优先：`GUARDS_FENCE` 高于 `--fence`
  - 开发宽松：`GUARDS_MODE=dev` 或 `--lenient`（仅当 Fence 启用时生效）

- check_patch_fence.py
  - 默认：严格模式；配置默认读取 `scripts/guards/fence.json` 并合并 `fence.local.json`

- check_invariants.py
  - 默认：读取 `scripts/guards/invariants.json`；缺任意必含片段 → 失败

---

## 典型使用场景

- 日常开发（**以内容机检为主**）
  - 仅跑不变量：

    ```bash
    python scripts/guards/run_guards.py
    ```

  - 需要“看一下范围”但不拦截：

    ```bash
    GUARDS_FENCE=on GUARDS_MODE=dev python scripts/guards/run_guards.py
    ```

- 冻结/交付（**收紧范围 + 严格机检**）
  - 强制 Patch Fence + Invariants：

    ```bash
    python scripts/guards/run_guards.py --fence on
    ```

- CI（GitHub Actions 或其他）
  - 建议在 CI Job 环境中设置：
    - PR/Release：`GUARDS_FENCE=on`（配合 invariants.json，双重门禁）
    - 日常流水线：保留 `fence=off`，仅跑 Invariants 加速

---

## 常见问答（FAQ）

- Q：我只想手动跑守护，并取消本机 `git commit` 时自动触发，怎么做？
  - A：在本机执行：

    ```bash
    pre-commit uninstall
    # 或直接删除 .git/hooks/pre-commit
    ```

    之后你可以在提交前手动运行：

    ```bash
    python scripts/guards/run_guards.py
    ```

- Q：白名单对我来说摩擦太大，我可以完全不用吗？
  - A：可以。**本轮已将 run_guards.py 的默认模式改为 `--fence off`**，不再自动跑 Patch Fence。你仍可在交付冻结期显式开启（`--fence on`）。

- Q：我想临时允许某些目录的改动，不想改主白名单，怎么办？
  - A：在本机创建/编辑 `scripts/guards/fence.local.json`（不入库），添加 `allowModifyDirs` 即可。Fence 开启时生效；关闭 Fence 时无需配置。

- Q：Invariants 检查什么？
  - A：由 `scripts/guards/invariants.json` 定义。例如本轮新增机检：**设置窗两页（display/chan）与“确认分型”设置行**、保存写回调用（`setFractalSettings/setChanSettings/setKlineStyle/setMaConfigs/setAdjust`）等。缺任一片段，将立即失败。

---

## 维护建议

- **以内容机检为主**：将“关键实现点”不断提炼为 invariants.json 条目，做到“病毒库式增强”，提升回归发现能力。
- **Patch Fence 视时期使用**：开发期关闭或宽松；冻结/交付期开启严格模式，防止无关范围的变更。
- **最小补丁原则**：每次提交尽量聚焦单一功能，便于通过 Patch Fence（当开启）与人工审查。
- **文档即配置**：当新增关键实现点（例如这次的“确认分型设置行”），立即补 invariants.json；提交前本地运行守护直至全绿。

---

## 参考命令备忘

```bash
# 仅不变量（默认）
python scripts/guards/run_guards.py

# 开启 Fence（严格）
python scripts/guards/run_guards.py --fence on

# 开发期（Fence 宽松）
GUARDS_FENCE=on GUARDS_MODE=dev python scripts/guards/run_guards.py

# 指定变更列表
python scripts/guards/run_guards.py --fence on --changed-files-file ./changed.txt

# 单独运行
python scripts/guards/check_invariants.py
python scripts/guards/check_patch_fence.py --lenient
```
