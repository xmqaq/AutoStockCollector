# 数据采集模块重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"系统总览"改为只读概览、"采集监控"改为操作台，修正 8 类数据的日期语义错配（补历史 / 更新到最新两个场景），并让采集任务可追溯、可重跑。

**Architecture:** 后端新增"类型分组常量 + 增量参数计算纯函数 + `/collect/update_latest` 路由"，收窄 `_build_history_tasks`，并让 `list_tasks` 返回 `params`。前端抽一份类型分类常量，总览页只读化并加"新鲜度"列，采集中心拆成「补历史」「更新到最新」两个弹窗、任务历史加"参数"列与"重跑"。复用既有 `ProgressTable`、`scheduler`、`progress_all`、`POST /tasks`、`POST /task/<id>/start`。

**Tech Stack:** 后端 Flask + Python（`unittest`），前端 Vue 3 + TypeScript + Element Plus + Pinia（无测试框架，验证用 `vue-tsc` 构建 + 目测）。

---

## 文件结构

后端（`AutoStockCollector-manage/`）：
- `api/routes/__init__.py` — 新增分组常量、收窄 `_build_history_tasks`、新增 `_compute_update_latest_tasks` 纯函数与 `/collect/update_latest` 路由。
- `core/scheduler/scheduler.py` — `Task.get_stats()` 与 `list_tasks()` DB 分支补 `params` 字段。
- `tests/unit/test_collect_planning.py`（新建）— 测 `_build_history_tasks` 过滤与 `_compute_update_latest_tasks` 计算。

前端（`AutoStockCollector-web/src/`）：
- `utils/collectTypes.ts`（新建）— 类型→类别/中文名映射常量。
- `api/collect.ts` — 新增 `updateLatest`、`createTask`、`startTask`（用于重跑）。
- `views/Dashboard/index.vue` — 只读化（已无操作按钮，确认即可）。
- `components/ProgressTable/index.vue` — 新增可选"新鲜度"列。
- `views/DataMonitor/index.vue` — 拆「补历史」「更新到最新」弹窗、移除静态覆盖表、任务历史加"参数"列与"重跑"。

---

## Task 1: 后端类型分组常量 + 收窄 `_build_history_tasks`

**Files:**
- Modify: `AutoStockCollector-manage/api/routes/__init__.py`（`_build_history_tasks` 约 941-979 行）
- Test: `AutoStockCollector-manage/tests/unit/test_collect_planning.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `AutoStockCollector-manage/tests/unit/test_collect_planning.py`：

```python
"""采集任务规划纯函数测试（不依赖 DB / scheduler）"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.routes import _build_history_tasks, RANGE_TYPES


class TestBuildHistoryTasks(unittest.TestCase):
    def test_history_only_contains_range_types(self):
        tasks = _build_history_tasks("2025-01-01", "2025-12-31")
        types = {t["task_type"] for t in tasks}
        # 历史采集只应包含区间类，不含快照/名录类
        self.assertEqual(types, set(RANGE_TYPES))
        self.assertNotIn("news", types)
        self.assertNotIn("fund_flow", types)
        self.assertNotIn("sector", types)
        self.assertNotIn("stock_info", types)

    def test_history_passes_dates_to_range_types(self):
        tasks = _build_history_tasks("2025-01-01", "2025-12-31", ["kline"])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["params"]["start_date"], "2025-01-01")
        self.assertEqual(tasks[0]["params"]["end_date"], "2025-12-31")

    def test_history_task_types_filter_ignores_snapshot(self):
        # 即使显式传入快照类，也不应产出
        tasks = _build_history_tasks("2025-01-01", "2025-12-31", ["kline", "news"])
        types = {t["task_type"] for t in tasks}
        self.assertEqual(types, {"kline"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd AutoStockCollector-manage && python -m unittest tests.unit.test_collect_planning -v`
Expected: FAIL —— `ImportError: cannot import name 'RANGE_TYPES'`（常量尚不存在）。

- [ ] **Step 3: 加分组常量并收窄 `_build_history_tasks`**

在 `api/routes/__init__.py` 顶部已有 import 之后（模块级，函数定义之前）加入常量：

```python
# 8 类数据按时间语义分组（采集规划唯一事实来源）
RANGE_TYPES = ["kline", "financial", "dragon_tiger", "margin"]   # 按日期区间
SNAPSHOT_TYPES = ["news", "fund_flow", "sector"]                 # 仅当前快照
CATALOG_TYPES = ["stock_info"]                                   # 全量名录
```

将 `_build_history_tasks` 整体替换为只构建区间类任务：

```python
def _build_history_tasks(start_date: str, end_date: str, task_types=None) -> list:
    """构建历史采集任务（仅区间历史类：kline/financial/dragon_tiger/margin）。

    快照类（news/fund_flow/sector）与名录类（stock_info）无历史区间概念，
    不在历史采集中构建，避免产生"选了日期不生效"的假任务。
    """
    range_tasks = {
        "kline": {"start_date": start_date, "end_date": end_date, "adjust": "qfq"},
        "financial": {"report_type": "annual", "start_date": start_date, "end_date": end_date},
        "dragon_tiger": {"start_date": start_date, "end_date": end_date},
        "margin": {"start_date": start_date, "end_date": end_date},
    }
    selected = task_types if task_types else RANGE_TYPES
    return [
        {"task_type": t, "params": range_tasks[t]}
        for t in RANGE_TYPES
        if t in selected
    ]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd AutoStockCollector-manage && python -m unittest tests.unit.test_collect_planning -v`
Expected: PASS（3 个测试全过）。

- [ ] **Step 5: 提交**

```bash
git add AutoStockCollector-manage/api/routes/__init__.py AutoStockCollector-manage/tests/unit/test_collect_planning.py
git commit -m "feat(collect): 历史采集只构建区间类任务，新增类型分组常量"
```

---

## Task 2: 增量参数计算纯函数 + `/collect/update_latest` 路由

**Files:**
- Modify: `AutoStockCollector-manage/api/routes/__init__.py`（紧接 `start_history_collection` 之后，约 1022 行后）
- Test: `AutoStockCollector-manage/tests/unit/test_collect_planning.py`（追加）

- [ ] **Step 1: 追加失败测试**

在 `tests/unit/test_collect_planning.py` 顶部 import 增加 `_compute_update_latest_tasks`：

```python
from api.routes import _build_history_tasks, RANGE_TYPES, _compute_update_latest_tasks
```

在文件末尾 `if __name__` 之前追加：

```python
class TestComputeUpdateLatest(unittest.TestCase):
    TODAY = "2026-05-29"

    def _stats(self, **overrides):
        base = {
            "kline": {"record_count": 10, "date_from": "2025-01-01", "date_to": "2026-05-20"},
            "financial": {"record_count": 5, "date_from": "2024-01-01", "date_to": "2025-12-31"},
            "dragon_tiger": {"record_count": 3, "date_from": "2026-05-01", "date_to": "2026-05-29"},
            "margin": {"record_count": 0, "date_from": None, "date_to": None},
            "news": {"record_count": 100, "date_from": None, "date_to": None},
            "fund_flow": {"record_count": 50, "date_from": None, "date_to": None},
            "sector": {"record_count": 90, "date_from": None, "date_to": None},
            "stock_info": {"record_count": 200, "date_from": None, "date_to": None},
        }
        base.update(overrides)
        return base

    def test_range_type_resumes_from_next_day(self):
        tasks, skipped = _compute_update_latest_tasks(self._stats(), ["kline"], self.TODAY)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_type"], "kline")
        self.assertEqual(tasks[0]["params"]["start_date"], "2026-05-21")  # date_to + 1
        self.assertEqual(tasks[0]["params"]["end_date"], self.TODAY)

    def test_range_type_already_latest_is_skipped(self):
        # dragon_tiger date_to == today，应跳过
        tasks, skipped = _compute_update_latest_tasks(self._stats(), ["dragon_tiger"], self.TODAY)
        self.assertEqual(tasks, [])
        self.assertIn("dragon_tiger", skipped)

    def test_range_type_no_data_uses_one_year_lookback(self):
        tasks, skipped = _compute_update_latest_tasks(self._stats(), ["margin"], self.TODAY)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["params"]["start_date"], "2025-05-29")  # today - 365d
        self.assertEqual(tasks[0]["params"]["end_date"], self.TODAY)

    def test_snapshot_type_has_no_dates(self):
        tasks, skipped = _compute_update_latest_tasks(self._stats(), ["news", "fund_flow", "sector"], self.TODAY)
        types = {t["task_type"] for t in tasks}
        self.assertEqual(types, {"news", "fund_flow", "sector"})
        for t in tasks:
            self.assertNotIn("start_date", t["params"])
        news = next(t for t in tasks if t["task_type"] == "news")
        self.assertEqual(news["params"]["limit"], 500)

    def test_catalog_type_uses_incremental_mode(self):
        tasks, skipped = _compute_update_latest_tasks(self._stats(), ["stock_info"], self.TODAY)
        self.assertEqual(tasks[0]["params"], {"mode": "incremental"})

    def test_default_selects_all_eight_types(self):
        tasks, skipped = _compute_update_latest_tasks(self._stats(), None, self.TODAY)
        handled = {t["task_type"] for t in tasks} | set(skipped)
        self.assertEqual(handled, set(RANGE_TYPES + ["news", "fund_flow", "sector", "stock_info"]))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd AutoStockCollector-manage && python -m unittest tests.unit.test_collect_planning -v`
Expected: FAIL —— `ImportError: cannot import name '_compute_update_latest_tasks'`。

- [ ] **Step 3: 实现纯函数 + 路由**

在 `api/routes/__init__.py` 中 `start_history_collection` 函数之后插入：

```python
def _compute_update_latest_tasks(stats: dict, task_types=None, today: str = None):
    """根据各类数据当前覆盖情况，计算"更新到最新"应提交的任务。

    stats: _get_collection_stats(db) 的返回，形如
           {type: {"record_count": int, "date_from": str|None, "date_to": str|None}}
    返回: (tasks, skipped)
          tasks  = [{"task_type": str, "params": dict}, ...]
          skipped = [type, ...]  # 区间类已是最新而跳过
    """
    from datetime import datetime, timedelta

    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")
    all_types = RANGE_TYPES + SNAPSHOT_TYPES + CATALOG_TYPES
    selected = task_types if task_types else all_types

    tasks, skipped = [], []
    for t in selected:
        if t in RANGE_TYPES:
            date_to = (stats.get(t) or {}).get("date_to")
            if date_to and date_to >= today:
                skipped.append(t)
                continue
            if date_to:
                start = (datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                start = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
            params = {"start_date": start, "end_date": today}
            if t == "kline":
                params["adjust"] = "qfq"
            elif t == "financial":
                params["report_type"] = "annual"
            tasks.append({"task_type": t, "params": params})
        elif t in SNAPSHOT_TYPES:
            params = {"limit": 500} if t == "news" else {}
            tasks.append({"task_type": t, "params": params})
        elif t in CATALOG_TYPES:
            tasks.append({"task_type": t, "params": {"mode": "incremental"}})
    return tasks, skipped


@api_bp.route("/collect/update_latest", methods=["POST"])
def start_update_latest():
    """一键更新到最新：区间类从 DB 最新日期补到今天，快照类抓最新，名录类增量补新。

    Body 参数:
      task_types (可选) 指定只更新哪几类，默认全部 8 类
    """
    from core.scheduler.scheduler import scheduler
    from config.database import DatabaseConfig

    data = request.get_json() or {}
    task_types = data.get("task_types")

    db = DatabaseConfig.get_database()
    stats = _get_collection_stats(db)
    tasks, skipped = _compute_update_latest_tasks(stats, task_types)

    started, failed = {}, {}
    for task_cfg in tasks:
        ttype = task_cfg["task_type"]
        try:
            task_id = scheduler.create_task(ttype, task_cfg["params"])
            scheduler.start_task(task_id)
            started[ttype] = task_id
        except Exception as e:
            failed[ttype] = str(e)

    return jsonify({
        "success": True,
        "started": started,
        "skipped": skipped,
        "failed": failed,
        "total_started": len(started),
        "timestamp": datetime.now().isoformat()
    })
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd AutoStockCollector-manage && python -m unittest tests.unit.test_collect_planning -v`
Expected: PASS（全部测试通过）。

- [ ] **Step 5: 启动服务做一次端到端冒烟（手动）**

Run: `cd AutoStockCollector-manage && python main.py`（后台），另开终端：
`curl -s -X POST http://localhost:5555/api/v1/collect/update_latest -H 'Content-Type: application/json' -d '{"task_types":["dragon_tiger"]}'`
Expected: 返回 JSON 含 `success: true`，且 `started` 或 `skipped` 含 `dragon_tiger`。

- [ ] **Step 6: 提交**

```bash
git add AutoStockCollector-manage/api/routes/__init__.py AutoStockCollector-manage/tests/unit/test_collect_planning.py
git commit -m "feat(collect): 新增 /collect/update_latest 与增量参数计算"
```

---

## Task 3: `list_tasks` 返回 `params`（任务可追溯）

**Files:**
- Modify: `AutoStockCollector-manage/core/scheduler/scheduler.py`（`Task.get_stats()` 约 127-145 行；`list_tasks()` DB 分支约 300-312 行）

- [ ] **Step 1: 在内存任务统计中加 params**

在 `Task.get_stats()` 的返回字典中（`"task_type": self.task_type,` 之后）加入：

```python
            "params": self.params,
```

- [ ] **Step 2: 在 DB 任务列表中加 params**

在 `list_tasks()` 的 `db_list` 推导中（`"task_type": t.get("task_type"),` 之后）加入：

```python
                "params": t.get("params", {}),
```

- [ ] **Step 3: 冒烟验证（手动）**

服务运行中执行：`curl -s 'http://localhost:5555/api/v1/tasks?limit=3' | python -m json.tool`
Expected: 每个 task 对象含 `params` 字段（如 `{"start_date": "...", "end_date": "..."}` 或 `{"mode": "incremental"}`）。

- [ ] **Step 4: 提交**

```bash
git add AutoStockCollector-manage/core/scheduler/scheduler.py
git commit -m "feat(scheduler): 任务列表返回 params 以支持追溯与重跑"
```

---

## Task 4: 前端类型分类常量 + collect API 扩展

**Files:**
- Create: `AutoStockCollector-web/src/utils/collectTypes.ts`
- Modify: `AutoStockCollector-web/src/api/collect.ts`

- [ ] **Step 1: 新建类型分类常量**

`AutoStockCollector-web/src/utils/collectTypes.ts`：

```ts
export type CollectCategory = 'range' | 'snapshot' | 'catalog'

export interface CollectTypeMeta {
  value: string
  label: string
  category: CollectCategory
}

export const COLLECT_TYPES: CollectTypeMeta[] = [
  { value: 'kline', label: 'K线数据', category: 'range' },
  { value: 'financial', label: '财务数据', category: 'range' },
  { value: 'dragon_tiger', label: '龙虎榜', category: 'range' },
  { value: 'margin', label: '融资融券', category: 'range' },
  { value: 'news', label: '新闻资讯', category: 'snapshot' },
  { value: 'fund_flow', label: '资金流向', category: 'snapshot' },
  { value: 'sector', label: '板块数据', category: 'snapshot' },
  { value: 'stock_info', label: '股票信息', category: 'catalog' },
]

export const RANGE_TYPES = COLLECT_TYPES.filter(t => t.category === 'range')
export const TYPE_LABEL: Record<string, string> =
  Object.fromEntries(COLLECT_TYPES.map(t => [t.value, t.label]))
```

- [ ] **Step 2: 扩展 collect API**

在 `AutoStockCollector-web/src/api/collect.ts` 的 `collectApi` 对象内（`collectHistory` 之后）加入：

```ts
  updateLatest(params: { task_types?: string[] } = {}) {
    return client.post('/api/v1/collect/update_latest', params)
  },

  createTask(task_type: string, params: Record<string, unknown>) {
    return client.post('/api/v1/tasks', { task_type, params })
  },

  startTask(id: string) {
    return client.post(`/api/v1/task/${id}/start`)
  },
```

- [ ] **Step 3: 类型检查通过**

Run: `cd AutoStockCollector-web && npx vue-tsc --noEmit`
Expected: 无报错（新文件与新方法类型正确）。

- [ ] **Step 4: 提交**

```bash
git add AutoStockCollector-web/src/utils/collectTypes.ts AutoStockCollector-web/src/api/collect.ts
git commit -m "feat(web): 新增采集类型分类常量与 updateLatest/重跑 API"
```

---

## Task 5: 总览页只读化 + ProgressTable 新鲜度列

**Files:**
- Modify: `AutoStockCollector-web/src/components/ProgressTable/index.vue`
- Modify: `AutoStockCollector-web/src/views/Dashboard/index.vue`

- [ ] **Step 1: ProgressTable 增加可选"新鲜度"列**

在 `components/ProgressTable/index.vue` 的 `<script setup>` 中，给组件加 prop（在现有 `defineProps` 处合并；若当前为 `defineProps<{ data: ...; loading?: boolean }>()`，改为）：

```ts
const props = defineProps<{
  data: any[]
  loading?: boolean
  showFreshness?: boolean
}>()

function freshness(dateTo?: string): { text: string; cls: string } {
  if (!dateTo) return { text: '—', cls: 'fresh-none' }
  const diff = Math.floor((Date.now() - new Date(dateTo).getTime()) / 86400000)
  if (diff <= 1) return { text: '最新', cls: 'fresh-ok' }
  if (diff <= 7) return { text: `${diff} 天前`, cls: 'fresh-mid' }
  return { text: `${diff} 天前`, cls: 'fresh-stale' }
}
```

在"数据区间"列之后新增一列（`v-if` 控制只在总览显示）：

```html
    <el-table-column v-if="showFreshness" label="新鲜度" width="100" align="center">
      <template #default="{ row }">
        <span :class="freshness(row.date_to).cls">{{ freshness(row.date_to).text }}</span>
      </template>
    </el-table-column>
```

在 `<style scoped>` 末尾加颜色：

```css
.fresh-ok { color: #67c23a; }
.fresh-mid { color: #909399; }
.fresh-stale { color: #e6a23c; }
.fresh-none { color: #606266; }
```

> 注：若现有 `defineProps` 是无变量形式（如 `defineProps<...>()` 未赋值给 `props`），模板中原 `data`/`loading` 引用仍可用；新增 `props` 变量不影响模板自动解包。

- [ ] **Step 2: 总览页启用新鲜度列**

在 `views/Dashboard/index.vue` 中将进度表标题从"采集状态总览"改为"数据覆盖总览"，并给 `ProgressTable` 传 `show-freshness`：

```html
              <span>数据覆盖总览</span>
```
```html
          <ProgressTable :data="collectStore.progressList" :loading="loading" show-freshness />
```

（总览页本就无采集操作按钮，无需移除；确认仅"刷新"按钮保留。）

- [ ] **Step 3: 构建与目测**

Run: `cd AutoStockCollector-web && npm run build`
Expected: 构建成功无类型错误。随后 `npm run dev`，打开 `/dashboard`，确认覆盖表出现"新鲜度"列且色级合理（落后 >7 天为橙色）。

- [ ] **Step 4: 提交**

```bash
git add AutoStockCollector-web/src/components/ProgressTable/index.vue AutoStockCollector-web/src/views/Dashboard/index.vue
git commit -m "feat(web): 总览改为数据覆盖总览并显示数据新鲜度"
```

---

## Task 6: 采集中心 —— 拆分两个采集弹窗 + 任务参数列 + 重跑

**Files:**
- Modify: `AutoStockCollector-web/src/views/DataMonitor/index.vue`
- Modify: `AutoStockCollector-web/src/router/index.ts`（标题文案）

- [ ] **Step 1: 路由标题改为"采集中心"**

`router/index.ts` 中 `data-monitor` 路由的 `meta.title` 由 `'采集监控'` 改为 `'采集中心'`（path 不变）。

- [ ] **Step 2: 工具栏改为两个采集入口**

`DataMonitor/index.vue` 模板中，将原"启动采集"按钮替换为两个按钮：

```html
        <el-button type="primary" @click="showHistoryModal = true">
          <el-icon><VideoPlay /></el-icon> 补历史
        </el-button>
        <el-button type="success" @click="openUpdateModal">
          <el-icon><Refresh /></el-icon> 更新到最新
        </el-button>
```

- [ ] **Step 3: 移除静态覆盖表（保留仪表盘=运行进度）**

删除"采集进度明细"那张 `el-card`（含 `<ProgressTable ... />`，约 29-35 行），仪表盘列改为占满宽度：将 `<el-col :span="8">` 仪表盘卡片所在 `el-row` 调整为单列：

```html
    <el-card shadow="never" class="section-card">
      <template #header><span>运行中任务进度</span></template>
      <v-chart :option="gaugeOption" style="height:200px" autoresize />
    </el-card>
```

并删除不再使用的 `ProgressTable` import。

- [ ] **Step 4: 补历史弹窗（仅区间类 + 预设）**

将原采集弹窗替换为"补历史"弹窗：

```html
    <el-dialog v-model="showHistoryModal" title="补历史数据" width="520px">
      <el-form label-width="90px">
        <el-form-item label="快捷范围">
          <el-radio-group v-model="historyPreset" @change="applyPreset">
            <el-radio-button value="last1y">近一年</el-radio-button>
            <el-radio-button value="ytd">今年以来</el-radio-button>
            <el-radio-button value="2025">2025全年</el-radio-button>
            <el-radio-button value="2024">2024全年</el-radio-button>
            <el-radio-button value="custom">自定义</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="historyDateRange" type="daterange" range-separator="至"
            start-placeholder="开始日期" end-placeholder="结束日期"
            value-format="YYYY-MM-DD" style="width:100%"
          />
        </el-form-item>
        <el-form-item label="采集类型">
          <el-checkbox-group v-model="historyTypes">
            <el-checkbox v-for="t in RANGE_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showHistoryModal = false">取消</el-button>
        <el-button type="primary" :loading="historyLoading" @click="handleHistory">开始采集</el-button>
      </template>
    </el-dialog>
```

- [ ] **Step 5: 更新到最新弹窗（全类型 + 覆盖预览）**

新增弹窗：

```html
    <el-dialog v-model="showUpdateModal" title="更新到最新" width="560px">
      <el-table :data="updateRows" size="small">
        <el-table-column width="50">
          <template #default="{ row }">
            <el-checkbox v-model="row.checked" />
          </template>
        </el-table-column>
        <el-table-column prop="label" label="数据类型" width="120" />
        <el-table-column label="当前覆盖" min-width="180">
          <template #default="{ row }">{{ row.preview }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showUpdateModal = false">取消</el-button>
        <el-button type="success" :loading="updateLoading" @click="handleUpdate">开始更新</el-button>
      </template>
    </el-dialog>
```

- [ ] **Step 6: 脚本逻辑（预设、提交、预览、重跑）**

`<script setup>` 中替换/新增（删除旧的 `showCollectModal`/`collectForm`/`collectDateRange`/`taskTypeOptions`/`handleStartCollect`）：

```ts
import { RANGE_TYPES, COLLECT_TYPES, TYPE_LABEL } from '@/utils/collectTypes'

// 补历史
const showHistoryModal = ref(false)
const historyLoading = ref(false)
const historyPreset = ref('last1y')
const historyDateRange = ref<[string, string] | null>(null)
const historyTypes = ref<string[]>(RANGE_TYPES.map(t => t.value))

function fmt(d: Date) { return d.toISOString().slice(0, 10) }
function applyPreset(p: string) {
  const today = new Date()
  if (p === 'last1y') {
    const s = new Date(today); s.setDate(s.getDate() - 365)
    historyDateRange.value = [fmt(s), fmt(today)]
  } else if (p === 'ytd') {
    historyDateRange.value = [`${today.getFullYear()}-01-01`, fmt(today)]
  } else if (p === '2025') {
    historyDateRange.value = ['2025-01-01', '2025-12-31']
  } else if (p === '2024') {
    historyDateRange.value = ['2024-01-01', '2024-12-31']
  }
}
applyPreset('last1y')

async function handleHistory() {
  if (!historyDateRange.value?.[0]) { ElMessage.warning('请选择日期范围'); return }
  historyLoading.value = true
  try {
    await collectApi.collectHistory({
      start_date: historyDateRange.value[0],
      end_date: historyDateRange.value[1],
      task_types: historyTypes.value,
    })
    ElMessage.success('历史采集任务已启动')
    showHistoryModal.value = false
    await loadTasks()
  } finally { historyLoading.value = false }
}

// 更新到最新
const showUpdateModal = ref(false)
const updateLoading = ref(false)
const updateRows = ref<{ value: string; label: string; category: string; checked: boolean; preview: string }[]>([])

function openUpdateModal() {
  const statByType: Record<string, any> = {}
  collectStore.progressList.forEach(p => { statByType[p.task_type] = p })
  updateRows.value = COLLECT_TYPES.map(t => {
    const st = statByType[t.value] || {}
    let preview = ''
    if (t.category === 'range') {
      preview = st.date_to ? `已到 ${st.date_to}，将补到今天` : '暂无数据，将补近一年'
    } else if (t.category === 'snapshot') {
      preview = '抓取最新快照'
    } else {
      preview = '增量补充新增股票'
    }
    return { value: t.value, label: t.label, category: t.category, checked: true, preview }
  })
  showUpdateModal.value = true
}

async function handleUpdate() {
  const types = updateRows.value.filter(r => r.checked).map(r => r.value)
  if (!types.length) { ElMessage.warning('请至少选择一类'); return }
  updateLoading.value = true
  try {
    const res = await collectApi.updateLatest({ task_types: types })
    const skipped = res.data?.skipped || []
    ElMessage.success(skipped.length ? `已启动，${skipped.length} 类已是最新跳过` : '更新任务已启动')
    showUpdateModal.value = false
    await loadTasks()
  } finally { updateLoading.value = false }
}

// 重跑：completed/failed/cancelled 均按原参数新建并启动
async function handleRerun(row: any) {
  const res = await collectApi.createTask(row.task_type, row.params || {})
  const id = res.data?.task_id
  if (id) { await collectApi.startTask(id); ElMessage.success('已按原参数重跑'); await loadTasks() }
}
```

- [ ] **Step 7: 任务历史表加"参数"列与"重跑"**

在任务历史 `el-table` 中，"创建时间"列后新增"参数"列：

```html
        <el-table-column label="参数" min-width="200">
          <template #default="{ row }">
            <span v-if="row.params?.start_date">{{ row.params.start_date }} ~ {{ row.params.end_date }}</span>
            <span v-else-if="row.params?.mode">{{ row.params.mode }}</span>
            <span v-else>快照</span>
          </template>
        </el-table-column>
```

将"操作"列改为对所有终态任务提供重跑：

```html
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button v-if="row.status === 'running' || row.status === 'pending'"
              size="small" type="warning" @click="handleCancel(row.task_id)">取消</el-button>
            <el-button v-else size="small" type="primary" @click="handleRerun(row)">重跑</el-button>
          </template>
        </el-table-column>
```

删除旧的 `handleRetry`（被 `handleRerun` 取代），并移除其对 `collectApi.retryTask` 的调用。

- [ ] **Step 8: 构建与目测**

Run: `cd AutoStockCollector-web && npm run build`
Expected: 构建成功无类型错误。`npm run dev` 后打开 `/data-monitor`：
- 「补历史」弹窗只列 4 个区间类，预设按钮能填日期；
- 「更新到最新」弹窗列出 8 类并显示覆盖预览；
- 任务历史出现"参数"列，终态任务有"重跑"按钮；
- 页面不再有重复的覆盖明细表。

- [ ] **Step 9: 提交**

```bash
git add AutoStockCollector-web/src/views/DataMonitor/index.vue AutoStockCollector-web/src/router/index.ts
git commit -m "feat(web): 采集中心拆分补历史/更新到最新弹窗，任务支持参数展示与重跑"
```

---

## Self-Review 记录

- **Spec 覆盖**：①类型分类→Task1/Task4；②页面职责（总览只读/采集中心操作）→Task5/Task6；③覆盖新鲜度→Task5；④补历史→Task1+Task6；⑤更新到最新→Task2+Task6；⑥任务可追溯+重跑→Task3+Task6。无遗漏。
- **占位符**：无 TBD/TODO，所有步骤含具体代码与命令。
- **类型一致性**：后端 `RANGE_TYPES/SNAPSHOT_TYPES/CATALOG_TYPES`、`_build_history_tasks`、`_compute_update_latest_tasks` 命名前后一致；前端 `COLLECT_TYPES/RANGE_TYPES/TYPE_LABEL`、`updateLatest/createTask/startTask`、`handleRerun` 一致；任务行 `params` 字段由 Task3 提供、Task6 消费，对齐。
- **测试现实**：后端 `unittest`（纯函数 TDD），前端无测试框架故以 `vue-tsc/npm run build` + 目测验证，未引入新测试栈（YAGNI）。
