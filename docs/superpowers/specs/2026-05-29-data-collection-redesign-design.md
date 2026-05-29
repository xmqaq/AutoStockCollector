# 数据采集模块重构设计

日期：2026-05-29
范围：`AutoStockCollector-web`（系统总览、采集监控两页）+ `AutoStockCollector-manage`（采集相关 API）

## 背景与问题

当前"系统总览"(`/dashboard`) 与"采集监控"(`/data-monitor`) 存在职责重叠，且采集的日期范围对用户而言"像是被系统固定的"。经排查，根因有两点：

1. **职责重叠**：两页都渲染同一个 `ProgressTable`（同一份 `collectStore.progressList`），边界模糊。
2. **日期语义错配**：采集弹窗有日期选择器、后端 `/collect/history` 也接收 `start_date/end_date`，但 8 类数据时间语义不同，其中一半根本不使用所选日期：
   - 使用日期：`kline` / `financial` / `dragon_tiger` / `margin`
   - 忽略日期（仅抓当前/最新）：`news`（仅最新 N 条）/ `fund_flow`（仅当日快照）/ `sector`（仅当前快照）
   - 无日期概念：`stock_info`（全量名录）

   因此"选了 2025 全年""向后延展到今天"对快照类无效，造成"日期固定"的体感。同时缺少独立的"增量更新到最新"动作。

## 目标

1. 日期/范围真正可控（补一整年、补到今天皆可），且每类数据如实表达其时间能力。
2. 合并去重两个页面，职责清晰。
3. 一眼看清每类数据的覆盖区间/条数/新鲜度。
4. 采集任务可追溯（看到所用参数）、可按原参数重跑。

非目标（本次不做）：定时/自动调度（仅做手动一键更新；后端实现保留可被未来 cron 复用的形态）。

## 设计

### 1. 数据类型分类（基石）

按时间语义将 8 类归为三类，前后端共用一份映射常量：

| 类别 | 类型 | 时间能力 | 补历史 | 更新到最新 |
|---|---|---|---|---|
| 区间历史类 | kline / financial / dragon_tiger / margin | 按日期区间 | 支持（选区间） | 支持（从 DB 最新日期+1 补到今天） |
| 快照类 | news / fund_flow / sector | 仅当前 | 不支持 | 支持（抓最新快照） |
| 名录类 | stock_info | 全量名录 | 不支持 | 支持（增量补新代码） |

该分类直接消除"选了日期不生效"的困惑：补历史场景下只暴露区间历史类。

前端常量文件 `src/utils/collectTypes.ts`（或 `src/constants/`，跟随既有约定）导出：

```ts
export type CollectCategory = 'range' | 'snapshot' | 'catalog'
export interface CollectTypeMeta {
  value: string        // kline / financial / ...
  label: string        // 中文名
  category: CollectCategory
}
export const COLLECT_TYPES: CollectTypeMeta[]   // 8 项
```

后端在 `api/routes/__init__.py` 内以同等的分组常量表达（如 `RANGE_TYPES`/`SNAPSHOT_TYPES`/`CATALOG_TYPES`），作为 `_build_history_tasks` 与新增 `update_latest` 的唯一事实来源。

### 2. 页面职责（消除重复）

- **系统总览 `/dashboard`（只读）**
  - 顶部健康卡片（后端状态、完成度、累计条数、最新新闻数）——维持现状。
  - 数据覆盖表：复用 `ProgressTable`，展示每类 记录数 / 数据区间(date_from~date_to) / 新鲜度。
  - 最新资讯列表——维持现状。
  - 移除所有采集操作入口（本页纯只读）。
- **采集中心 `/data-monitor`（操作台，页面标题改为"采集中心"，路由 path 不变以免影响既有链接）**
  - 工具栏：「补历史」「更新到最新」「清空数据库」「刷新」。
  - 运行中任务实时进度：保留仪表盘，语义明确为"当前运行中任务的整体进度"。
  - 任务历史表（含参数列与重跑）。
  - 不再渲染静态覆盖表（覆盖信息归总览）。

结果：`ProgressTable` 仅在总览出现一次，两页职责零重叠。

### 3. 覆盖表新鲜度展示（总览）

`ProgressTable` 已有"数据量"和"数据区间"列。新增一列"新鲜度"：

- 区间历史类：以 `date_to` 距今天数计算。`<=1` 天显示"最新"（绿）；`<=7` 天显示"N 天前"（常规）；`>7` 天显示"N 天前"（橙色提示需更新）。
- 快照类 / 名录类：显示最近一次采集时间（若可得）或"—"，不做"落后天数"判断。

新鲜度纯前端基于 `progress_all` 返回的 `date_to` 计算，后端无需改动。

### 4. 采集场景一：补历史（弹窗）

- 日期范围选择器 + 预设按钮：`近一年` / `今年以来` / `2025全年` / `2024全年` / `自定义`。
  - 预设语义（以当天为基准计算）：
    - 近一年：[今天-365天, 今天]
    - 今年以来：[当年-01-01, 今天]
    - 2025全年：[2025-01-01, 2025-12-31]
    - 2024全年：[2024-01-01, 2024-12-31]
    - 自定义：保留用户手选区间
- 类型勾选只列区间历史类 4 项（kline/financial/dragon_tiger/margin），默认全选。
- 提交走现有 `POST /api/v1/collect/history`；前端只发送区间类 `task_types`。
- 后端 `_build_history_tasks` 收窄为只构建区间历史类任务（移除 news/fund_flow/sector，stock_info 不在历史采集中）。这样即使旧调用传入快照类也不会产生"假任务"。

### 5. 采集场景二：更新到最新（弹窗，新增）

- 类型勾选默认全选 8 类。
- 每个勾选类型旁显示预览：当前覆盖到的日期（区间类取 `date_to`，快照/名录类显示最近更新或"快照"）+ "将补 N 天 / 抓最新快照"。预览数据来自 `progress_all`，纯前端计算文案。
- 提交走新增 `POST /api/v1/collect/update_latest`，body：`{ task_types?: string[] }`。
- 后端按类型计算增量参数：
  - 区间历史类：`start = date_to + 1 天`，`end = 今天`；若 `date_to >= 今天` 则跳过该类型（记入返回的 `skipped`）。
  - 快照类：直接以现有 collect 逻辑抓最新（无日期参数）。
  - 名录类（stock_info）：`mode=incremental`。
  - 计算完成后统一 `scheduler.create_task / start_task`。

### 6. 任务可追溯与重跑

- 后端 `scheduler.list_tasks` 返回项补充 `params` 字段（当前缺失）。
- 采集中心任务历史表新增"参数"列：区间类显示 `start_date~end_date`，名录类显示 `mode`，快照类显示"快照"。
- 重跑：复用现有 `retryTask`（按 task_id 重提，使用 DB 中原 params）。在表中已有"重试"按钮基础上，确保对 `completed` 任务也提供"重跑"入口（按原参数重新创建并启动）。

## 后端改动清单（AutoStockCollector-manage）

1. 新增分组常量 `RANGE_TYPES` / `SNAPSHOT_TYPES` / `CATALOG_TYPES`（`api/routes/__init__.py`）。
2. 收窄 `_build_history_tasks`：仅构建区间历史类任务。
3. 新增 `POST /api/v1/collect/update_latest`：基于 `_get_collection_stats` 的 `date_to` 计算增量参数并提交任务；返回 `{ started, skipped, failed }`。建议抽 `_compute_update_latest_tasks(stats, task_types)` helper（形态便于未来被 cron 复用）。
4. `scheduler.list_tasks` 返回项增加 `params`（内存版 `get_stats` 与 DB 版均补齐）。

## 前端改动清单（AutoStockCollector-web）

1. 新增 `src/utils/collectTypes.ts`：类型→类别/中文名映射常量，供两页复用。
2. `src/api/collect.ts`：新增 `updateLatest(params: { task_types?: string[] })`。
3. `views/Dashboard/index.vue`：覆盖表新增"新鲜度"列；确认本页无采集操作入口。
4. `views/DataMonitor/index.vue`（采集中心）：
   - 标题与文案改为"采集中心"。
   - 工具栏拆出「补历史」「更新到最新」两个弹窗。
   - 补历史弹窗：预设按钮 + 仅区间类勾选。
   - 更新到最新弹窗：全类型勾选 + 覆盖预览文案。
   - 移除静态覆盖表（保留仪表盘=运行中进度）。
   - 任务历史表新增"参数"列；为 completed/failed/cancelled 任务提供"重跑"。
5. `components/ProgressTable/index.vue`：新增"新鲜度"列（接受 date_to，前端计算落后天数与色级）。该列仅总览使用，通过 prop 开关控制是否显示，避免影响其它潜在引用。

## 数据流

```
总览（只读）
  fetchProgress -> GET /collect/progress_all -> {tasks:{type:{record_count,date_from,date_to}}}
                -> 覆盖表（含前端计算新鲜度）

采集中心（操作）
  补历史      -> POST /collect/history {start_date,end_date,task_types(区间类)}
  更新到最新  -> POST /collect/update_latest {task_types}
                  后端读 progress_all 的 date_to -> 计算增量 -> create/start task
  任务历史    -> GET /tasks?status= -> 含 params -> 展示+重跑(retryTask)
  每3秒自动刷新 progress + tasks（维持现状）
```

## 测试要点

- 后端：`_build_history_tasks` 不再产出快照类；`update_latest` 对"已最新"类型返回 skipped；`list_tasks` 含 params。
- 前端：补历史弹窗仅显示 4 个区间类；预设按钮正确填充区间；更新预览文案与 date_to 一致；总览覆盖表新鲜度色级正确；采集中心不再出现重复覆盖表。

## 兼容性

- 路由 path（`/dashboard`、`/data-monitor`）保持不变，仅改页面标题与内容。
- `/collect/history` 接口签名不变；仅服务端构建逻辑收窄，旧前端调用仍可用。
