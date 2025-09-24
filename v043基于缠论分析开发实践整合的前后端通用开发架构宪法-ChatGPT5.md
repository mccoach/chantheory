# 通用开发规范 v4.3（前后端通用 · 效率优先 · 同步现实现 · 以代码为准 · 全量版）

## 说明

- 本文在 v4.2 的完整版本基础上，全面对齐“当前代码”的实际实现，保持原有结构与章节粒度，不删节；凡与实现不一致之处，均按“代码为准”修订与扩展。
- 关键修订与澄清（相对旧稿）：
  - 守护脚本（Patch Fence + Invariants）为本地强制项：pre-commit 自动运行 + 手动执行，云端 CI 为可选（非强制）。支持目录白名单与 fence.local.json（本地覆盖），开发期可用“宽松模式（lenient/dev）”仅警告不拦截，交付冻结期切回严格模式拦截越界。
  - Invariants 采用“静态包含检查”（不使用正则），围绕关键函数/标识（如 useMarketView 覆盖式防抖与 previewView、/api/candles meta 关键键、overlayMarkerYAxis（index=1）+ CHAN_UP/CHAN_DOWN 占位系列等）守护“不可缺失”的实现点。
  - 探活 utils/backendReady：默认绝对地址 <http://localhost:8000，可由> VITE_BACKEND_ORIGIN 指定；App 探活成功后首刷，避免后端未活导致超时。
  - 其余章节（数据模型、重采样规则、错误模型、性能并发、后台任务/健康检查等）均在原有粒度上与现实现“等量同步”。
- 守护脚本相关新增与强化：
  - 守护脚本修订原则：只增不删不改
  - 每次脚本修订必须附详细修订说明
  - 契约穷举式守护（return、export/export default、路由、事件键、配置键）
  - 精准令牌守护关键功能细节（入口/核心/结果链路至少覆盖两段）
  - 禁用正则（仅静态包含检查）
  - 不做风险分级（全部按最高风险执行）
  - Fence.local 维持现状并补充说明
  - 不单独编写守护脚本指南（通用原则融入本文；项目专有规定进各项目文档）

---

## 一、总则

- 效率优先
  - 交付与长期维护效率第一：一切决策以降低总成本（开发/测试/运维/迭代）为目标。
- 最简逻辑
  - 最小正确闭环优先：先达成可用的最小正确闭环，再做增量优化与扩展。
  - 奥卡姆剃刀：同等价值优先选择更简单、更直接的实现。
- 模块化为效率服务
  - 分层与职责清晰；仅在显著降低心智负担与重构成本时引入分层；反对“形式化模块化”。
  - 单向依赖：上层只依赖下层稳定接口；禁止跨层耦合与“抄近道”。
- Local-first 与合规
  - 默认本地可运行与可验证：保护隐私，避免数据再分发风险；云端 CI 可选启用。
- 可复现性
  - 关键产出附元信息：算法版本、参数、数据时间窗、生成时间与时区必须写入 meta，支持回放与对拍。

---

## 二、标准目录（通用建议）

- 前端（示例）
  
src/
├─ assets/
├─ components/
│ ├─ features/
│ └─ ui/
├─ composables/
├─ constants/
├─ charts/
├─ api/
├─ services/
├─ styles/
├─ utils/
├─ types/
├─ docs/
├─ adr/
└─ main.ts(x)/App.vue

- 后端（示例）
  
backend/
├─ app.py
├─ routers/
├─ services/
├─ datasource/
├─ indicators/
├─ models/
├─ utils/
├─ cache/
├─ migrations/
├─ observability/
├─ docs/
└─ settings.py

---

## 三、模块职责与“必选/可选”

- assets：媒体资源。必选。
- components/features：业务容器（MainChartPanel/VolumePanel/IndicatorPanel/SymbolPanel/WatchlistPanel/StorageManager）。必选。
- components/ui：通用 UI（ModalDialog/NumberSpinner 等）。必选。
- composables：useXxx 参数与状态编排；不直连底层数据源。必选。
- constants：端点/枚举/默认参数。必选。
- charts：纯函数生成 ECharts option；主题集中。可视化项目必选。
- api：HTTP 客户端与 DTO；统一错误模型与 trace_id 注入。必选。
- services：业务聚合/缓存/流程编排；可替换可测试。必选。
- utils：通用工具（backendReady/window/preset/download 等）。必选。
- 后端 routers 薄/ services 厚；datasource 适配屏蔽外部 API 差异；db/sqlite 维护 DDL/UPSERT/查询/迁移。必选。

---

## 四、数据契约与时间（与现实现完全一致）

- 时间统一：后端输出 ISO8601（含时区）；前端展示不附带时区后缀（仅显示层）。
- 分钟族（m 结尾）：ts 为结束时刻；显示到“YYYY-MM-DD HH:MM”。
- 日/周/月：ts 统一为 15:00（Asia/Shanghai）；显示“YYYY-MM-DD”。
- /api/candles（服务端一次成型可视窗口）：
  - 入参：code、freq、adjust、include、ma_periods（JSON）、window_preset、bars、anchor_ts、iface_key?、trace_id?
  - 出参：candles（ALL 序列）、indicators、meta
  - meta 关键键（不变量）：
    - timezone="Asia/Shanghai"
    - source/provider、source_key（方法键，如 A_1m_a 或 resample_1d_to_1M）
    - downsample_from（"1m"|"1d"|null）
    - is_cached=True
    - algo_version、generated_at、trace_id
    - all_rows、view_rows、view_start_idx、view_end_idx、window_preset_effective
- 前端仅按 meta.view_* 设置 dataZoom；交互即时预览 previewView 持久化 viewBars/rightTs（LocalStorage）。

---

## 五、错误模型与重试（修订 · 保持实现一致）

- 错误对象：code、message、trace_id、hint（可选）。
- 前端 axios 拦截器对取消类错误静默（debug 输出），不污染 error 控制台；以 code=CANCELED 识别。
- 并发与幂等：写路径幂等键；指数退避重试；重试语义一致。
- 日志与追踪：后端 NDJSON（log_event），service/level/event/message/trace_id 统一；模块级/trace 定向 DEBUG 可控。
- 资源与度量（建议）：near_end.ensure/db_read/indicators/assemble 分段时延按项目需要记录。

---

## 六、性能与并发控制（覆盖式防抖 + 序号守护）

- 覆盖式防抖：AbortController + 请求序号 reqId；仅最新请求落地。
- 展示层序号守护：renderSeq 确保仅最后一次展示动作生效（渲染/应用 dataZoom/标记叠加/resize）。
- 交互即时预览：previewView 在缩放/输入 N 根时即时刷新起止与 bars，并持久化 viewBars/rightTs；回包落地后一致。
- 探活与首帧：utils/backendReady 优先绝对地址（默认 <http://localhost:8000），探活成功后首刷（useMarketView> > autoStart=false 支持）。

---

## 七、安全与合规（Local-first）

- 仅本地访问：CORS 白名单为本地开发地址。
- 不再分发敏感原始数据：导出默认不内嵌原始数组（可合规开关）。
- 隐私最小化：默认不收集使用数据；如需采集须显式开关与保留策略。
- 取消类请求：前端静默处理，后端保持标准错误模型与日志。

---

## 八、工程规范（工具与流程）

- 类型与风格：TS 严格模式或 JSDoc；ESLint+Prettier；Python 可选 black/flake8。
- 路径别名：统一 @ 指向 src；后端使用模块化导入约定。
- 命名：组件 PascalCase；composable useXxx；服务 XxxService；常量统一前缀或全大写。
- 配置与密钥：环境变量/配置文件管理；禁止硬编码密钥。
- 构建与包体：按需引入，避免“大而全”无脑打包。
- 提交规范：Conventional Commits（建议）；pre-commit 执行守护脚本。

---

## 九、变更控制与交付保障（SOP · 本地守护为强制）

### 目的与范围

- 任何代码修改（功能、修复、优化、重构）必须通过本地守护脚本（Patch Fence + Invariants）。云端 CI 可选启用，非强制。

### 基本原则

- 二阶段握手：计划先行、获批再改（多人协作适用；个人可简化为“自我白名单”）。
- 白名单/变更预算：允许在批准的文件/目录/预算内修改，超出需调整白名单或回退。
- 最小补丁优先：不做无关重构与整理。
- 可验证交付：变更核对单 + 回归核对单 + 手测步骤（必要时附守护结果）。
- 守护脚本强制：pre-commit 自动执行；手动可随时运行；每次验收新增“可机检要点”合入 invariants.json（病毒库式增强）。
- 迭代补网：一旦发生回归，立即把该点抽象为新的机检不变量，纳入守护库与回归核对单。
- 守护令牌变更只增不删不改
- 每次守护脚本修订必须有完整修订说明
- 契约穷举与精准令牌（return、export/export default、路由、事件键、配置键等）

### 角色与职责（多人场景参考）

- 需求方：提供目标与验收点，授权白名单/预算，审批计划与交付。
- 执行方：提交计划、受控实施，形成完整交付包，对守护不变量负责。
- 审查方：对照清单与守护结果验收，发现问题立即驳回或回滚。

### 术语

- 修改点、文件白名单（允许文件/目录）、变更预算、功能验收、回归不变量、守护脚本、交付包（文档+结果）。

### 流程（本地简化版）

- 开发期（宽松模式）
  - 使用 GUARDS_MODE=dev 或 --lenient 运行 run_guards.py：Fence 越界仅警告；Invariants 严格；
  - fence.local.json 维护目录白名单，降低高频维护成本；
  - 每次修改后手动或提交前自动运行守护脚本，红灯即修。
- 冻结/交付（严格模式）
  - 运行 run_guards.py（不加 --lenient）：Fence 严格拦截越界；Invariants 严格；
  - 更新 fence.json 主白名单与 invariants.json 新要点；全绿后提交/打包。

### 白名单与变更预算

- 白名单维度：文件/目录粒度，支持 allowAdd/Modify/Delete 与 allow*Dirs（目录白名单）。
- 预算维度：最大文件数、增删行上限（可选实现）、禁止改动项（公共 API、日志结构、关键时间语义等）。
- 超范围/超预算：严格期必须暂停并调整白名单或回退。

### 影响分析与禁止改动项（示例）

- 不得破坏：公共 API 契约（/api/candles meta 键与语义）、序列时间戳语义（分钟右端、日/周/月 15:00）、日志字段与级别、覆盖式防抖/序号守护、性能预算与并发模型。
- 分析至少覆盖：接口/数据契约、时间与时区、错误模型与日志、性能与并发影响、外部依赖与限流退避。

### 交付护栏（交付包必须包含）

- 变更核对单、回归核对单、手测步骤、守护脚本结果（本地）。
- 记录与可追溯（仓库 docs/records 或 PR 模板）。
- Guards-ChangeLog（守护脚本修订说明）
- 新增令牌有效性校验结果

### 回归不变量（基线与扩展）

- 基线不变量（跨项目必检）
  - 仅在白名单/预算内改动；
  - 公共契约/时间语义/日志结构不变；
  - 覆盖式防抖与序号守护不降级；
  - 关键 UI/交互绑定与 series 占位存在。
- 项目不变量（ChanTheory 示例）
  - 主图双击打开设置（事件绑定 + 处理函数存在）；
  - CHAN 占位（yAxisIndex=1，overlayMarkerYAxis）存在；CHAN_UP/CHAN_DOWN 系列 ID 存在；
  - 多窗体 dataZoom/hover 同步；预览即时；窗宽高亮；/api/candles meta 字段齐全；
  - 时间语义：分钟 ts 为结束时刻；日/周/月 ts 为 15:00（Asia/Shanghai）。

---

## 十、版本与元信息

- 语义化版本：MAJOR.MINOR.PATCH；破坏性变更需标注与迁移说明。
- 产出元信息：图表/报告嵌入 algo_version、参数、数据窗、生成时间、timezone。
- Changelog：用户可读 + 研发可复现；必要时附对拍图或快照差异。

---

## 十一、测试与回归

- 测试金字塔
  - 单测为基座：utils 与算法；charts option 快照；关键交互最小集成。
  - 契约测试与组件测试为中层；E2E 精选关键路径（可选）。
- 黄金样例与对拍：关键输出建立黄金样例与对拍基准，升级后对比差异。
- 容错测试：网络/空数据/超阈值等异常路径覆盖。
- 基准测试：性能关键模块可提供 benchmark，升级后对比。
- 与守护脚本的衔接：守护负责“存在性与改动范围”；测试负责“行为正确性”，两者互补。

---

## 十二、前端要点（与现实现同步）

- API 客户端统一：axios + 拦截器（trace_id/错误模型/超时/取消）。
  - 取消类错误静默（Dev 下 debug 输出；对外返回 code=CANCELED）。
- 状态编排：useMarketView（覆盖式防抖 + 预览即时 + 持久化 viewBars/rightTs；右端锚定；bars 优先）。
- 图表渲染：ECharts Canvas；主题集中管理（CSS 变量→charts/theme.js）。
- 缩放/联动：zoomSync；主窗广播、副窗接收；跨窗 hover 同步（chan:hover-index）。
- 主图：K线/HL柱 + MA；overlayMarkerYAxis（index=1，隐藏）承载 CHAN 标记；CHAN_UP/CHAN_DOWN 占位系列稳定存在；tooltip 固定/聚焦线（trigger='axis'，confine=true，class=ct-fixed-tooltip）。
- 副窗：Volume/MACD/KDJ/RSI/BOLL；与主窗 dataZoom 联动；tooltip 同步风格。
- 探活与首刷：backendReady 直连后端绝对地址，探活成功后再 vm.reload() 首刷。

---

## 十三、后端要点（与现实现同步）

- 路由薄、服务厚：routers 仅做校验与调用服务；聚合/缓存/重采样在 services。
- 数据源适配：datasource 层屏蔽外部 API 差异与字段映射；失败时提供可诊断错误；方法注册表提供稳定 source_key。
- 缓存策略：热数据 TTL/LRU；本地磁盘缓存可选；暴露“是否命中缓存”与时延字段（建议）。
- 错误泄露控制：DEBUG 返回详细错误；生产仅返回标准错误对象。
- 可观测性：结构化日志、基本度量（请求时长/错误率/缓存命中），trace_id 贯穿调用链。
- 数据库迁移：版本化迁移（可选，如后续引入）；当前提供在线迁移 DB 文件与完整性检查。
- 幂等与一致性：写路径提供幂等键；重试必须保持效果一致。
- 契约优先：OpenAPI（可选）与 JSON Schema（可选）；目前以守护脚本 + 集成测试守护破坏性变更。
- 限流与熔断：外部依赖增加限流/熔断/隔离舱（按需）；降级路径可验证。

---

## 十四、反模式清单（禁止）

- 为模块而模块：无复用/隔离价值却强行抽象。
- 补丁摞补丁：连续 workaround 叠加，不做根因修复与回收计划。
- 上帝模块/组件：把路由/数据源/算法/缓存/视图堆在一起，导致不可测、难演进。
- 跨层耦合：视图或控制层绕过服务直接操作数据或实现细节。
- 缺少元信息：图表/报告无版本与参数标记。
- 过度拆分：将顺畅流程拆成过多层级，增加心智负担与链路长度。
- 破坏性变更不守护：公共契约/时间语义/日志结构等无守护与迁移说明。

---

## 十五、落地建议（变更策略）

- 先收口后扩展：先清理重复与冗余，再做新能力。
- 小步可回滚：保留回滚点；黄金样例对拍。
- 文档即代码：先更新 invariants/fence 并通过，后同步文档。
- 特性开关与灰度：风险功能走开关与小流量。
- ADR 常态化：关键决策 24h 内补齐 ADR；定期回顾与归档。

---

## 十六、协作与治理（可在多人场景采用）

- DoD（完成定义）：代码/测试/文档/守护/回滚/安全检查全达标方可合并。
- 代码评审 SLA：工作日 24h 内完成初评；跨团队变更需双侧 OWNER 通过。
- 值班与交接：明确 on-call 轮值；交接清单可复用。
- 知识沉淀：问题复盘与知识库更新纳入验收项。

---

## 十七、附录A：请求与交付模板（可复制）

- 需求方 → 执行方（计划先行）
  - 目标/变更点：
  - 允许范围：文件白名单 或 变更预算（最大文件数/增删行上限/禁止类）
  - 验收项：功能 + 基础回归不变量
  - 输出要求：全量文件/仅差异、是否附守护结果
- 执行方 → 需求方（计划）
  - 候选文件清单（含理由/可否避免）
  - 最小补丁方案
  - 影响分析（接口/时间语义/日志/性能/并发）
  - 修改预算建议
  - 验收清单草案
  - Guards-ChangeLog 草案（如预计触及守护脚本）
- 执行方 → 需求方（交付包）
  - 修改文件全量内容
  - 变更核对单（逐文件逐函数/逻辑块）
  - 回归核对单（功能验收 + 基础不变量）
  - 手测步骤（可复制执行）
  - 守护脚本结果（本地）
  - 本次新增的守护要点清单与位置（invariants.json/fence.json）
  - Guards-ChangeLog 正式版（删除/修改全量列出与理由；新增项的有效性依据与校验结论；回滚方案）

---

## 十八、附录B：关键回归不变量示例（项目可扩展）

- 通用
  - 仅白名单/预算内改动
  - 公共 API/契约不变（字段/语义/错误模型/日志结构）
  - 覆盖式防抖 + 序号守护存在
  - 契约穷举守护与精准令牌
- ChanTheory（与现实现一致示例）
  - 主窗双击打开设置（事件绑定 + 处理函数存在）
  - 主图初始化 overlayMarkerYAxis（index=1）存在，CHAN_UP/CHAN_DOWN 占位系列存在（ID 不变）；多窗体 dataZoom/hover 同步
  - 预览即时：滚轮/输入 N 根后起止与 bars 立即刷新与持久化（viewBars/rightTs）；回包落地后一致
  - 窗宽高亮向下就近；view_rows≥all_rows → ALL
  - /api/candles meta 包含 all_rows/view_rows/view_start_idx/view_end_idx/window_preset_effective/timezone/source/source_key/downsample_from/is_cached
  - 时间语义：分钟 ts 为结束时刻；日/周/月 ts 为 15:00（Asia/Shanghai）
  - axios 拦截器：取消类错误静默（debug 输出）

---

## 十九、守护脚本使用（本地 · 强制）

- 目录：scripts/guards/
  - run_guards.py：统一入口；自动推导 git 暂存变更；支持 --lenient
  - check_patch_fence.py：改动范围护栏；支持 allowAdd/Modify/Delete 与 allow*Dirs；支持 fence.local.json（本地覆盖）
  - check_invariants.py：关键不变量检查（静态包含，禁用正则）
  - invariants.json：不可缺失的函数/标记清单（含契约穷举与精准令牌）
  - fence.json：主白名单；fence.local.json：本地覆盖（.gitignore 忽略）
- pre-commit：.pre-commit-config.yaml；pip install pre-commit；pre-commit install
- 运行示例：
  - 开发期（宽松）：python scripts/guards/run_guards.py --lenient
  - 严格期：python scripts/guards/run_guards.py
  - 单独跑 Invariants：python scripts/guards/check_invariants.py
- Fence.local 使用说明：仅用于本地开发期的临时例外；需记录原因与到期点；在合并或发布前必须清理或收敛。
- 令牌选取要求：
  - 契约穷举：对 return 字段关键键、export/export default 名称、公共路由与事件名、配置键进行覆盖。
  - 精准细节：对关键判定与本地化行为设置入口/核心/结果三段中的至少两���令牌，确保链路完整。
  - 唯一性与抗重构：优先选函数名、常量键、事件名等语义稳定锚点，避免依赖易漂移文本。
- 修订说明与校验：
  - 只增不删不改
  - 新增项有效性校验必填：说明防护依据，附唯一性搜索、非注释命中与链路覆盖；建议做一次失效演练验证红灯触发。
- 严禁跳过守护：任何跳过或绕过守护脚本的提交均视为不合规。

---

## 二十、更新策略（与现实现同步）

- 以代码为准：实现变更 → 先更新 invariants.json 与 fence.json/fence.local.json → 守护跑到全绿 → 同步本文档条目。
- 守护脚本修订遵循只增不删不改
- 文档同步修订说明：更新文档时，附上守护脚本修订说明摘要与有效性校验结论。
- 文档“不可先于代码”，确保落地行为始终可复现与可验证。

## 结束
