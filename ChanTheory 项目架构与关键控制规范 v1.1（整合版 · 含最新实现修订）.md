# ChanTheory 项目架构与关键控制规范 v1.1（整合版 · 含最新实现修订 · 以代码为准）

说明

- 本版在 v1.0 共识稿与既有 v1.1 草案基础上，全面对齐“当前代码”实际实现，消除与实现不一致之处，并在原有结构与章节粒度上“等量覆盖”（不删节），保证文档与代码一致。
- 关键同步点（与既有文案差异说明）：
  - 守护脚本为强制项，但“本地守护（pre-commit + 手动执行）”为必选，云端 CI 可选（非强制）。Patch Fence 支持目录白名单与 fence.local.json，本地开发期可用“宽松模式（lenient/dev）”仅警告不拦截；交付冻结期用严格模式拦截越界。
  - Invariants 检查采用“静态包含”方式，不使用正则表达式，围绕关键函数/标识（如 CHAN_UP/CHAN_DOWN/overlayMarkerYAxis、/api/candles meta 关键键、useMarketView 覆盖式防抖与 previewView 等）守护“不可缺失”的实现点。
  - 前端 MainChartPanel 顶部为“三列布局”：左列频率切换；中列起止与 bars 展示；右列窗宽预设按钮 + 高级图标按钮（打开高级面板）。SymbolPanel 仅保留标的输入与导出（频率/窗宽被移入 MainChartPanel）。
  - 主图存在“第二条隐藏 y 轴（overlayMarkerYAxis，index=1）”，专用于承载缠论涨跌标记（CHAN_UP/CHAN_DOWN 占位系列），不影响主价格轴自适应。
  - /api/candles 服务端“一次成型”计算可视窗口（右端锚定），返回 ALL 序列 + meta.view_*；前端仅按 meta 应用 dataZoom；缩放即时预览 previewView 持久化 viewBars/rightTs。
  - 时间语义：分钟族 ts=结束时刻；日/周/月 ts=当日或该组最后一日 15:00（Asia/Shanghai）；与重采样右端对齐一致。
  - 探活 utils/backendReady：默认绝对地址 <http://localhost:8000，可由> VITE_BACKEND_ORIGIN 指定。App 探活成功后首刷，避免后端未活导致长超时。
  - 项目专用规则（窗口右端持久化与后台处理触发）已按模块归属融入本文相应章节；��规则仅适用于本项目，不纳入通用开发规范。

---

## 0. 范围与目标

- 目标

  - 建立“以代码为准”的规范：文档描述必须与代码行为一致；当实现演进时，优先更新守护脚本 + 文档同步。
  - 本地守护强制：提交前通过 Patch Fence + Invariants；云端 CI 可选开启（按项目需要）。
  - 数据以本地 SQLite 为权威单一真相源；最小存储（仅存不复权序列 + 因子），最大可复现（其他均即时计算）。

- 总原则
  - 效率优先（交付与长期维护的总成本最小）
  - 最简逻辑（根因重构，避免补丁摞补丁）
  - 模块化为效率服务（职责清晰，可替换可测试）
  - Local-first 与合规（默认本地运行与验证；云端 CI 可选）
  - 可复现性（产出与 API 元信息完整、可对拍）

---

## 1. 架构总览

- 后端（FastAPI + SQLite）

  - 路由薄/服务厚：routers 只做校验与调度，services 承载核心流程（读取 → 复权 → 重采样 → 可视窗口计算）。
  - SQLite（WAL）为单一真相源：candles（adjust='none'）、adj_factors（qfq/hfq 因子）、candles_cache、cache_meta；支持在线迁移 DB（config.json 变更 → 校验 → 切换）。
  - 重采样与复权即时计算：分钟派生多分钟；日派生周/月；qfq/hfq 按因子即时套用；兜底策略明确。
  - 结构化日志（NDJSON）：统一 log_event（service/level/event/message/trace_id）；summary 模式可裁剪字段；模块级别与 trace ID 定向 DEBUG 可配置。
  - 配置管理：config.json 原子写入 + 镜像 config.applied.json + 文件监听，变更（如 db_path）触发在线迁移。

- 前端（Vue3 + Vite + ECharts v6）

  - 主题与样式：global.css（CSS 变量），charts/theme.js 映射 ECharts 主题。
  - 请求与并发：统一 axios + 拦截器（trace_id 注入；取消类错误静默）；覆盖式防抖（AbortController + reqId + UI renderSeq）。
  - useMarketView：autoStart=false 支持首帧探活后再首刷；右端锚定；预览即时；本地持久化 viewBars/rightTs。
  - MainChartPanel 顶部三列：频率 / 起止+bars / 窗宽预设+高级按钮（集成高级入口）；SymbolPanel 专注标的输入与导出。
  - CHAN 覆盖层稳定：主图初始化存在 overlayMarkerYAxis（index=1），CHAN_UP/CHAN_DOWN 占位系列；仅更新 data，避免 Unknown series 报错。
  - 多窗联动：zoomSync 横轴缩放同步（主窗广播，从窗接收）；跨窗 hover 同步（chan:hover-index）。

- 时间与显示
  - 分钟族 time 显示到“YYYY-MM-DD HH:MM”；日/周/月显示到“YYYY-MM-DD”（不附带时区后缀）。
  - 分钟族 ts = 结束时刻；日/周/月 ts = 15:00（Asia/Shanghai）。

---

## 2. 数据模型与持久化

- 存储介质

  - SQLite（WAL）：跨平台、零运维、事务与并发足够。
  - 如规模显著增长再评估 DuckDB/Parquet 归档（对外契约保持稳定）。

- 表结构（概要）

  - candles（仅存 adjust='none'）
    - 主键：symbol, freq('1m'|'1d'), adjust('none'), ts(ms)
    - 列：open, high, low, close, volume, amount?, turnover_rate?, source, fetched_at(ISO), revision?
  - adj_factors
    - 主键：symbol, date(YYYYMMDD)
    - 列：qfq_factor, hfq_factor, updated_at
  - candles_cache / cache_meta（非 1d）
    - cache_meta：symbol/freq/adjust → rows, first_ts, last_ts, last_access

- 存储策略
  - 仅存不复权序列 + 因子表；复权即时计算；指标即时计算。
  - 不存冗余派生（change/change_pct/amplitude 等前端可稳算的列一律即时计算）。

---

## 3. 数据拉取与入库策略（共识与实现一致）

- 日线（1d）
  - 整窗直拉 + 覆盖更新（UPSERT）；A 股额外获取 qfq/hfq 因子并 UPSERT。
- 分钟族（1m/5m/15m/30m/60m）
  - 近端唯一判定：期望最后一根结束时刻 vs 本地 cache_meta.last_ts；若未达标则整窗直拉（接受上游左端限制）。
- 兜底重采样
  - 分钟：1m→ 多分钟会话切片重采样；日 → 周/月（W-FRI、自然月末），组末 15:00。
- 读取路径
  - 所有业务读取仅用本地数据库（采集与业务彻底解耦）。

---

## 4. 复权与重采样

- 复权
  - 价格 × 因子、成交量 ÷ 因子；因子查不到回退 none，元信息保留（meta.hint 可按需扩展）。
- 重采样
  - 分钟族：会话切片（AM 9:30-11:30，PM 13:00-15:00），右端对齐；开=首、收=尾、高=最大、低=最小、量/额=求和。
  - 日 → 周/月：W-FRI 与自然月末对齐；ts=该组最后一日 15:00。

---

## 5. 衍生列存储策略

- 可稳定本地计算的不拉取不存储（如 change/change_pct）。
- 依赖外部口径的（turnover_rate/amount 等）如源有则存。
- 技术指标不入库，使用时本地计算（MA/MACD/KDJ/RSI/BOLL）。

---

## 6. API 契约与元信息

- /api/candles（Router：backend/routers/candles.py；Service：backend/services/market.py）

  - 入参
    - code, freq(1m|5m|15m|30m|60m|1d|1w|1M), adjust(none|qfq|hfq)
    - include（如 "ma,macd,kdj,rsi,boll,vol"）、ma_periods（JSON）
    - window_preset（5D/10D/1M/3M/6M/1Y/3Y/5Y/ALL），bars（优先）
    - anchor_ts（右端锚点，毫秒；前端调用必须携带）
    - iface_key（方法键，选填），trace_id（选填）
  - 行为
    - 服务端一次成型计算可视窗口（右端锚定，bars 优先；ALL=当前序列总根数）；返回 ALL candles + meta.view_* 索引，前端仅按 meta 应用 dataZoom。
  - 出参
    - candles：[ {t,o,h,l,c,v,a?,tr?} ]
    - indicators：按 include 即时计算（MA/MACD/KDJ/RSI/BOLL）
    - meta（关键键，不变量）
      - timezone="Asia/Shanghai"
      - source（em|sina|ak|tx|resample）、source_key（如 A_1m_a 或 resample_1m_to_5m）
      - downsample_from（"1m"|"1d"|null）
      - is_cached=True
      - algo_version、generated_at、trace_id
      - all_rows、view_rows、view_start_idx、view_end_idx、window_preset_effective

- 错误模型
  - DEBUG=True：detail 含回溯；DEBUG=False：标准 {code,message,trace_id}
  - 前端 axios 拦截器对取消类错误静默（debug 输出），不污染 error 面板。

---

## 7. 后端模块化（文件职责）

- app.py：入口与 CORS；启动钩子（DB 初始化、配置监听、后台任务启动）；/api/ping 与 /api/health。
- routers：candles/symbols/storage/watchlist/user_config/debug —— 仅组装参数/校验/调用服务并返回。
- services：
  - market：核心链路（读取 → 复权 → 重采样 → 可视窗口计算 → 组装响应）
  - storage：SQLite 读写、UPSERT、缓存元信息维护、LRU/TTL 清理
  - symbol_index：索引构建/快照归档（与 symbols 路由联动）
  - tasks：后台任务（自选近端保障、缓存清理守护）
- datasource：fetchers（归一化/方法注册/稳定 source_key），akshare 适配层。
- db/sqlite.py：连接/DDL/迁移/健康/统计；candles/candles_cache/adj_factors/symbol_index 等表读写。
- utils：time（时区/日期换算）、window_preset（预设 →bars 映射）、logger（NDJSON）、errors、fileio（原子写）。

---

## 8. 前端结构与交互（修订 · 三列功能区）

- 主题与样式
  - global.css（CSS 变量）；charts/theme.js 读取变量映射 ECharts 主题（背景/轴线/网格/涨跌色）。

- 请求与并发（覆盖式防抖）
  - axios 拦截器统一注入 trace_id；取消类错误（Abort/Canceled）仅 debug 输出。
  - useMarketView：AbortController 取消旧请求；请求序号 reqId 守护；展示层 renderSeq 守护。

- 组件与职责
  - MainChartPanel：三列功能区（频率|起止+bars|窗宽+高级）；主图渲染（K 线/HL 柱 + MA）；隐藏第二 y 轴（overlayMarkerYAxis，index=1）承载 CHAN 标记；跨窗 hover 广播；dataZoom 联动；快捷键支持。
  - SymbolPanel：标的输入与导出（导出 PNG/JPG/SVG/HTML）；刷新按钮。
  - VolumePanel、IndicatorPanel：副窗（量窗 + MACD/KDJ/RSI/BOLL），与主窗同步 dataZoom 与 hover。
  - WatchlistPanel、StorageManager：自选池管理与存储维护。

- 交互与键盘行为
  - 跨窗 hover 一致：任意窗广播 chan:hover-index；主图左右键从最后 hover 起跳（showTip/highlight）。
  - dataZoom：主窗作为源，副窗 attach 到 zoomSync 自动跟随。

- 起止与 bars 即时预览与持久化
  - previewView：缩放/输入 N 根时即刻刷新起止与 bars，并持久化 viewBars/rightTs（LocalStorage）；回包落地后以 meta 为准。
  - 时间显示规则（显示层）：分钟族“YYYY-MM-DD HH:MM”；日/周/月“YYYY-MM-DD”；不带时区后缀。

- 窗宽高亮自动匹配
  - pickPresetByBarsCountDown 向下就近高亮；view_rows≥all_rows → 高亮 ALL（原有规则保持）。

- 缠论覆盖层
  - 初始化存在 overlayMarkerYAxis（index=1，隐藏）；CHAN_UP/CHAN_DOWN 占位系列；仅更新 data，避免 Unknown series。

- 探活与首帧策略
  - utils/backendReady：优先绝对地址（默认 <http://localhost:8000）；App> 探活成功后 vm.reload() 首刷，避免后端未活导致超时。

- 窗口切片右端持久化与后台处理触发规则（项目专用，唯一）
  - 核心状态
    - 切片右端时间 rightTs（code|freq 维度持久化）。
    - 可视根数 viewBars（code|freq 维度持久化）。
    - 触底 atRightEdge：切片右端是否位于全量数据的最右端（最新一根）。
  - 必然触发后台数据处理的三类场景（近端比对 + 必要拉新）
    1) 改变标的（Symbol change）
    2) 改变频率（Freq change）
    3) 点击刷新按钮（Refresh）
    - 两条近端线并行评估：
      - 线 A：当前选择 freq 与本地库做近端比对；若有缺口才远程整窗拉新 → 落库；否则直接本地取全量。
      - 线 B：当前标的的 1d 数据做近端比对；若当前 freq=1d，则 A 与 B 合并为仅 1d 的近端比对。
    - 后台处理结束后右端保持规则：
      - 若触发前 atRightEdge=true → 处理后仍锚到最新一条（右端触底保持）。
      - 若触发前 atRightEdge=false → 处理后仍锚到原 rightTs（就近夹取到 ≤ 原值的最大 ts）。
  - 绝不触发后台数据处理的交互（仅本地渲染与持久化）
    - 改变 bars（统一判定“bars 数变化”）
      - 鼠标滚轮缩放：以当前聚焦 bar 为中心同时改变左右端（双端收放）。
      - 预设窗宽按钮/手动输入根数：保持右端不变，仅改变左端；若左端触底无法再扩展，按“左端触底反推右端移动”规则改变右端。
      - 持久化：即时 previewView 更新 viewBars/rightTs。
      - 窗宽高亮：缩放后向下就近 pickPresetByBarsCountDown；view_rows≥all_rows → 高亮 ALL（保持原有规则）。
    - 鼠标拖动平移或键盘左右键导致窗口移动
      - 仅移动切片，不触发后台处理；如确实改变了切片右端时间，则更新 rightTs 并判定/持久化 atRightEdge。
  - 强制锚定
    - 前端任何 /api/candles 请求都必须携带 anchor_ts=rightTs；服务端以此一次成型视窗并锚定，避免“未指定锚点时默认跳最右端”。
  - 越界与就近区间原则
    - 切片左端 < 数据区间左端：以数据区间左端为切片左端，按原窗宽反推切片右端；若窗宽 > 有效数据范围，则以 ALL（全量）显示。
    - 切片右端 > 数据区间右端：以数据区间右端为切片右端，按原窗宽反推切片左端；若窗宽 > 有效数据范围，则以 ALL 显示。
    - 左端触底反推右端移动（bars 扩展但左端已卡死）：当需扩大 bars 且左端已到数据区间最左端无法再扩展时，保持左端不动，向右移动右端以满足目标 bars；其余场景保持右端不变。
    - 原 rightTs 不在新数据集合时（如清理/迁移或源修订）：就近向左夹取到 ≤ 原值的最大 ts；不可达时锚到最右端并置 atRightEdge=true。
  - 交互解耦
    - 复权切换（none/qfq/hfq）、技术指标开关与参数、主图样式（K/HL柱）、缠论/分型可视参数变化、主题切换、窗口 resize、导出：均不触发后台数据处理；右端不变；仅渲染层重绘与宽度应用。

---

## 9. 用户配置与存储路径（文件）

- 持久层
  - 单文件 config.json（原子写 + 镜像 .applied.json + 滚动备份）
  - 后端提供 GET/PUT /api/user/config；watcher 发现变更自动迁移 DB（校验通过后切换）。

- 默认路径与可配置
  - 默认 var/；db_path 可迁移（integrity_check 通过即切换）。

- 配置变更监听
  - 监听 config.json 与镜像；检测变更走安全迁移流程，失败回滚。

- 视图持久化（项目专用）
  - 每个 code|freq 维度持久化 viewBars 与 rightTs（LocalStorage）；复用 useUserSettings.setViewBars/setRightTs。
  - atRightEdge 状态持久化（建议 per code|freq 缓存并随视窗更新），用于刷新后保持锚定策略。

---

## 10. 后台任务与调度

- 启动后后台近端保障（可选）
  - 自选池：并发（受限）对每个标执行“1d 全量覆盖/校正”。

- 缓存清理（守护线程）
  - 周期执行 LRU/TTL 清理（可中断等待），保留基本快照统计。

- 在线备份/健康检查
  - PRAGMA integrity_check、VACUUM 等接口暴露（/api/storage/*）。

---

## 11. 性能与并发控制（修订）

- 覆盖式防抖：Abort+reqId+renderSeq；仅最后一次请求/动作落地。
- 交互即时预览：previewView 立即刷新起止与 bars，并持久化，提升体感；回包落地一致。
- 日志与可观测：NDJSON + 基本度量；trace_id 贯穿链路。
- 资源预算与建议：可根据项目设定记录 near_end.ensure/db_read/indicators/assemble 分段时延。

---

## 12. 安全与合规

- Local-first：CORS 白名单仅本地开发地址。
- 数据最小化：导出默认不内嵌原始数据（可开关）。
- 隐私最小化：默认不收集使用数据；如需采集须显式开关与保留策略。
- 交互解耦：非后台处理类交互不触发数据抓取或落库；仅本地渲染。

---

## 13. 风险与对策

- 上游限流或瞬断：并发限流、指数退避、失败重试；错峰与任务队列。
- 特殊交易日分钟数异常：交易日历与特���日容差处理。
- 因子缺失/修订：fallback none + 对账回补（预留）；meta.hint 标注。
- 本地守护遗漏：每次验收新增“可机检要点”入 invariants.json（病毒库式增强）。
- 视窗越界：按“就近区间原则”落地，必要时全量显示（ALL）。

---

## 14. 默认参数（建议范围）

- fetch.concurrency = 2–4（当前配置 3 为常见选择）
- retry.max_attempts = 2（~3）
- retry.base_delay_ms = 500
- 日线近端截止小时 daily_fresh_cutoff_hour（当前 settings 中默认 18）
- DEBUG = 开发 True / 生产 False

---

## 15. 路线与交付（修订 · 本地守护强制）

- 一步到位新骨架（与现实现保持一致）
  - 后端：SQLite DDL/PRAGMA、datasource、storage、market、routers、meta 扩展
  - 前端：global.css + charts/theme.js、统一 axios、覆盖式防抖（Abort+reqId+renderSeq）、主/量/指标窗体、LocalStorage 持久化、起止与 bars 即时预览、CHAN 占位稳定

- 验收补充（不变量清单）
  - 覆盖式防抖落地：旧回包/旧帧不落地
  - 预览即时：滚轮/输入 N 根后，起止与 bars 立即刷新与持久化，回包一致
  - 窗宽高亮向下就近；view_rows≥all_rows → ALL
  - 跨窗体 hover 一致
  - 缠论覆盖层稳定（隐藏 yAxis=1 + CHAN_UP/CHAN_DOWN 占位）
  - 探活首刷策略生效（后端未活不首刷）
  - 错误模型：取消类错误静默（不污染 error）

- 变更流程（本地守护为强制）
  - 守护脚本通过（Patch Fence + Invariants）；pre-commit 自动执行；手动可随时运行；
  - 云端 CI 可选：如启用，在 PR 上运行同一套脚本作为门禁。

---

## 16. 术语对照

- 近端：当前会话/粒度下应当已生成的最后一根 K 的结束时刻（右端）
- 整窗直拉：历史起点 → 当前的全历史拉取
- 兜底重采样：主抓取失败或不足时，从 1m 或 1d 重采样生成目标粒度
- 覆盖式防抖：AbortController + reqId + UI renderSeq，只保留最新请求/动作
- 预览态：previewView 在交互时即时更新起止与 bars，落地后以 meta 为准
- 切片右端持久化：rightTs 在 code|freq维度持久化，用作锚定与刷新后保持

---

## 17. 技术执行规范整理（随开发迭代同步）

### 17.1 标的索引拉取与本地数据库存储

- 范围：A / ETF / LOF 三类；UPSERT 不删除；快照统计 symbol_index_summary。
- 并发抓取、主备接口、聚合优先级（A>ETF>LOF）、重试指数退避；结构化日志。
- API：
  - GET /api/symbols/index（可选 refresh）
  - POST /api/symbols/refresh
  - GET /api/symbols/summary

### 17.2 行情数据拉取操作规范

- 适用标的：A/ETF/LOF
- 频率：1m/5m/15m/30m/60m、1d/1w/1M
- 时区：Asia/Shanghai；右端对齐（label=right）
- 近端判定：以“应当已生成的 K 的结束时刻 end_ts_expected”与本地 last_ts 比较
- 整窗直拉：触发条件为近端未达标或首次请求（接受上游左端限制）
- 存储：
  - A 股 1d → candles（none）+ adj_factors
  - 非 A 日线（含分钟/周/月）→ candles_cache + cache_meta
- 重采样：
  - 1m→ 多分钟；1d→ 周/月；严格右端对齐、会话切片
- meta.source/source_key 标记真实来源与方法键

### 17.3 前端信息显示层技术规范（修订）

- 不使用固定时长防抖；覆盖式防抖 + 序号守护；交互即时预览
- MainChartPanel 顶部三列；SymbolPanel 精简（仅标的输入与导出）
- 预览即时：previewView 在缩放/输入 N 根时立即刷新起止与 bars，并持久化 viewBars/rightTs
- 时间显示：分钟族 →YYYY-MM-DD HH:MM；日/周/月 →YYYY-MM-DD
- 窗宽高亮：向下就近（pickPresetByBarsCountDown）；view_rows≥all_rows→ALL
- 缠论覆盖层：overlayMarkerYAxis（index=1）+ CHAN_UP/CHAN_DOWN 占位系列；仅更新 data
- 渲染与重绘：变化即重绘；主窗越界重置 dataZoom；展示层动作以 renderSeq 校验

### 17.4 切频/切窗解耦与右端锚定缩放规则（修订 · 项目专用唯一规则）

- 预设 → bars（向上取整，ALL=total_rows）
- 切频仅改变频率；切窗仅改变窗宽；均由服务端返回视图窗口索引
- 强制锚定：前端任何 /api/candles 请求必须携带 anchor_ts=rightTs，以右端锚点定位 e_idx，向左推 s_idx。
- 自动高亮：缩放后向下就近；view_rows≥all_rows → ALL（原有规则保持）。

- bars 改变的两类缩放与右端持久化：
  - 鼠标滚轮缩放：以当前聚焦 bar 为中心，同时改变左右端（双端收放）；仅本地预览与持久化，不触发后台处理。
  - 预设窗宽/手动输入根数：保持右端不变，仅改变左端；若左端触底无法再扩展，反推右端移动以满足目标 bars；不触发后台处理。

- 越界与就近区间原则（窗口切片越界落地）
  - 切片左端 < 数据区间左端：以数据区间左端为切片左端，按原窗宽反推切片右端；若窗宽 > 有效数据范围，则以 ALL 显示。
  - 切片右端 > 数据区间右端：以数据区间右端为切片右端，按原窗宽反推切片左端；若窗宽 > 有效数据范围，则以 ALL 显示。

- 触底状态与刷新后的保持（后台处理三类）
  - 改标/改频/刷新结束后：若触发前 atRightEdge=true，则保持右端在最新一条；否则保持原 rightTs（就近夹取）。

---

## 18. 守护脚本与本地工作流（强制）

- 目录：scripts/guards/
  - run_guards.py：统一入口；自动推导 git 暂存变更；支持宽松（--lenient / GUARDS_MODE=dev）与严格模式
  - check_patch_fence.py：改动范围护栏；支持 fence.json + fence.local.json；支持目录白名单
  - check_invariants.py：关键不变量检查；静态包含；不使用正则
  - invariants.json：不变量清单（文件路径 + mustContain）
  - fence.json：主白名单（allowAdd/Modify/Delete + allow*Dirs）；fence.local.json：本地覆盖（.gitignore 忽略）
- 本地使用：
  - pip install pre-commit；pre-commit install（提交时自动运行）
  - 手动运行：python scripts/guards/run_guards.py（严格）或加 --lenient（宽松）
- 云端 CI（可选）：如需启用，可在 PR 上运行同一脚本作为门禁

---

## 19. 版本与元信息

- 语义化版本：MAJOR.MINOR.PATCH；破坏性变更需标注与迁移说明
- 产出元信息：algo_version、参数、数据窗、生成时间、timezone
- Changelog：用户可读 + 研发可复现；必要时附对拍差异

---

## 20. 测试与回归

- 单测：utils 与算法；charts option 快照；关键交互最小集成
- 集成慢测：/api/candles 贯通对拍（scripts/cases.yaml）
- 守护脚本：Patch Fence 与 Invariants 必过；与测试互补

---

## 21. 常见问题与建议

- 高频开发：Fence 用宽松模式 + fence.local.json 目录白名单；Invariants 始终严格
- 交付冻结：Strict 模式全绿；必要时扩主白名单与不变量清单
- 新增可机检要点：验收后立即合入 invariants.json（“病毒库式”增强）

---

## 22. 图形标记与符号宽度（项目专用）

- 唯一权威符号宽度源（统一广播）
  - 宽度计算：统一以 hostWidth × visCount（当前可见根数）为基准，结合 barPercent 与最小/最大宽约束，得到 markerWidthPx。
  - 广播机制：主窗计算后触发全局事件 chan:marker-size，携带 { px: markerWidthPx }。
  - 订阅与应用：主图缠论标记、量窗标记、分型标记等模块仅订阅该事件并立即应用；不做各自估算、也不触发任何数据处理。

- 覆盖层不变量
  - 主图存在 overlayMarkerYAxis（index=1，隐藏）；CHAN_UP/CHAN_DOWN 占位系列稳定存在（仅更新 data）。
  - 分型标记绑定主价格轴 yAxisIndex=0；确认分型连线按设置绘制；仅受统一宽度源影响其符号宽高与偏移。

---

## 结束
