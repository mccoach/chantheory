# ChanTheory 项目架构与关键控制规范 v1.3（整合版 · 新增“有效交互第一性原则 + 程序化 dataZoom 阻断 + 前置原子化持久化”修订 · 以代码为准）

说明

- 本版在 v1.2 基础上，围绕“有效交互的第一性原则、程序化 dataZoom 回环阻断、持久化前置与原子化”等核心痛点，进行了系统性的规则修订和落地澄清：
  - 有效交互第一性原则：不再按“动作类型”判断是否进入中枢，而是只以“关键三项（barsCount/rightTs/hostWidthPx→markerWidthPx）是否发生实际变化”为唯一有效性的判据；未发生变化的任何事件一律视为噪声，不得进入中枢。
  - 程序化 dataZoom 阻断：为渲染层程序化应用视窗范围引入明确标识或范围签名；onDataZoom 遇到此类事件必须直接返回，不得进入中枢，彻底阻断回环。
  - 持久化前置与原子化：在判定“关键三项发生变化”的当帧，先写入紧凑快照（原子化持久化），再调用中枢 execute 更新权威内存态与广播；持久化作为独立链路的尽端，不作为下一步处理的前置条件。
  - 两帧合并的写频控制：中枢广播层继续执行“两帧合并”并只广播最终值；在持久化链路上优先采用“两帧合并 + 原子快照”的最简策略，是否增加“有界处理（节流/防抖 + maxWait）”可根据实测性能做开关控制，不强制。
- 严格遵循“以代码为准”的原则：文档描述与当前实现一致；如后续实现演进，优先更新守护脚本与本文同步。
- 关键修订与澄清（相对 v1.2）：
  - 有效交互白名单改为“第一性原则判定”：仅当 barsCount/rightTs/hostWidthPx（派生 markerWidthPx）发生实际变化时才触发中枢，动作类型不再作为判断依据；离散量判定采用 e_idx（右端索引）、bars 整数与 markerWidthPx 派生值。
  - 程序化 dataZoom 阻断：渲染层应用范围（dispatchAction/setOption）前设置程序化标志或范围签名；onDataZoom 内遇到标志或签名一致立即 return，不做 Pan/ScrollZoom 判定、不进入中枢。
  - 持久化链路前置与原子化：变化发生的当帧先写入紧凑快照（单键或逻辑原子分组），再走中枢；持久化不作为请求参数的来源，API 锚点参数依然来自中枢权威内存态（anchor_ts=hub.rightTs）。
  - 保留两帧合并与覆盖式防抖：中枢层的两帧合并与请求层的覆盖式防抖继续有效；持久化链路默认不再额外加节流/防抖（可选开关依据实测启用）。

---

## 0. 范围与目标

- 目标

  - 以代码为准的规范：文档描述必须与实现一致；当实现演进，守护脚本与文档同步更新。
  - 显示状态彻底统一：前端显示层仅由 barsCount 与 rightTs 决定切片范围与位置；markerWidthPx 为派生统一宽度，不依赖后端是否处理；任何主动交互都走中枢汇总，两帧合并，覆盖防抖。
  - 有效交互第一性原则：仅当关键三项发生实际变化时才进入中枢；无变化即噪声，直接过滤；程序化 dataZoom 事件标识明确并阻断回环。
  - 持久化前置与原子化：变化发生的当帧，先落地紧凑快照，再进入中枢；持久化链路独立收尾，不作为后续处理前置条件。
  - 数据以本地 SQLite 为权威单一真相源；最小存储（仅存不复权 + 因子），最大可复现（其他即时计算）。

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
  - useViewCommandHub（显示状态中枢）：统一管理 barsCount/rightTs/markerWidthPx/atRightEdge/hostWidthPx/allRows/presetKey/freq/symbol；集中指令入口与广播合并，持久化（前置与原子化策略）与广播。
  - 有效交互门卫（第一性原则）：交互源（dataZoom/滚轮/键盘/预设/手输/resize）的候选目标值（nextBars/nextRightTs/nextHostWidth）仅在与当前中枢快照出现实际变化时才允许进入中枢；程序化 dataZoom 标识明确，onDataZoom 确认来源后阻断回环。
  - useMarketView：autoStart=false 支持首帧探活后再首刷；右端锚定；预览即时；持久化 viewBars/rightTs（前置写）与权威内存态一致；anchor_ts=hub.rightTs。

- 显示与时间
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
  - 近端唯一判定：应当已生成的最后一根结束时刻 vs 本地 cache_meta.last_ts；若未达标则整窗直拉（接受上游左端限制）。
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
    - anchor_ts（右端锚点，毫秒；前端调用必须携带，取自中枢权威内存态 hub.rightTs）
    - iface_key（方法键，选填），trace_id（选填）
  - 行为
    - 服务端一次成型计算可视窗口（右端锚定，bars 优先；ALL=当前序列总根数）；返回 ALL candles + meta.view\_\*；前端仅按 meta 应用 dataZoom。
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

## 8. 前端结构与交互（修订 · 有效交互第一性原则 · 程序化阻断 · 前置原子化持久化）

- 主题与样式

  - global.css（CSS 变量）；charts/theme.js 读取变量映射 ECharts 主题（背景/轴线/网格/涨跌色）。

- 请求与并发（覆盖式防抖）

  - axios 拦截器统一注入 trace_id；取消类错误（Abort/Canceled）仅 debug 输出。
  - useMarketView：AbortController 取消旧请求；请求序号 reqId 守护；展示层 renderSeq 守护；anchor_ts 始终取自显示状态中枢 hub.rightTs（权威内存态）。

- 显示状态中枢（useViewCommandHub）

  - 权威状态：barsCount、rightTs、markerWidthPx（派生，范围 [1,16]）、atRightEdge、hostWidthPx、allRows、presetKey、freq、symbol。
  - 指令入口（execute）：ChangeFreq、ChangeWidthPreset、ScrollZoom、Pan、KeyMove、SetBarsManual、SetDatesManual、Refresh、ChangeSymbol、ResizeHost。
  - 广播机制：两帧合并（最多 2 帧），仅广播最终值；任何有效交互立即持久化（前置与原子化）并调度广播。
  - 边界与触底：setDatasetBounds(minTs,maxTs,totalRows) 落地后，若 atRightEdge=true 自动锚到最新；rightTs 越界按就近夹取；随后更新 atRightEdge = (rightTs==maxTs)。

- 有效交互第一性原则与门卫（新增）

  - 判定标准仅基于“关键三项离散量”的实际变化：
    - barsCount：视窗 e_idx-s_idx+1 的整数是否变化；
    - rightTs：以 candles[e_idx].ts 为离散锚点，是否变化；
    - hostWidthPx→markerWidthPx：宿主宽度变化是否导致派生的 markerWidthPx 变化。
  - 门卫机制：在各交互源（onDataZoom/onWheelZoom/键盘左右键/预设/手输起止/resize）先计算候选 nextBars/nextRightTs/nextHostWidth，并与中枢快照比较；若三项均未变则直接 return，不得进入中枢；一旦任一项发生变化，执行“前置原子化持久化 → 中枢 execute → 两帧合并广播”。

- 程序化 dataZoom 阻断（新增）

  - 程序化应用视窗（dispatchAction/setOption）前设置程序化标志或范围签名；
  - onDataZoom 内首行检测该标志/签名；若为程序化事件，立即 return，不做 Pan/ScrollZoom 判定，不进入中枢，阻断回环。

- 前置原子化持久化（新增）

  - 变化发生当帧，先写入紧凑快照（单键或逻辑原子分组；例如 code|freq → {bars,rightTs,atRightEdge}），保证原子性与恢复一致性；
  - 持久化为独立链路的尽端，不作为请求参数的前置；请求锚点取自中枢权威内存态；
  - 写频控制：默认依靠“两帧合并”自然限制写频；是否增加“有界处理（节流/防抖 + maxWait）”由实测性能决定（可开关），不强制。

- 组件与职责

  - MainChartPanel：三列功能区（频率|起止+bars|窗宽+高级）；主图渲染（K 线/HL 柱 + MA）；隐藏第二 y 轴（overlayMarkerYAxis，index=1）承载 CHAN 标记；跨窗 hover 广播；dataZoom 联动；快捷键支持。
    - onDataZoom 判定流程：过滤程序化事件 → 计算离散范围（s_idx/e_idx）→ 构造候选 nextBars/nextRightTs → 门卫判定有效性 → 有效则前置原子化持久化并调用中枢（Pan/ScrollZoom）；无效则 return。
    - 订阅中枢快照：本地文案与高亮随 snapshot 更新；将 snapshot.markerWidthPx 以 chan:marker-size 事件统一转发。
    - 高级面板手输起止：前端基于 ALL candles 查找 s_idx/e_idx，计算 nextBars 与 nextRightTs，执行门卫判定与前置原子化持久化后中枢 SetDatesManual；不触发后端。
  - VolumePanel：订阅中枢快照，使用 overrideMarkWidth=snapshot.markerWidthPx；不再各自估算宽度；其余不变。
  - IndicatorPanel：与主窗 dataZoom 联动；hover 广播一致；无需宽度订阅。
  - SymbolPanel：标的输入与导出；刷新按钮；显示层按中枢快照同步 barsCount/rightTs 文案。

- 交互与键盘行为

  - 跨窗 hover 一致：任意窗广播 chan:hover-index；主图左右键从最后 hover 起跳（showTip/highlight）。
  - dataZoom：主窗作为源，副窗 attach 到 zoomSync 自动跟随；程序化事件阻断；Pan/Zoom 分支统一走中枢且受门卫过滤。

- 起止与 bars 即时预览与持久化

  - 预览即时：缩放/输入 N 根时即时刷新起止与 bars；变化门卫判定后前置原子化持久化，回包落地后以 meta 为准。
  - 时间显示规则（显示层）：分钟族“YYYY-MM-DD HH:MM”；日/周/��“YYYY-MM-DD”；不带时区后缀。

- 窗宽高亮自动匹配

  - pickPresetByBarsCountDown 向下就近高亮；barsCount≥allRows → 高亮 ALL；高亮变化不回写 barsCount 为标准值。

- 缠论覆盖层

  - 初始化存在 overlayMarkerYAxis（index=1，隐藏）；CHAN_UP/CHAN_DOWN 占位系列；仅更新 data，避免 Unknown series。

- 探活与首帧策略

  - utils/backendReady：优先绝对地址（默认 <http://localhost:8000）；App> 探活成功后 vm.reload() 首刷，避免后端未活导致超时。

- 窗口切片右端持久化与后台处理触发规则（项目专用，唯一）

  - 核心状态
    - 切片右端时间 rightTs（code|freq 维度持久化；中枢唯一来源）。
    - 可视根数 barsCount（code|freq 维度持久化；中枢唯一来源）。
    - 触底 atRightEdge：切片右端是否位于全量数据的最右端（最新一根）。
  - 后台处理必然触发的三类场景（近端比对 + 必要拉新）
    1. 改变标的（Symbol change）
    2. 改变频率（Freq change）
    3. 点击刷新按钮（Refresh）
    - 两条近端线并行评估：
      - 线 A：当前选择 freq 与本地库做近端比对；若有缺口则远程整窗拉新 → 落库；否则直接本地取全量。
      - 线 B：当前标的的 1d 数据做近端比对；若当前 freq=1d，则 A 与 B 合并为仅 1d 的近端比对。
    - 后台处理结束后右端保持规则：
      - 若触发前 atRightEdge=true → 处理后仍锚到最新一条（右端触底保持）。
      - 若触发前 atRightEdge=false → 处理后仍锚到原 rightTs（就近夹取到 ≤ 原值的最大 ts）。
  - 绝不触发后台数据处理的交互（仅本地渲染与持久化；中枢统一承担）
    - 改变 bars（统一判定“bars 数变化”）
      - 鼠标滚轮缩放：以当前聚焦 bar 为中心同时改变左右端（双改：bars+右端）；门卫判定有效变化后执行前置原子化持久化并中枢 ScrollZoom。
      - 预设窗宽按钮/手动输入根数：保持右端不变，仅改变 bars（仅 bars）；若左端触底无法再扩展，按“左端触底反推右端移动”规则改变右端；门卫判定与前置持久化后中枢。
      - 持久化：变化当帧前置原子化持久化（紧凑快照）。
      - 窗宽高亮：缩放后向下就近 pickPresetByBarsCountDown；barsCount≥allRows → 高亮 ALL。
    - 鼠标拖动平移或键盘左右键导致窗口移动
      - 仅移动切片（Pan/KeyMove），门卫判定有效变化后前置原子化持久化并中枢 Pan/KeyMove；不触发后台处理。
  - 强制锚定
    - 前端任何 /api/candles 请求都必须携带 anchor_ts=hub.rightTs（权威内存态）；服务端以此一次成型视窗并锚定，避免“未指定锚点时默认跳最右端”。

- 越界与就近区间原则

  - 切片左端 < 数据区间左端：以数据区间左端为切片左端，按原窗宽反推切片右端；若窗宽 > 有效数据范围，则以 ALL（全量）显示。
  - 切片右端 > 数据区间右端：以数据区间右端为切片右端，按原窗宽反推切片左端；若窗宽 > 有效数据范围，则以 ALL 显示。
  - 左端触底反推右端移动（bars 扩展但左端已卡死）：当需扩大 bars 且左端已到数据区间最左端无法再扩展时，保持左端不动，向右移动右端以满足目标 bars；其余场景保持右端不变。
  - 原 rightTs 不在新数据集合时（如清理/迁移或源修订）：就近向左夹取到 ≤ 原值的最大 ts；不可达时锚到最右端并置 atRightEdge=true。

- 交互解耦
  - 复权切换（none/qfq/hfq）、技术指标开关与参数、主图样式（K/HL 柱）、缠论/分型可视参数变化、主题切换、窗口 resize、导出：均不触发后台数据处理；右端不变；仅渲染层重绘与宽度应用。

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
  - 每个 code|freq 维度持久化 viewBars（barsCount）、rightTs 与 atRightEdge（LocalStorage）；显示状态中枢与���互源遵循“前置原子化持久化”的策略；显示状态中枢统一读写并以权威内存态驱动请求参数。

---

## 10. 后台任务与调度

- 启动后后台近端保障（可选）

  - 自选池：并发（受限）对每个标执行“1d 全量覆盖/校正”。

- 缓存清理（守护线程）

  - 周期执行 LRU/TTL 清理（可中断等待），保留基本快照统计。

- 在线备份/健康检查
  - PRAGMA integrity_check、VACUUM 等接口暴露（/api/storage/\*）。

---

## 11. 性能与并发控制（修订 · 两帧合并 + 覆盖式防抖 · 前置原子化持久化）

- 覆盖式防抖：Abort+reqId+renderSeq；仅最后一次请求/动作落地。
- 中枢两帧合并：滚轮/拖动等高频指令仅广播最终值；避免抖动。
- 前置原子化持久化：有效交互发生当帧写入紧凑快照（单键或逻辑原子分组）；默认依靠两帧合并自然限制写频；是否启用“有界处理（节流/防抖 + maxWait）”由实测性能决定，可作为开关（不强制）。
- 显示层即时预览：任意有效交互都即时更新 barsCount/rightTs 与 symbol 文案，高亮与 markerWidthPx 同步；前置持久化后由中枢广播；回包一致。
- 日志与可观测：NDJSON + 基本度量；trace_id 贯穿链路；建议增加“过滤无效事件数”“每秒持久化写次数/耗时”打点以便调参。

---

## 12. 安全与合规

- Local-first：CORS 白名单仅本地开发地址。
- 数据最小化：导出默认不内嵌原始数据（可开关）。
- 隐私最小化：默认不收集使用数据；如需采集须显式开关与保留策略。
- 交互解耦：非后台处理类交互不触发数据抓取或落库；仅本地渲染与显示状态更新（前置原子化持久化 + 中枢广播）。

---

## 13. 风险与对策

- 上游限流或瞬断：并发限流、指数退避、失败重试；错峰与任务队列。
- 特殊交易日分钟数异常：交易日历与特例容差处理。
- 因子缺失/修订：fallback none + 对账回补（预留）；meta.hint 标注。
- 本地守护遗漏：每次验收新增“可机检要点”入 invariants.json（病毒库式增强）。
- 视窗越界：按“就近区间原则”落地；必要时全量显示（ALL）。
- 持久化写频：默认依靠两帧合并控制；如观测到卡顿，按开关启用“有界处理”，限定节流与 maxWait。

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
  - 前端：global.css + charts/theme.js、统一 axios、覆盖式防抖（Abort+reqId+renderSeq）、主/量/指标窗体、LocalStorage 持久化（前置原子化）、显示状态中枢（第一性原则门卫）、起止与 bars 即时预览、CHAN 占位稳定、程序化 dataZoom 阻断

- 验收补充（不变量清单）

  - 覆盖式防抖落地：旧回包/旧帧不落地
  - 中枢两帧合并：高频触发仅广播最终值
  - 有效交互门卫：仅当关键三项发生变化才进入中枢；程序化 dataZoom 阻断有效
  - 前置原子化持久化：变化当帧写入紧凑快照；回包与显示一致
  - Pan/Zoom 分支判定正确（平移仅右端；缩放双改）
  - 窗宽高亮向下就近；barsCount≥all_rows → ALL
  - 跨窗体 hover 一致
  - 缠论覆盖层稳定（隐藏 yAxis=1 + CHAN_UP/CHAN_DOWN 占位）
  - 探活首刷策略生效（后端未活不首刷）
  - 错误模型：取消类错误静默（不污染 error）

- 变更流程（本地守护为强制）
  - 守护脚本通过（Patch Fence + Invariants）；pre-commit 自动执行；手动可随时运行��
  - 云端 CI 可选：如启用，在 PR 上运行同一套脚本作为门禁。

---

## 16. 术语对照

- 切片右端锚点（rightTs）：当前窗口右端 bar 的收盘时间毫秒；离散锚点为 candles[e_idx].ts。
- 可见根数（barsCount）：当前窗口可见的 K 根数（ALL=总根数）。
- markerWidthPx：统一符号宽度（派生自 hostWidth 与 barsCount，上限 16 下限 1）。
- 程序化 dataZoom：由渲染层调用 dispatchAction/setOption 应用范围导致的 zoom 事件，不属于用户交互；须阻断。
- 有效交互门卫：比较候选 nextBars/nextRightTs/nextHostWidth 与中枢快照，未变则 return。
- 前置原子化持久化：变化发生当帧写入紧凑快照（单键或逻辑原子分组），随后进入中枢路径。

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

- 不使用固定时长防抖；覆盖式防抖 + 序号守护；交互即时预览。
- MainChartPanel 顶部三列；SymbolPanel 精简（仅标的输入与导出）。
- 显示状态中枢：barsCount/rightTs/markerWidthPx/atRightEdge/hostWidthPx/allRows/presetKey/freq/symbol；两帧合并广播；任何有效交互前置原子化持久化。
- 时间显示：分钟族 →YYYY-MM-DD HH:MM；日/周/月 →YYYY-MM-DD。
- 窗宽高亮：向下就近（pickPresetByBarsCountDown）；barsCount≥all_rows→ALL。
- 缠论覆盖层：overlayMarkerYAxis（index=1）+ CHAN_UP/CHAN_DOWN 占位系列；仅更新 data。
- 渲染与重绘：变化即重绘；主窗越界重置 dataZoom；展示层动作以 renderSeq 校验。
- 程序化 dataZoom 阻断（新增）：渲染层应用范围的 dataZoom 事件不得进入中枢。

### 17.4 切频/切窗解耦与右端锚定缩放规则（修订 · 显示状态中枢版 · 项目专用唯一规则）

- 预设 → bars（向上取整，ALL=total_rows）
- 切频仅改变 barsCount；切窗仅改变 barsCount；均不改 rightTs；由服务端返回视图窗口索引。
- 强制锚定：前端任何 /api/candles 请求必须携带 anchor_ts=hub.rightTs，以右端锚点定位 e_idx，向左推 s_idx。
- 自动高亮：缩放后向下就近；barsCount≥all_rows → ALL。
- 有效交互第一性原则（新增）：
  - 仅当 barsCount/rightTs/hostWidthPx（派生 markerWidthPx）发生实际变化时才进入中枢；未变即噪声，一律过滤。
  - 判定基于离散量（e_idx、bars 整数、派生 markerWidthPx），不以像素/百分比为准。

- bars 改变的两类缩放与右端持久化：

  - 鼠标滚轮缩放：以当前聚焦 bar 为中心，同时改变左右端（双改 ScrollZoom）；门卫判定有效后前置原子化持久化并中枢。
  - 预设窗宽/手动输入根数：保持右端不变，仅改变 bars（SetBarsManual）；若左端触底无法再扩展，反推右端移动以满足目标 bars；不触发后端。

- Pan/KeyMove 与越界：

  - 鼠标拖动平移/键盘左右键：仅移动切片右端（Pan/KeyMove），门卫判定有效后前置原子化持久化并中枢；越界按夹取规则纠偏。

- 手输起止日期：
  - 查询本地当前 ALL candles；计算 s_idx/e_idx → nextBars 与 nextRightTs；门卫判定有效后前置原子化持久化并中枢 SetDatesManual；不触发后端。

---

## 18. 守护脚本与本地工作流（强制）

- 目录：scripts/guards/
  - run_guards.py：统一入口；自动推导 git 暂存变更；支持宽松（--lenient / GUARDS_MODE=dev）与严格模式。
  - check_patch_fence.py：改动范围护栏；支持 fence.json + fence.local.json；支持目录白名单。
  - check_invariants.py：关键不变量检查；静态包含；不使用正则。
  - invariants.json：不变量清单（文件路径 + mustContain）。
  - fence.json：主白名单（allowAdd/Modify/Delete + allow\*Dirs）；fence.local.json：本地覆盖（.gitignore 忽略）。
- ��版新增可机检要点建议：
  - useViewCommandHub.js 必含 execute(…) 的各 action 令牌与 setDatasetBounds/markerWidthPx/\_recalcMarkerWidth、有效交互门卫与幂等早退令牌。
  - MainChartPanel.vue 必含 onDataZoom 程序化阻断令牌与 Pan/ScrollZoom 分支调用、chan:marker-size 转发、SetDatesManual。
  - VolumePanel.vue 必含订阅中枢快照应用 overrideMarkWidth 与传入 buildVolumeOption。
  - useMarketView.js 必含 hub.onChange 中 presetKey/barsCount/rightTs 文案更新、reload anchor_ts=hub.rightTs。
  - 有效交互门卫令牌：在交互源中判定 nextBars/nextRightTs/nextHostWidth 与快照差异后方执行下游。

---

## 19. 版本与元信息

- 语义化版本：MAJOR.MINOR.PATCH；破坏性变更需标注与迁移说明。
- 产出元信息：algo_version、参数、数据窗、生成时间、timezone。
- Changelog：用户可读 + 研发可复现；必要时附对拍差异。

---

## 20. 测试与回归

- 单测：utils 与算法；charts option 快照；关键交互最小集成；onDataZoom 程序化阻断与门卫判定；中枢 action 落地。
- 集成慢测：/api/candles 贯通对拍（scripts/cases.yaml）。
- 守护脚本：Patch Fence 与 Invariants 必过；与测试互补。
- 性能观测（建议）：前端记录“过滤无效事件数”“持久化写次数/耗时”“渲染掉帧统计”，用于调参。

---

## 21. 常见问题与建议

- 高频开发：Fence 用宽松模式 + fence.local.json 目录白名单；Invariants 始终严格。
- 交付冻结：Strict 模式全绿；必要时扩主白名单与不变量清单。
- 新增可机检要点：验收后立即合入 invariants.json（“病毒库式”增强）。
- 持久化链路：默认仅“两帧合并 + 原子快照”；如观测卡顿再启用“有界处理”。

---

## 22. 图形标记与符号宽度（项目专用 · 统一来源修订）

- 唯一权威符号宽度源（统一广播）

  - 宽度计算：markerWidthPx = round(hostWidthPx × 0.88 / barsCount)，限制 [1,16]。
  - 广播机制：主窗订阅中枢后将 snapshot.markerWidthPx 以事件 chan:marker-size 转发；宽度唯一来源为中枢派生值。
  - 订阅与应用：主图缠论标记、量窗标记、分型标记等模块仅订阅该事件或直接订阅中枢快照并立即应用；不做各自估算、也不触发任何数据处理。

- 覆盖层不变量
  - 主图存在 overlayMarkerYAxis（index=1，隐藏）；CHAN_UP/CHAN_DOWN 占位系列稳定存在（仅更新 data）。
  - 分型标记绑定主价格轴 yAxisIndex=0；确认分型连线按设置绘制；仅受统一宽度源影响其符号宽高与偏移。

---

## 23. 显示状态中枢（useViewCommandHub）操作与规则（新增 · 第一性原则与持久化前置）

- 主动交互统一入口（execute）

  - ChangeFreq：仅改变 barsCount；rightTs 不变；越界夹取；自动高亮；变化当帧前置原子化持久化与广播。
  - ChangeWidthPreset：仅改变 barsCount；rightTs 不变；越界夹取；自动高亮；变化当帧前置原子化持久化与广播。
  - ScrollZoom：双改 barsCount+rightTs；自动高亮；变化当帧前置原子化持久化与广播。
  - Pan：仅改变 rightTs；barsCount 不变；越界夹取；变化当帧前置原子化持久化与广播。
  - KeyMove：仅改变 rightTs；barsCount 不变；越界夹取；变化当帧前置原子化持久化与广播。
  - SetBarsManual：仅改变 barsCount；rightTs 不变；自动高亮；变化当帧前置原子化持久化与广播。
  - SetDatesManual：双改 barsCount+rightTs（手输起止）；越界夹取；自动高亮；变化当帧前置原子化持久化与广播。
  - Refresh：barsCount/rightTs 不变；必要后台处理后由 setDatasetBounds 应用触底/越界规则；广播快照。
  - ChangeSymbol：仅更新 symbol；barsCount/rightTs 不变；变化当帧前置原子化持久化（保持现值）与广播。
  - ResizeHost：仅更新宿主宽度；重算 markerWidthPx；barsCount/rightTs 不变；变化当帧前置原子化持久化与广播。

- 有效交互门卫与幂等早退

  - 门卫：在交互源计算候选 nextBars/nextRightTs/nextHostWidth，与中枢快照离散量比较；未变则 return；变化则前置持久化后中枢 execute。
  - 幂等早退：中枢内部对即将落地状态做轻量幂等检查；若 nextBars==barsCount 且 nextRightTs==rightTs 且 markerWidthPx 不变，则直接 return，双保险。

- 边界与触底

  - setDatasetBounds：落地后，若 atRightEdge=true → 自动锚到最新；rightTs 越界按就近夹取；随后更新 atRightEdge = (rightTs==maxTs)。

- 初始恢复

  - initFromPersist(code,freq)：读取持久化 barsCount/rightTs/atRightEdge；不做查表重置；广播快照；后续仅在落地与有效交互中变更。

- 自动高亮与非标 bars

  - 任何 barsCount 改变均向下就近高亮；barsCount≥allRows 高亮 ALL；高亮变化不回写 barsCount 为标准值。

- 事件兼容
  - 主窗订阅中枢后将 markerWidthPx 转发 chan:marker-size 事件；订阅者以中枢值作为唯一宽度来源。

---

## 24. 变更控制与交付保障（SOP · 有效交互门卫 + 持久化前置版）

- 目的与范围

  - 任何代码修改（功能、修复、优化、重构）必须通过本地守护脚本（Patch Fence + Invariants）。云端 CI 可选启用。

- 基本原则

  - 二阶段握手：计划先行、获批再改；白名单/预算受控。
  - 最小补丁优先：不做无关重构与整理。
  - 可验证交付：变更核对单 + 回归核对单 + 手测步骤（必要时附守护结果）。
  - 守护令牌变更只增不删不改；每次守护脚本修订必须有完整修订说明。

- 影响分析与禁止改动项（示例）

  - 不得破坏：公共 API 契约（/api/candles meta 键与语义）、时间语义（分钟右端、日/周/月 15:00）、日志结构、覆盖式防抖/序号守护、显示状态中枢不变量（execute 指令集、setDatasetBounds、markerWidthPx 派生与广播）、程序化 dataZoom 阻断与有效交互门卫、性能与并发模型。

- 交付护栏（交付包必须包含）
  - 变更核对单、回归核对单、手测步骤、守护脚本结果（本地）。
  - Guards-ChangeLog（守护脚本修订说明）。
  - 新增令牌有效性校验结果。

---

## 25. 验收清单（有效交互门卫 + 程序化阻断 + 前置持久化版）

- 仅当关键三项发生实际变化，主窗 onDataZoom 才触发中枢；程序化 dataZoom 阻断有效。
- 任何 barsCount/rightTs/hostWidthPx（派生 markerWidthPx）变化，变化当帧前置原子化持久化，写入紧凑快照（单键或逻辑原子分组）。
- 中枢两帧合并与覆盖式防抖有效：高频滚轮/拖动仅落地最后一次请求与最终广播。
- 任何 barsCount 改变，窗宽高亮向下就近即时更新；非标 bars 不被拉齐。
- 任何有效交互改变 barsCount 或 rightTs，均立即持久化到 LocalStorage（code|freq 维度）。
- markerWidthPx 始终由中枢计算并统一广播；量窗/分型/缠论标记等均无自估逻辑；随缩放即时变化。
- 刷新/改频/改标三类后台处理结束后触底保持与越界夹取规则正确；rightTs 无被动漂移。
- anchor_ts=hub.rightTs 强制锚定；服务端返回 ALL + meta.view\_\* 正确；前端仅依 meta 设置 dataZoom。
- 缠论覆盖层不变量：overlayMarkerYAxis（index=1）存在，CHAN_UP/CHAN_DOWN 占位存在。
- 跨窗 hover 同步与 dataZoom 联动保持一致；结构化日志打点可观测“过滤的无效事件数/持久化写频与耗时”。

---

## 结束
