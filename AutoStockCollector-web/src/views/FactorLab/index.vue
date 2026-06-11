<template>
  <div class="factor-lab">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- ═══════════ 因子管理 ═══════════ -->
      <el-tab-pane label="因子管理" name="registry">
        <div class="section-toolbar">
          <el-button type="primary" size="small" @click="fetchFactors">刷新</el-button>
          <el-select v-model="filterGroup" placeholder="全部分组" size="small" clearable style="width:120px">
            <el-option v-for="g in allGroups" :key="g" :label="g" :value="g" />
          </el-select>
          <el-checkbox v-model="showValidOnly" size="small" style="margin-left:4px">
            仅显示有效因子
          </el-checkbox>
          <span style="flex:1" />
          <span class="weight-sum-label">
            权重总和: <b :class="weightSumAlertClass">{{ weightSum.toFixed(1) }}</b>
            <span v-if="weightSumAlertClass === 'weight-alert'" style="color:#f56c6c;font-size:11px;margin-left:4px">≠ {{ weightTarget }}</span>
          </span>
          <el-dropdown trigger="click" size="small" @command="applyWeightPreset">
            <el-button size="small">
              <span>一键科学赋权</span><el-icon style="margin-left:4px"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="ic">IC均值加权</el-dropdown-item>
                <el-dropdown-item command="icir">IR（信息比率）加权</el-dropdown-item>
                <el-dropdown-item command="group-equal" divided>分组等权</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button size="small" @click="resetWeights">恢复默认</el-button>
          <el-button type="success" size="small" @click="debouncedSave" :loading="saving">保存权重</el-button>
          <el-button type="warning" size="small" @click="previewWeights" :loading="previewLoading">预览排名</el-button>
          <el-tooltip content="切换紧凑/默认视图" placement="top">
            <el-button size="small" circle @click="toggleDensity">
              <span style="font-size:14px">{{ compactView ? '⊞' : '⊟' }}</span>
            </el-button>
          </el-tooltip>
        </div>
        <el-table :data="filteredFactors" stripe border size="small" max-height="600" highlight-current-row
                  :class="compactView ? 'compact-table' : ''" row-class-name="factor-row">
          <el-table-column prop="group" label="分组" width="90" />
          <el-table-column prop="name" label="因子名" width="140" />
          <el-table-column label="有效性" width="180">
            <template #default="{ row }">
              <span v-if="effectivenessMap[row.name]" class="validity-cell">
                <el-tag :type="(effectivenessMap[row.name]?.ic ?? 0) > 0 ? 'success' : 'danger'" size="small" class="validity-status-tag">
                  {{ (effectivenessMap[row.name]?.ic ?? 0) > 0 ? '有效' : '无效' }}
                </el-tag>
                <span class="validity-ic" :class="(effectivenessMap[row.name]?.ic ?? 0) > 0 ? 'ic-positive' : 'ic-negative'">
                  IC {{ (effectivenessMap[row.name]?.ic ?? 0).toFixed(4) }}
                </span>
                <span class="validity-sep">|</span>
                <span class="validity-ir" :class="(effectivenessMap[row.name]?.icir ?? 0) > 0.3 ? 'ir-good' : 'ir-weak'">
                  IR {{ (effectivenessMap[row.name]?.icir ?? 0).toFixed(2) }}
                </span>
              </span>
              <span v-else class="validity-na">-</span>
            </template>
          </el-table-column>
          <el-table-column label="分布" width="110">
            <template #default="{ row }">
              <el-popover placement="top" :width="260" trigger="hover">
                <template #reference>
                  <el-tag size="small" type="info" style="cursor:pointer">
                    {{ factorDistMap[row.name]?.count ?? '-' }} 只
                  </el-tag>
                </template>
                <div style="font-size:12px;line-height:1.8">
                  <div>均值: <b>{{ factorDistMap[row.name]?.mean?.toFixed(3) ?? '-' }}</b></div>
                  <div>标准差: <b>{{ factorDistMap[row.name]?.std?.toFixed(3) ?? '-' }}</b></div>
                  <div>中位数: <b>{{ factorDistMap[row.name]?.median?.toFixed(3) ?? '-' }}</b></div>
                  <div>min/max: <b>{{ factorDistMap[row.name]?.min?.toFixed(2) ?? '-' }}</b> / <b>{{ factorDistMap[row.name]?.max?.toFixed(2) ?? '-' }}</b></div>
                </div>
              </el-popover>
            </template>
          </el-table-column>
          <el-table-column label="方向" width="56" align="center">
            <template #default="{ row }">
              <span class="direction-badge" :class="row.inverse ? 'direction-inverse' : 'direction-normal'">
                <span class="dir-arrow">{{ row.inverse ? '↓' : '↑' }}</span>
                <span class="dir-label">{{ row.inverse ? '逆' : '正' }}</span>
              </span>
            </template>
          </el-table-column>
          <el-table-column label="当前权重" width="200">
            <template #default="{ row }">
              <el-slider v-model="row._weight" :min="0" :max="5" :step="0.1"
                         show-input size="small" input-size="small" style="width:160px"
                         @change="onWeightChange" />
            </template>
          </el-table-column>
          <el-table-column label="默认权重" width="70" align="center">
            <template #default="{ row }"> {{ row.default_weight }} </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ═══════════ 因子选股 ═══════════ -->
      <el-tab-pane label="因子选股" name="stock-picker">
        <div class="section-toolbar">
          <el-form :inline="true" size="small">
            <el-form-item label="计算天数">
              <el-select v-model="scDaysBack" style="width:120px">
                <el-option label="1天前" :value="1" />
                <el-option label="3天前" :value="3" />
                <el-option label="5天前" :value="5" />
                <el-option label="10天前" :value="10" />
              </el-select>
            </el-form-item>
            <el-form-item label="最低分">
              <el-input-number v-model="scMinScore" :min="0" :max="100" :step="5" size="small" style="width:100px" />
            </el-form-item>
            <el-form-item label="数量">
              <el-select v-model="scLimit" style="width:100px">
                <el-option label="50" :value="50" />
                <el-option label="100" :value="100" />
                <el-option label="200" :value="200" />
                <el-option label="500" :value="500" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="computeScoresAsync" :disabled="progressRunning && progressMode==='score'">计算评分</el-button>
              <el-button v-if="progressRunning && progressMode==='score'" type="danger" @click="cancelScore">取消</el-button>
              <el-button v-if="scResult" size="small" @click="exportCSV">导出CSV</el-button>
            </el-form-item>
          </el-form>
          <span v-if="scResult" style="color:#909399;font-size:12px;margin-left:8px">
            {{ scWeightLabel }} · {{ scResult.trade_date }}
          </span>
        </div>

        <template v-if="scResult">
          <el-descriptions :column="3" border size="small" style="margin-bottom:12px">
            <el-descriptions-item label="计算日期">{{ scResult.trade_date }}</el-descriptions-item>
            <el-descriptions-item label="总样本">{{ scResult.total }} 只</el-descriptions-item>
            <el-descriptions-item label="返回数量">{{ scResult.rows.length }} 只</el-descriptions-item>
          </el-descriptions>

          <el-table ref="scTableRef" :data="scResult.rows" stripe border size="small" max-height="600"
                    @row-click="openStockDrawer">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="code" label="代码" width="100" />
            <el-table-column prop="name" label="名称" width="120" />
            <el-table-column prop="industry" label="行业" width="120" />
            <el-table-column prop="score" label="综合分" width="100" sortable>
              <template #default="{ row }">
                <el-tag :type="row.score >= 60 ? 'success' : row.score >= 40 ? 'warning' : 'info'">
                  {{ row.score }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="因子明细" min-width="300">
              <template #default="{ row }">
                <div class="factor-bars" v-if="row.factors">
                  <div v-for="(v, k) in row.factors" :key="k" class="factor-bar-item">
                    <span class="fb-label">{{ k }}</span>
                    <el-progress :percentage="Math.round((v+3)/6*100)" :stroke-width="10" size="small"
                                 :color="v > 0 ? '#67c23a' : '#f56c6c'" />
                  </div>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else description="点击「计算评分」查看因子选股结果" />
      </el-tab-pane>

      <!-- ═══════════ IC回测 ═══════════ -->
      <el-tab-pane label="IC回测" name="backtest">
        <div class="section-toolbar">
          <el-form :inline="true" size="small">
            <el-form-item label="回测日期">
              <el-select v-model="btDaysAgo" style="width:140px">
                <el-option label="10天前" :value="10" />
                <el-option label="20天前" :value="20" />
                <el-option label="40天前" :value="40" />
                <el-option label="60天前" :value="60" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="runICTest" :disabled="btRunning">运行回测</el-button>
              <el-button v-if="btRunning" type="danger" @click="cancelICTest">取消</el-button>
            </el-form-item>
          </el-form>
        </div>

        <div v-if="btRunning" class="bt-progress">
          <div class="bt-progress-bar">
            <el-progress :percentage="btProgress" :stroke-width="18"
                         :status="btStatus === 'failed' ? 'exception' : undefined" />
          </div>
          <div class="bt-progress-step">{{ btStep }}</div>
        </div>

        <template v-if="btHistory.length > 0">
          <el-timeline style="padding:0">
            <el-timeline-item v-for="(h, hi) in btHistory" :key="h.id"
                              :timestamp="'回测截止: ' + h.test_date"
                              placement="top"
                              :color="h.bestICVal > 0 ? '#67c23a' : '#f56c6c'"
                              :hollow="hi > 0">
              <!-- Metric Cards Row -->
              <div class="bt-metrics">
                <div class="bt-metric-card" v-for="(row, ri) in h.compositeTable" :key="ri">
                  <div class="bt-metric-title">{{ row.period }}</div>
                  <div class="bt-metric-row">
                    <span class="bt-metric-label">IC</span>
                    <span class="bt-metric-val" :class="row.ic > 0 ? 'green' : 'red'">
                      {{ Number(row.ic).toFixed(4) }}
                      <span v-if="hi < btHistory.length - 1" class="trend-arrow" :class="getTrendClass(h, ri, 'ic')">{{ getTrendArrow(h, ri, 'ic') }}</span>
                    </span>
                  </div>
                  <div class="bt-metric-row">
                    <span class="bt-metric-label">t-stat</span>
                    <span class="bt-metric-val" :class="(row.tstat||0) > 2 ? 'green' : (row.tstat||0) < -2 ? 'red' : ''">
                      {{ row.tstat != null ? Number(row.tstat).toFixed(3) : '-' }}
                      <span v-if="hi < btHistory.length - 1" class="trend-arrow" :class="getTrendClass(h, ri, 'tstat')">{{ getTrendArrow(h, ri, 'tstat') }}</span>
                    </span>
                  </div>
                  <div class="bt-metric-row">
                    <span class="bt-metric-label">ICIR</span>
                    <span class="bt-metric-val" :class="(row.icir||0) > 0.3 ? 'green' : (row.icir||0) < -0.3 ? 'red' : ''">
                      {{ row.icir != null ? Number(row.icir).toFixed(3) : '-' }}
                      <span v-if="hi < btHistory.length - 1" class="trend-arrow" :class="getTrendClass(h, ri, 'icir')">{{ getTrendArrow(h, ri, 'icir') }}</span>
                    </span>
                  </div>
                  <div class="bt-metric-row">
                    <span class="bt-metric-label">Spread</span>
                    <span class="bt-metric-val" :class="(row.spread||0) > 0 ? 'green' : 'red'">
                      {{ row.spread > 0 ? '+' : '' }}{{ Number(row.spread).toFixed(2) }}
                      <span v-if="hi < btHistory.length - 1" class="trend-arrow" :class="getTrendClass(h, ri, 'spread')">{{ getTrendArrow(h, ri, 'spread') }}</span>
                    </span>
                  </div>
                  <div class="bt-metric-row">
                    <span class="bt-metric-label">样本</span>
                    <span class="bt-metric-val">{{ row.n }}</span>
                  </div>
                </div>
              </div>

              <!-- Quintile Chart + Factor IC side by side -->
              <div class="bt-chart-row">
                <div class="bt-chart-box" :class="{ 'bt-chart-expanded': expandedChart === hi + '-q' }">
                  <div class="bt-chart-header">
                    <span class="bt-chart-title">分组收益</span>
                    <el-button size="small" text @click.stop="toggleExpandChart(hi + '-q')" class="bt-expand-btn">
                      {{ expandedChart === hi + '-q' ? '⊟' : '⊞' }}
                    </el-button>
                  </div>
                  <div :style="{ height: expandedChart === hi + '-q' ? '400px' : '200px' }">
                    <v-chart :option="quintileChartOption(h.compositeTable[0])" autoresize style="height:100%;width:100%" />
                  </div>
                </div>
                <div class="bt-chart-box" :class="{ 'bt-chart-expanded': expandedChart === hi + '-fic' }">
                  <div class="bt-chart-header">
                    <span class="bt-chart-title">单因子 IC</span>
                    <el-button size="small" text @click.stop="toggleExpandChart(hi + '-fic')" class="bt-expand-btn">
                      {{ expandedChart === hi + '-fic' ? '⊟' : '⊞' }}
                    </el-button>
                  </div>
                  <div :style="{ height: expandedChart === hi + '-fic' ? '400px' : '200px' }">
                    <v-chart :option="factorICChartOption(h.factorTable)" autoresize style="height:100%;width:100%" />
                  </div>
                </div>
              </div>

              <!-- Delete button -->
              <div style="text-align:right;margin-top:4px">
                <el-button size="small" text type="danger" @click="removeBtHistory(h.id)">删除</el-button>
              </div>
            </el-timeline-item>
          </el-timeline>

          <!-- History trend comparison -->
          <div v-if="btHistory.length >= 2" class="bt-trend-section">
            <el-button class="bt-trend-toggle" @click="showBtTrend = !showBtTrend" text size="small">
              {{ showBtTrend ? '收起趋势图' : '📈 IC趋势对比' }}
            </el-button>
            <div v-if="showBtTrend" class="bt-trend-chart">
              <v-chart :option="btTrendOption" autoresize style="height:100%;width:100%" />
            </div>
          </div>

          <div style="text-align:center;margin-top:12px">
            <el-button size="small" text type="info" @click="clearBtHistory">清空全部历史</el-button>
          </div>
        </template>
        <el-empty v-else-if="!btRunning" description="点击「运行回测」开始IC测试" :image-size="80" />
      </el-tab-pane>

      <!-- ═══════════ 因子相关性 ═══════════ -->
      <el-tab-pane label="因子相关性" name="correlation">
        <div class="section-toolbar">
          <el-form :inline="true" size="small">
            <el-form-item label="截面对比日">
              <el-select v-model="corrDaysBack" style="width:120px">
                <el-option label="1天前" :value="1" />
                <el-option label="5天前" :value="5" />
                <el-option label="10天前" :value="10" />
              </el-select>
            </el-form-item>
            <el-form-item label="因子范围">
              <el-select v-model="corrFactorScope" multiple collapse-tags collapse-tags-tooltip
                         style="width:200px" placeholder="全部因子">
                <el-option v-for="f in factors" :key="f.name" :label="f.name" :value="f.name" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="computeCorrelationAsync" :disabled="corrRunning">计算相关性</el-button>
              <el-button v-if="corrRunning" type="danger" @click="cancelCorrelation">取消</el-button>
            </el-form-item>
          </el-form>
          <div style="font-size:11px;color:#606880;line-height:1.4">
            <div>内部使用 <b>90天K线</b> 计算因子值，以确保统计稳定性</div>
            <div v-if="corrFactorScope.length > 0">已选 {{ corrFactorScope.length }} 个因子</div>
          </div>
        </div>
        <template v-if="corrResult">
          <div class="heatmap-wrapper">
            <v-chart :option="heatmapOption" autoresize style="height:600px;width:100%" />
          </div>
          <div class="corr-legend">
            <span v-for="c in heatmapLegend" :key="c.label" class="corr-legend-item">
              <span :style="{ background: c.color, display:'inline-block', width:14, height:14, borderRadius:2, marginRight:4, verticalAlign:'middle' }"></span>
              {{ c.label }}
            </span>
          </div>
        </template>
        <el-empty v-else description="点击「计算相关性」查看因子间相关性热力图" />
      </el-tab-pane>

      <!-- ═══════════ 因子缓存 ═══════════ -->
      <el-tab-pane label="因子缓存" name="cache">
        <div class="section-toolbar">
          <el-button type="primary" size="small" @click="fetchCacheStatus">刷新</el-button>
          <el-button type="warning" size="small" @click="triggerCacheUpdate" :loading="cacheLoading">
            触发全量更新
          </el-button>
        </div>
        <template v-if="cacheStatus">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="缓存记录数">{{ cacheStatus.total_cached }}</el-descriptions-item>
            <el-descriptions-item label="因子数量">{{ cacheStatus.factor_count }}</el-descriptions-item>
            <el-descriptions-item label="最后更新">{{ cacheStatus.latest_update || '无' }}</el-descriptions-item>
            <el-descriptions-item label="已过期(小时)">{{ cacheStatus.stale_hours ?? '无' }}</el-descriptions-item>
          </el-descriptions>
        </template>
        <el-empty v-else description="加载中..." />
      </el-tab-pane>

      <!-- ═══════════ 使用说明 ═══════════ -->
      <el-tab-pane label="使用说明" name="help">
        <el-card shadow="never" class="help-card">
          <h3>🚀 因子平台使用说明</h3>
          <el-divider />

          <h4>📌 平台概述</h4>
          <p>因子平台是一套从因子定义→权重调优→股票筛选→IC验证→相关性分析的完整工作流。
          当前系统内置 <b>19 个量化因子</b>，覆盖技术面(7个)、资金面(5个)、情绪面(5个)三大类，
          另有 AI 模型因子(2个)用于机器学习选股。</p>

          <el-divider />

          <h4>📖 各功能页说明</h4>

          <h5>① 因子管理</h5>
          <p>列出所有已注册因子及其元信息：</p>
          <ul>
            <li><b>分组</b> — 因子所属类别（技术面/资金面/情绪面）</li>
            <li><b>分布</b> — Hover查看该因子在全市场的均值、标准差、中位数、极值，了解因子数值特征</li>
            <li><b>方向</b> — 正向因子值越高越好，逆向因子值越低越好（IC测试时自动处理方向）</li>
            <li><b>权重</b> — 拖动滑块(0~5)调整各因子重要度，点击「保存权重」写入注册表，或点击「预览排名」立即查看效果</li>
          </ul>

          <h5>② 因子选股</h5>
          <p>使用当前权重（或自定义预览权重）为全市场股票打分排名：</p>
          <ul>
            <li><b>计算天数</b> — 选择最近第几个交易日的数据计算</li>
            <li><b>最低分</b> — 过滤低于该综合分的股票</li>
            <li><b>数量</b> — 返回前N只股票</li>
            <li><b>结果</b> — 按综合分降序排列，每行展示各因子标准化值(−3~+3)的进度条，绿色=正值(利好)，红色=负值</li>
            <li><b>点击行</b> — 弹出抽屉展示因子雷达图 + 明细表</li>
            <li><b>导出CSV</b> — 含BOM头，Excel可直接打开</li>
          </ul>

          <h5>③ IC回测</h5>
          <p>截面信息系数(Information Coefficient)测试，衡量因子对未来收益的预测能力：</p>
          <ul>
            <li><b>IC</b> — 因子综合分与未来N日收益的Spearman秩相关系数，>0 表示高分股未来跑赢</li>
            <li><b>t-stat</b> — IC的t统计量，绝对值>2 表示统计显著</li>
            <li><b>ICIR</b> — IC与IC标准差的比值，>0.3 表示信号稳定</li>
            <li><b>分组收益</b> — 按综合分5等分(Q1最高→Q5最低)，观察收益是否单调递减（好因子的特征）</li>
            <li><b>Spread</b> — Q1 − Q5 收益差，越大说明因子区分度越好</li>
            <li><b>历史记录</b> — 多次运行结果自动保存到 localStorage，刷新不丢失，支持单条删除和全部清空</li>
          </ul>

          <h5>④ 因子相关性</h5>
          <p>计算全市场下所有因子两两之间的 Spearman 秩相关系数：</p>
          <ul>
            <li><b>热力图</b> — 红色=正相关，绿色=负相关，颜色深浅表示相关强度</li>
            <li><b>用途</b> — 发现高度相关的冗余因子（如 |r|>0.7），可考虑降权或合并，避免多重共线性</li>
          </ul>

          <h5>⑤ 因子缓存</h5>
          <p>部分因子依赖预计算缓存（如龙虎榜、资金流等外部数据）：</p>
          <ul>
            <li>查看最后更新时间和数据新鲜度（过期小时数）</li>
            <li>数据过期时点击「触发全量更新」异步刷新缓存</li>
          </ul>

          <el-divider />

          <h4>🧩 如何添加新因子</h4>
          <p>在 <code>modules/workflow/factor_miner/factors/</code> 下创建 Python 文件，用 <code>@register</code> 装饰器注册：</p>
          <pre class="help-code">
<span style="color:#7c8db0"># 1. 在 factors/ 目录下新建文件，如 my_factor.py</span>
<span style="color:#c792ea">@register</span>
<span style="color:#82aaff">class</span> <span style="color:#ffcb6b">MyFactor</span>(<span style="color:#c792ea">Factor</span>):
    <span style="color:#7c8db0"># 因子元信息</span>
    meta = FactorMeta(
        name        = <span style="color:#c3e88d">'my_signal'</span>,      <span style="color:#7c8db0"># 唯一标识名</span>
        inverse     = <span style="color:#f78c6c">False</span>,           <span style="color:#7c8db0"># True=值越低越好</span>
        group       = <span style="color:#c3e88d">'衍生'</span>,          <span style="color:#7c8db0"># 分组名</span>
        description = <span style="color:#c3e88d">'我的自定义因子'</span>, <span style="color:#7c8db0"># 说明</span>
    )

    <span style="color:#82aaff">def</span> <span style="color:#ffcb6b">compute</span>(<span style="color:#f78c6c">self</span>, code, store):
        <span style="color:#7c8db0"># code: 股票代码, store: 数据访问对象</span>
        klines = store.kline_map.get(code, [])
        <span style="color:#82aaff">if</span> <span style="color:#f78c6c">len</span>(klines) < <span style="color:#f78c6c">20</span>:
            <span style="color:#82aaff">return</span> <span style="color:#89ddff">None</span>  <span style="color:#7c8db0"># 数据不足时返回 None</span>
        ret = (klines[-<span style="color:#f78c6c">1</span>][<span style="color:#c3e88d">'close'</span>] - klines[<span style="color:#f78c6c">0</span>][<span style="color:#c3e88d">'close'</span>]) / klines[<span style="color:#f78c6c">0</span>][<span style="color:#c3e88d">'close'</span>] * <span style="color:#f78c6c">100</span>
        <span style="color:#82aaff">return</span> ret  <span style="color:#7c8db0"># 返回 float 或 None</span></pre>
          <p style="margin-top:8px">添加后重启后端即可自动发现并注册，前端刷新后出现在因子管理列表中。</p>

          <el-divider />

          <h4>💡 最佳实践</h4>
          <ul>
            <li><b>权重调试流程</b>：调整权重 → 预览排名 → 运行IC回测 → 观察单调性 → 调整权重 → 重复</li>
            <li><b>避免过拟合</b>：不要针对单一日期反复调权重，应观察多期IC的稳定性</li>
            <li><b>因子去冗余</b>：相关性 >0.7 的两个因子保留IC更高的那个，或降低其中一个的权重</li>
            <li><b>数据新鲜度</b>：因子缓存超过24小时应考虑触发更新，确保使用最新数据计算</li>
          </ul>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- ═══════════ 进度对话框 ═══════════ -->
    <el-dialog v-model="progressVisible" :title="progressTitle" width="480px"
               :close-on-click-modal="false" :show-close="true" align-center
               :close-on-press-escape="!progressRunning">
      <div class="sc-progress-box">
        <div class="sc-progress-step">{{ progressStep }}</div>
        <div class="sc-progress-bar-wrap">
          <el-progress :percentage="progressPct" :stroke-width="20"
                       :status="progressStatus === 'failed' ? 'exception'
                              : progressStatus === 'completed' ? 'success' : undefined"
                       :color="progressPct < 50 ? '#409eff'
                              : progressPct < 80 ? '#e6a23c' : '#67c23a'"
                       :stroke-linecap="'round'" />
        </div>
        <div class="sc-progress-eta" v-if="progressRunning && progressPct > 0 && progressPct < 100">
          已用 {{ elapsedStr }} · 预计剩余 {{ etaStr }}
        </div>
        <div v-if="progressStatus === 'completed'" style="margin-top:14px;text-align:center">
          <el-button type="primary" @click="progressVisible = false; progressStatus = ''">查看结果</el-button>
        </div>
        <div v-if="progressStatus === 'failed'" style="margin-top:14px;text-align:center;color:#f56c6c;font-size:13px">
          计算失败: {{ progressStep }}<br>
          <el-button size="small" style="margin-top:6px" @click="progressVisible = false; progressStatus = ''">关闭</el-button>
        </div>
        <div v-if="progressStatus === 'cancelled'" style="margin-top:14px;text-align:center;color:#e6a23c">
          已取消
        </div>
        <div class="sc-progress-hint" v-if="progressRunning">
          对话框可关闭，计算在后台继续运行
        </div>
      </div>
    </el-dialog>

    <!-- ═══════════ 预览结果对话框 ═══════════ -->
    <el-dialog v-model="previewVisible" title="权重预览 — 按当前权重重算排名" width="80%" top="5vh">
      <template v-if="previewResult">
        <el-descriptions :column="3" border size="small" style="margin-bottom:12px">
          <el-descriptions-item label="总样本">{{ previewResult.total }} 只</el-descriptions-item>
          <el-descriptions-item label="返回数量">{{ previewResult.rows.length }} 只</el-descriptions-item>
          <el-descriptions-item label="日期">{{ previewResult.trade_date }}</el-descriptions-item>
        </el-descriptions>
        <el-table :data="previewResult.rows" stripe border size="small" max-height="500">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="code" label="代码" width="100" />
          <el-table-column prop="name" label="名称" width="120" />
          <el-table-column prop="industry" label="行业" width="120" />
          <el-table-column prop="score" label="综合分" width="100" sortable>
            <template #default="{ row }">
              <el-tag :type="row.score >= 60 ? 'success' : row.score >= 40 ? 'warning' : 'info'">
                {{ row.score }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="因子明细" min-width="300">
            <template #default="{ row }">
              <div class="factor-bars" v-if="row.factors">
                <div v-for="(v, k) in row.factors" :key="k" class="factor-bar-item">
                  <span class="fb-label">{{ k }}</span>
                  <el-progress :percentage="Math.round((v+3)/6*100)" :stroke-width="10" size="small"
                               :color="v > 0 ? '#67c23a' : '#f56c6c'" />
                </div>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <div v-else style="text-align:center;padding:40px;color:#909399">计算中...</div>
    </el-dialog>

    <!-- ═══════════ IC回测详情抽屉 ═══════════ -->
    <el-drawer v-model="btDetailDrawerVisible" :title="btDetailTitle" size="400px" direction="rtl">
      <template v-if="btDetailData.length > 0">
        <el-table :data="btDetailData" stripe border size="small" max-height="600">
          <el-table-column prop="period" label="周期" width="100" />
          <el-table-column prop="value" label="数值" min-width="120">
            <template #default="{ row }">
              <span :style="{ color: parseFloat(row.value) > 0 ? '#67c23a' : parseFloat(row.value) < 0 ? '#f56c6c' : '', fontWeight: 600 }">
                {{ row.value }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>

    <!-- ═══════════ 股票详情抽屉 ═══════════ -->
    <el-drawer v-model="stockDrawerVisible" :title="stockDrawerTitle" size="500px" direction="rtl">
      <template v-if="stockDrawerData">
        <el-descriptions :column="2" border size="small" style="margin-bottom:16px">
          <el-descriptions-item label="代码">{{ stockDrawerData.code }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ stockDrawerData.name }}</el-descriptions-item>
          <el-descriptions-item label="行业">{{ stockDrawerData.industry }}</el-descriptions-item>
          <el-descriptions-item label="综合分">
            <el-tag :type="stockDrawerData.score >= 60 ? 'success' : stockDrawerData.score >= 40 ? 'warning' : 'info'">
              {{ stockDrawerData.score }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <h4 style="margin-bottom:8px">因子雷达图</h4>
        <div style="height:360px">
          <v-chart :option="radarOption" autoresize style="height:100%;width:100%" />
        </div>
        <h4 style="margin:16px 0 8px">因子明细</h4>
        <el-table :data="stockDrawerFactorTable" stripe border size="small" max-height="400">
          <el-table-column prop="name" label="因子" width="140" />
          <el-table-column prop="value" label="标准化值" width="100">
            <template #default="{ row }">
              <span :style="{ color: row.value > 0 ? '#67c23a' : '#f56c6c', fontWeight: 600 }">{{ row.value }}</span>
            </template>
          </el-table-column>
          <el-table-column label="强度" min-width="160">
            <template #default="{ row }">
              <el-progress :percentage="Math.round((row.value+3)/6*100)" :stroke-width="14" size="small"
                           :color="row.value > 0 ? '#67c23a' : '#f56c6c'" />
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { factorApi } from '@/api/factor'

import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart, BarChart, LineChart } from 'echarts/charts'
import { RadarComponent, TooltipComponent, VisualMapComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([RadarChart, BarChart, LineChart, RadarComponent, TooltipComponent, VisualMapComponent, GridComponent, LegendComponent, CanvasRenderer])

const LS_KEY = 'factorlab_bt_history'

/* ── tab ── */
const activeTab = ref('registry')

/* ── 因子管理 ── */
const factors = ref<any[]>([])
const saving = ref(false)
const previewLoading = ref(false)
const previewVisible = ref(false)
const previewResult = ref<any>(null)
const factorDistMap = ref<Record<string, any>>({})
const effectivenessMap = ref<Record<string, any>>({})
const filterGroup = ref('')
const showValidOnly = ref(false)
const compactView = ref(false)
const weightTarget = ref(1)
const weightPresetMode = ref('')
const weightSum = computed(() => factors.value.reduce((s, f) => s + (f._weight || 0), 0))
const weightSumAlertClass = computed(() =>
  Math.abs(weightSum.value - weightTarget.value) < 0.01 ? 'weight-ok' : 'weight-alert'
)
const allGroups = computed(() => [...new Set(factors.value.map(f => f.group).filter(Boolean))])
const filteredFactors = computed(() => {
  let list = filterGroup.value ? factors.value.filter(f => f.group === filterGroup.value) : factors.value
  if (showValidOnly.value) {
    list = list.filter(f => effectivenessMap.value[f.name]?.ic !== undefined)
  }
  return list
})

/* ── 因子选股 ── */
const scDaysBack = ref(5)
const scMinScore = ref(0)
const scLimit = ref(100)
const scLoading = ref(false)
const scResult = ref<any>(null)
const scWeightLabel = ref('当前权重')
const scTableRef = ref<any>(null)

/* ── 通用进度弹窗 ── */
const progressVisible = ref(false)
const progressTitle = ref('计算中')
const progressRunning = ref(false)
const progressPct = ref(0)
const progressStep = ref('')
const progressStatus = ref('')
const progressTaskId = ref('')
const progressMode = ref<'score'|'corr'>('score')
const progressStartTime = ref(0)
const elapsedStr = ref('')
const etaStr = ref('')
let progressPollTimer: ReturnType<typeof setInterval> | null = null

/* ── 股票详情抽屉 ── */
const stockDrawerVisible = ref(false)
const stockDrawerData = ref<any>(null)
const stockDrawerTitle = computed(() =>
  stockDrawerData.value ? `${stockDrawerData.value.name} (${stockDrawerData.value.code})` : ''
)
const stockDrawerFactorTable = computed(() => {
  const d = stockDrawerData.value
  if (!d?.factors) return []
  return Object.entries(d.factors).map(([k, v]) => ({ name: k, value: v }))
})
const radarOption = computed(() => {
  const d = stockDrawerData.value
  if (!d?.factors) return {}
  const entries = Object.entries(d.factors) as [string, number][]
  return {
    tooltip: { trigger: 'item' as const },
    radar: {
      indicator: entries.map(([k]) => ({ name: k, max: 3, min: -3 })),
      center: ['50%', '55%'],
      radius: '65%',
      axisName: { color: '#c0c4cc', fontSize: 12 },
      splitArea: { areaStyle: { color: ['rgba(64,158,255,0.02)', 'rgba(64,158,255,0.05)'] } },
      axisLine: { lineStyle: { color: '#333' } },
      splitLine: { lineStyle: { color: '#2c2c2c' } },
    },
    series: [{
      type: 'radar',
      data: [{ value: entries.map(([, v]) => v), name: d.name || d.code }],
      areaStyle: { color: 'rgba(64,158,255,0.25)' },
      lineStyle: { color: '#409EFF', width: 2 },
      itemStyle: { color: '#409EFF' },
    }],
  }
})

/* ── IC回测 ── */
const btDaysAgo = ref(40)
const btPeriods = ref([5, 10, 20])
const btRunning = ref(false)
const btProgress = ref(0)
const btStatus = ref('')
const btStep = ref('')
const btTaskId = ref('')
const btHistory = ref<any[]>([])
const btActiveHistory = ref<string[]>([])
const showBtTrend = ref(false)
const expandedChart = ref<string | null>(null)
const btDetailDrawerVisible = ref(false)
const btDetailTitle = ref('')
const btDetailData = ref<any[]>([])
let btPollTimer: ReturnType<typeof setInterval> | null = null

/* ── 因子相关性 ── */
const corrDaysBack = ref(5)
const corrLoading = ref(false)
const corrResult = ref<any>(null)
const corrRunning = ref(false)
const corrFactorScope = ref<string[]>([])

/* ── 因子缓存 ── */
const cacheStatus = ref<any>(null)
const cacheLoading = ref(false)

/* ── 分位数柱状图 ── */
function quintileChartOption(row: any) {
  if (!row) return {}
  const labels = ['Q1高分', 'Q2', 'Q3', 'Q4', 'Q5低分']
  // 发散型色阶: Q1深绿 → Q3灰 → Q5深红
  const divergingColors = ['#1a7d36', '#67c23a', '#909399', '#d98c2e', '#b33a3a']
  const vals = [row.top20_return ?? 0, row.q2 ?? 0, row.q3 ?? 0, row.q4 ?? 0, row.bot20_return ?? 0]
  const maxAbs = Math.max(...vals.map(Math.abs), 0.01)
  return {
    tooltip: { trigger: 'axis' as const, formatter: (p: any) => `${p[0].name}: ${p[0].value.toFixed(2)}%` },
    grid: { left: 48, right: 16, top: 12, bottom: 20 },
    xAxis: { type: 'category' as const, data: labels, axisLabel: { color: '#909399', fontSize: 10 } },
    yAxis: { type: 'value' as const, axisLabel: { color: '#909399', fontSize: 10 }, min: -maxAbs * 1.3, max: maxAbs * 1.3,
             splitLine: { lineStyle: { color: '#2a2a45', type: 'dashed' } } },
    series: [{
      type: 'bar' as const,
      data: vals.map((v, i) => ({ value: v, itemStyle: { color: divergingColors[i], borderRadius: [2, 2, 0, 0] } })),
      barWidth: '55%',
      label: { show: true, position: 'outside', color: '#c0c4cc', fontSize: 11, fontWeight: 'bold',
               formatter: (p: any) => (p.value > 0 ? '+' : '') + p.value.toFixed(2) + '%' },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { color: '#606880', width: 2, type: 'dashed' },
        data: [{ yAxis: 0, label: { show: false } }],
      },
    }],
  }
}

/* ── 单因子 IC 横向柱状图 ── */
const PERIOD_COLORS: Record<string, string> = { '5d': '#4fc3f7', '10d': '#ffa726', '20d': '#ef5350', '40d': '#ab47bc' }
const PERIOD_NAMES: Record<string, string> = { '5d': '5日', '10d': '10日', '20d': '20日', '40d': '40日' }

function factorICChartOption(factorTable: any[]) {
  if (!factorTable || !factorTable.length) return {}
  const names = factorTable.map(f => f.name)
  const periods = Object.keys(factorTable[0]).filter(k => k.endsWith('d'))
  const series = periods.map(p => ({
    name: PERIOD_NAMES[p] || p,
    type: 'bar' as const,
    data: factorTable.map(f => {
      const v = f[p] ?? 0
      return {
        value: v,
        itemStyle: {
          color: v > 0 ? PERIOD_COLORS[p] || '#67c23a' : '#f56c6c',
          borderRadius: v > 0 ? [0, 2, 2, 0] : [2, 0, 0, 2],
        },
      }
    }),
    barWidth: 10,
    barGap: '20%',
  }))
  return {
    tooltip: { trigger: 'axis' as const,
      formatter: (params: any[]) => {
        const name = params[0]?.name || ''
        let html = `<b>${name}</b><br/>`
        params.forEach(p => {
          const v = p.value as number
          const color = v > 0 ? '#67c23a' : '#f56c6c'
          html += `<span style="color:${p.color};margin-right:4px">●</span>${p.seriesName}: <span style="color:${color};font-weight:700">${v.toFixed(4)}</span><br/>`
        })
        return html
      },
    },
    legend: { textStyle: { color: '#c0c4cc', fontSize: 11 }, top: 0, right: 0, icon: 'roundRect' },
    grid: { left: 100, right: 48, top: 28, bottom: 8 },
    xAxis: { type: 'value' as const, axisLabel: { color: '#909399', fontSize: 10 },
             splitLine: { lineStyle: { color: '#2a2a45', type: 'dashed' } } },
    yAxis: { type: 'category' as const, data: names, axisLabel: { color: '#c0c4cc', fontSize: 10 } },
    series,
  }
}

/* ── IC 趋势图 ── */
const btTrendOption = computed(() => {
  const hist = btHistory.value
  if (hist.length < 2) return {}
  const dates = hist.map(h => h.test_date)
  const periods = Object.keys(hist[0].composite)
  const series = periods.map(p => ({
    name: p + 'd',
    type: 'line' as const,
    data: hist.map(h => h.composite[p]?.ic ?? null),
    smooth: true,
  }))
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { textStyle: { color: '#c0c4cc' } },
    xAxis: { type: 'category' as const, data: dates, axisLabel: { color: '#909399' } },
    yAxis: { type: 'value' as const, axisLabel: { color: '#909399' } },
    grid: { left: 48, right: 16, top: 40, bottom: 28 },
    series,
  }
})

/* ── 热力图 ── */
const heatmapLegend = [
  { label: '强正相关', color: '#f56c6c' },
  { label: '正相关', color: '#e6a23c' },
  { label: '弱相关', color: '#f0f0f0' },
  { label: '负相关', color: '#67c23a' },
  { label: '强负相关', color: '#409eff' },
]

const heatmapOption = computed(() => {
  const r = corrResult.value
  if (!r) return {}
  const factors = r.factors
  const matrix = r.matrix
  const data: { value: number[] }[] = []
  for (let i = 0; i < factors.length; i++) {
    for (let j = 0; j < factors.length; j++) {
      if (matrix[i][j] !== null) {
        data.push({ value: [j, i, Math.abs(matrix[i][j] || 0)] })
      }
    }
  }
  return {
    tooltip: {
      formatter: (p: any) => {
        const [x, y] = p.data.value
        return `${factors[y]} ↔ ${factors[x]}: ${(matrix[y][x] || 0).toFixed(4)}`
      },
    },
    xAxis: {
      type: 'category' as const, data: factors,
      splitArea: { show: true },
      axisLabel: { rotate: 45, color: '#c0c4cc', fontSize: 11 },
      axisLine: { show: false },
    },
    yAxis: {
      type: 'category' as const, data: factors,
      splitArea: { show: true },
      axisLabel: { color: '#c0c4cc', fontSize: 11 },
      axisLine: { show: false },
    },
    visualMap: {
      min: 0, max: 1, calculable: true, orient: 'vertical', right: 0, top: 40, bottom: 40,
      inRange: { color: ['#409eff', '#67c23a', '#f0f0f0', '#e6a23c', '#f56c6c'] },
      textStyle: { color: '#909399' },
    },
    series: [{
      type: 'heatmap' as const, data,
      label: {
        show: factors.length <= 20, color: '#c0c4cc', fontSize: 10,
        formatter: (p: any) => (matrix[p.data.value[1]]?.[p.data.value[0]] || 0).toFixed(2),
      },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' } },
    }],
    grid: { left: 100, right: 60, top: 16, bottom: 80 },
  }
})

/* ── 因子管理 ── */
async function fetchFactors() {
  try {
    const { data } = await factorApi.list()
    factors.value = (data.data || []).map((f: any) => ({ ...f, _weight: f.weight }))
    await Promise.all([computeDistributions(), fetchEffectiveness()])
  } catch { ElMessage.error('获取因子列表失败') }
}

async function fetchEffectiveness() {
  try {
    const { data } = await factorApi.effectiveness({ days_back: 5 })
    effectivenessMap.value = data.data || {}
  } catch { /* silent */ }
}

async function applyWeightPreset(mode: string) {
  if (!mode) return
  weightPresetMode.value = mode
  if (mode === 'group-equal') {
    applyGroupEqualWeight()
    return
  }
  try {
    const { data } = await factorApi.weightPresets({ days_back: 5 })
    const preset = mode === 'ic' ? data.data.ic_weighted : data.data.icir_weighted
    if (!preset || !Object.keys(preset).length) {
      ElMessage.warning('暂无数据，请先运行IC测试')
      weightPresetMode.value = ''
      return
    }
    const maxVal = Math.max(...Object.values(preset) as number[], 0.01)
    const scale = 5 / maxVal
    for (const f of factors.value) {
      f._weight = Math.round((preset[f.name] || 0) * scale * 10) / 10
    }
    ElMessage.success(`已应用${mode === 'ic' ? 'IC均值' : 'IR（信息比率）'}加权权重`)
  } catch {
    ElMessage.error('获取权重预设失败')
    weightPresetMode.value = ''
  }
}

function applyGroupEqualWeight() {
  const groups: Record<string, any[]> = {}
  for (const f of factors.value) {
    if (!groups[f.group]) groups[f.group] = []
    groups[f.group].push(f)
  }
  const groupNames = Object.keys(groups)
  const groupWeight = 5 / groupNames.length
  for (const g of groupNames) {
    const members = groups[g]
    const memberWeight = groupWeight / members.length
    for (const f of members) {
      f._weight = Math.round(memberWeight * 10) / 10
    }
  }
  ElMessage.success(`已应用分组等权 (${groupNames.length}组)`)
}

function toggleDensity() {
  compactView.value = !compactView.value
}

/* ── 防抖自动保存 ── */
let saveTimer: ReturnType<typeof setTimeout> | null = null

function onWeightChange() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    debouncedSave()
  }, 1500)
}

async function debouncedSave() {
  if (saveTimer) { clearTimeout(saveTimer); saveTimer = null }
  saving.value = true
  try {
    await factorApi.updateWeights(getCurrentWeights())
    ElMessage.success('权重已自动保存')
    await fetchFactors()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function computeDistributions() {
  try {
    const { data } = await factorApi.score({ days_back: 5, limit: 500, min_score: -999 })
    const rows = data.data.rows
    if (!rows || rows.length === 0) return
    const dist: Record<string, any> = {}
    const factorNames = Object.keys(rows[0].factors || {})
    for (const name of factorNames) {
      const vals = rows.map((r: any) => r.factors[name]).filter((v: any) => v !== undefined && v !== null) as number[]
      if (vals.length === 0) continue
      const sorted = [...vals].sort((a, b) => a - b)
      const mean = vals.reduce((s, v) => s + v, 0) / vals.length
      const variance = vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length
      dist[name] = {
        count: vals.length,
        mean, std: Math.sqrt(variance),
        median: sorted.length % 2 === 0
          ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
          : sorted[Math.floor(sorted.length / 2)],
        min: sorted[0], max: sorted[sorted.length - 1],
      }
    }
    factorDistMap.value = dist
  } catch { /* silent */ }
}

function getCurrentWeights(): Record<string, number> {
  const w: Record<string, number> = {}
  factors.value.forEach(f => { w[f.name] = f._weight })
  return w
}

async function previewWeights() {
  previewLoading.value = true
  previewVisible.value = true
  previewResult.value = null
  try {
    const { data } = await factorApi.score({
      days_back: scDaysBack.value,
      limit: 100,
      min_score: 0,
      weights: getCurrentWeights(),
    })
    previewResult.value = data.data
  } catch (e: any) {
    ElMessage.error('预览失败: ' + (e.message || ''))
  } finally { previewLoading.value = false }
}

async function saveWeights() {
  if (saveTimer) { clearTimeout(saveTimer); saveTimer = null }
  await debouncedSave()
}

async function resetWeights() {
  try {
    await factorApi.resetWeights()
    ElMessage.success('已恢复默认权重')
    await fetchFactors()
  } catch { ElMessage.error('重置失败') }
}

/* ── 通用进度 ── */
function stopProgressPoll() {
  if (progressPollTimer) { clearInterval(progressPollTimer); progressPollTimer = null }
}

function startProgressPoll() {
  stopProgressPoll()
  progressStartTime.value = Date.now()
  elapsedStr.value = '0s'
  etaStr.value = '...'
  progressPollTimer = setInterval(pollProgressGeneric, 800)
}

function fmtDuration(ms: number): string {
  if (ms < 60000) return Math.round(ms / 1000) + 's'
  const m = Math.floor(ms / 60000)
  const s = Math.round((ms % 60000) / 1000)
  return `${m}m${s}s`
}

async function pollProgressGeneric() {
  if (!progressTaskId.value) return
  try {
    const api = progressMode.value === 'score' ? factorApi.scoreProgress : factorApi.correlationProgress
    const { data } = await api(progressTaskId.value)
    const d = data.data
    progressPct.value = d.progress; progressStep.value = d.step; progressStatus.value = d.status

    // ETA
    const elapsed = Date.now() - progressStartTime.value
    elapsedStr.value = fmtDuration(elapsed)
    if (d.progress > 0 && d.progress < 100) {
      const estTotal = elapsed / (d.progress / 100)
      const remaining = estTotal - elapsed
      etaStr.value = remaining > 0 ? fmtDuration(remaining) : '< 1s'
    }

    if (d.status === 'completed') {
      stopProgressPoll(); progressRunning.value = false; corrRunning.value = false
      if (progressMode.value === 'score') {
        scResult.value = d.result
        scWeightLabel.value = '当前权重'
        ElMessage.success(`评分完成，共 ${d.result?.total || 0} 只股票`)
      } else {
        corrResult.value = d.result
        ElMessage.success(`相关性计算完成，基于 ${d.result?.n_stocks || 0} 只股票`)
      }
    } else if (d.status === 'cancelled') {
      stopProgressPoll(); progressRunning.value = false; corrRunning.value = false
      ElMessage.info('已取消')
    } else if (d.status === 'failed') {
      stopProgressPoll(); progressRunning.value = false; corrRunning.value = false
      ElMessage.error('计算失败: ' + d.step)
    }
  } catch (e: any) {
    stopProgressPoll(); progressRunning.value = false; corrRunning.value = false
    progressStatus.value = 'failed'
    progressStep.value = e?.message || '连接失败，请检查后端服务'
    // Show error notification instead of just inline text
    ElMessage({ type: 'error', message: '计算请求异常: ' + (e?.message || '网络错误'), duration: 6000 })
  }
}

async function computeScoresAsync() {
  stopProgressPoll()
  progressMode.value = 'score'
  progressTitle.value = '因子评分进度'
  progressRunning.value = true
  progressVisible.value = true
  progressPct.value = 0; progressStatus.value = 'running'; progressStep.value = '启动中...'
  try {
    const { data } = await factorApi.scoreStart({
      days_back: scDaysBack.value,
      limit: scLimit.value,
      min_score: scMinScore.value,
    })
    progressTaskId.value = data.data.task_id
    startProgressPoll()
  } catch (e: any) {
    progressRunning.value = false; progressStatus.value = 'failed'
    progressStep.value = e.message || '启动失败'
    ElMessage.error('启动失败: ' + (e.message || ''))
  }
}

async function cancelScore() {
  if (progressTaskId.value) {
    try { await factorApi.scoreCancel(progressTaskId.value); ElMessage.info('正在取消...') }
    catch { /* ignore */ }
  }
}

async function computeCorrelationAsync() {
  stopProgressPoll()
  progressMode.value = 'corr'
  progressTitle.value = '相关性计算进度'
  corrRunning.value = true
  progressRunning.value = true
  progressVisible.value = true
  progressPct.value = 0; progressStatus.value = 'running'; progressStep.value = '启动中...'
  try {
    const params: any = { days_back: corrDaysBack.value }
    if (corrFactorScope.value.length > 0) {
      params.factors = corrFactorScope.value
    }
    const { data } = await factorApi.correlationStart(params)
    progressTaskId.value = data.data.task_id
    startProgressPoll()
  } catch (e: any) {
    progressRunning.value = false; corrRunning.value = false; progressStatus.value = 'failed'
    progressStep.value = e.message || '启动失败'
    ElMessage.error('启动失败: ' + (e.message || ''))
  }
}

async function cancelCorrelation() {
  if (progressTaskId.value) {
    try { await factorApi.correlationCancel(progressTaskId.value); ElMessage.info('正在取消...') }
    catch { /* ignore */ }
  }
}

// Keep the old synchronous computeScores for preview etc
async function computeScores() {
  scLoading.value = true
  try {
    const { data } = await factorApi.score({
      days_back: scDaysBack.value,
      limit: scLimit.value,
      min_score: scMinScore.value,
    })
    scResult.value = data.data
    scWeightLabel.value = '当前权重'
    activeTab.value = 'stock-picker'
  } catch (e: any) {
    ElMessage.error('计算失败: ' + (e.message || ''))
  } finally { scLoading.value = false }
}

function exportCSV() {
  if (!scResult.value?.rows?.length) return
  const rows = scResult.value.rows
  const factorNames = Object.keys(rows[0].factors || {})
  const header = ['排名', '代码', '名称', '行业', '综合分', ...factorNames]
  const csvRows = [header.join(',')]
  rows.forEach((r: any, i: number) => {
    const line = [i + 1, r.code, r.name, r.industry, r.score, ...factorNames.map(k => r.factors?.[k] ?? '')]
    csvRows.push(line.map(v => `"${v}"`).join(','))
  })
  const blob = new Blob(['\uFEFF' + csvRows.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `factor_stocks_${scResult.value.trade_date}.csv`
  a.click(); URL.revokeObjectURL(url)
}

function openStockDrawer(row: any) {
  stockDrawerData.value = row
  stockDrawerVisible.value = true
}

/* ── IC回测 ── */
function stopBtPoll() {
  if (btPollTimer) { clearInterval(btPollTimer); btPollTimer = null }
}

async function runICTest() {
  stopBtPoll()
  btRunning.value = true
  btProgress.value = 0; btStatus.value = 'running'; btStep.value = '启动中...'
  try {
    const { data } = await factorApi.icTestStart(btDaysAgo.value, btPeriods.value)
    btTaskId.value = data.data.task_id
    btPollTimer = setInterval(pollProgress, 800)
  } catch (e: any) {
    btRunning.value = false
    ElMessage.error('启动失败: ' + (e.message || ''))
  }
}

function pushBtResult(result: any) {
  if (!result) return
  const composite = result.composite || {}
  const entries = Object.entries(composite) as [string, any][]
  const best = entries.reduce((a, b) => (Math.abs(b[1].ic) > Math.abs(a[1].ic) ? b : a), entries[0])
  const bestICVal = best ? best[1].ic : 0
  const bestIC = best ? `${best[1].ic.toFixed(4)} (${best[0]}d)` : '-'
  const bestSpread = best ? `${best[1].spread > 0 ? '+' : ''}${best[1].spread.toFixed(2)} (${best[0]}d)` : '-'
  const entry = {
    id: Date.now().toString(),
    test_date: result.test_date,
    n_stocks: result.n_stocks,
    n_with_forward: result.n_with_forward,
    composite, factors: result.factors || {},
    bestIC, bestSpread, bestICVal,
    compositeTable: entries.map(([k, v]: any) => ({
      period: k + 'd', ...v,
      q2: v.quintiles?.q2 ?? '-',
      q3: v.quintiles?.q3 ?? '-',
      q4: v.quintiles?.q4 ?? '-',
    })),
    factorTable: Object.entries(result.factors || {}).map(([name, ics]: any) => ({
      name,
      ...Object.fromEntries(Object.entries(ics).map(([k, v]) => [k + 'd', v])),
    })),
  }
  btHistory.value.unshift(entry)
  localStorage.setItem(LS_KEY, JSON.stringify(btHistory.value.slice(0, 20)))
}

function removeBtHistory(id: string) {
  btHistory.value = btHistory.value.filter(h => h.id !== id)
  localStorage.setItem(LS_KEY, JSON.stringify(btHistory.value.slice(0, 20)))
}

async function pollProgress() {
  if (!btTaskId.value) return
  try {
    const { data } = await factorApi.icTestProgress(btTaskId.value)
    const d = data.data
    btProgress.value = d.progress; btStep.value = d.step; btStatus.value = d.status
    if (d.status === 'completed') {
      stopBtPoll(); btRunning.value = false
      pushBtResult(d.result); btProgress.value = 100; btStep.value = 'IC测试完成'
      ElMessage.success('IC测试完成')
    } else if (d.status === 'cancelled') {
      stopBtPoll(); btRunning.value = false; ElMessage.info('IC测试已取消')
    } else if (d.status === 'failed') {
      stopBtPoll(); btRunning.value = false; ElMessage.error('IC测试失败: ' + d.step)
    }
  } catch {
    stopBtPoll(); btRunning.value = false; ElMessage.error('获取进度失败')
  }
}

async function cancelICTest() {
  if (btTaskId.value) {
    try { await factorApi.icTestCancel(btTaskId.value); ElMessage.info('正在取消...') }
    catch { /* ignore */ }
  }
}

function clearBtHistory() {
  btHistory.value = []
  localStorage.removeItem(LS_KEY)
}

/* ── 趋势箭头 ── */
function getPrevEntry(h: any): any {
  const idx = btHistory.value.indexOf(h)
  return idx < btHistory.value.length - 1 ? btHistory.value[idx + 1] : null
}

function getPrevMetric(h: any, ri: string | number, key: string): number {
  const prev = getPrevEntry(h)
  if (!prev?.compositeTable?.[ri]) return 0
  return prev.compositeTable[ri][key] ?? 0
}

function getTrendArrow(h: any, ri: string | number, key: string): string {
  const cur = h.compositeTable[ri]?.[key] ?? 0
  const prev = getPrevMetric(h, ri, key)
  if (prev === 0) return ''
  return cur >= prev ? '↑' : '↓'
}

function getTrendClass(h: any, ri: string | number, key: string): string {
  const cur = h.compositeTable[ri]?.[key] ?? 0
  const prev = getPrevMetric(h, ri, key)
  if (prev === 0) return ''
  return cur >= prev ? 'trend-up' : 'trend-down'
}

/* ── 图表展开 ── */
function toggleExpandChart(id: string) {
  expandedChart.value = expandedChart.value === id ? null : id
}

/* ── 图表点击下钻 ── */
function onChartClick(type: string, h: any, event: any) {
  if (type === 'factorIC') {
    const name = event?.name || ''
    const factorData = h.factorTable?.find((f: any) => f.name === name)
    if (factorData) {
      btDetailTitle.value = `${name} — IC时间序列`
      btDetailData.value = Object.entries(factorData)
        .filter(([k]) => k !== 'name')
        .map(([k, v]) => ({ period: k, value: (v as number)?.toFixed(4) ?? '-' }))
      btDetailDrawerVisible.value = true
    }
  } else if (type === 'quintile') {
    const quintileMap: Record<string, string> = { 'Q1高分': 'top20_return', 'Q2': 'q2', 'Q3': 'q3', 'Q4': 'q4', 'Q5低分': 'bot20_return' }
    const qKey = quintileMap[event?.name || '']
    if (qKey && h.compositeTable[0]?.[qKey] !== undefined) {
      btDetailTitle.value = `${event.name} — 收益: ${(h.compositeTable[0][qKey] || 0).toFixed(2)}%`
      btDetailData.value = h.compositeTable.map((row: any) => ({
        period: row.period,
        value: row[qKey] != null ? Number(row[qKey]).toFixed(2) + '%' : '-',
      }))
      btDetailDrawerVisible.value = true
    }
  }
}

/* ── 因子相关性 ── */
async function computeCorrelation() {
  corrLoading.value = true
  try {
    const { data } = await factorApi.correlation({ days_back: corrDaysBack.value })
    corrResult.value = data.data
    activeTab.value = 'correlation'
  } catch (e: any) { ElMessage.error('计算失败: ' + (e.message || '')) }
  finally { corrLoading.value = false }
}

/* ── 因子缓存 ── */
async function fetchCacheStatus() {
  try {
    const { data } = await factorApi.cacheStatus()
    cacheStatus.value = data.data
  } catch { /* ignore */ }
}

async function triggerCacheUpdate() {
  cacheLoading.value = true
  try {
    await factorApi.triggerCacheUpdate()
    ElMessage.success('缓存更新已异步启动')
  } catch { ElMessage.error('触发失败') }
  finally { cacheLoading.value = false }
}

/* ── 初始化 ── */
onMounted(() => {
  fetchFactors()
  fetchCacheStatus()
  try {
    const saved = localStorage.getItem(LS_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed) && parsed.length) {
        btHistory.value = parsed
        btActiveHistory.value = [parsed[0].id]
      }
    }
  } catch { /* ignore */ }
})

onUnmounted(() => {
  if (saveTimer) clearTimeout(saveTimer)
})
</script>

<style scoped>
.factor-lab { padding: 8px; }
.section-toolbar { margin-bottom: 12px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

/* ── IC回测 进度 ── */
.bt-progress {
  background: linear-gradient(135deg, var(--bg-card-alt) 0%, var(--bg-deep-soft) 100%);
  border: 1px solid var(--border-alt);
  border-radius: 10px;
  padding: 24px;
  margin-bottom: 16px;
}
.bt-progress-step {
  color: var(--text-alt-secondary);
  font-size: 13px;
  text-align: center;
  margin-top: 10px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* ── IC回测 指标卡片 ── */
.bt-metrics {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.bt-metric-card {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-radius: 8px;
  padding: 10px 14px;
  flex: 1;
  min-width: 130px;
}
.bt-metric-title {
  font-size: 11px;
  color: var(--text-alt-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
  font-weight: 600;
}
.bt-metric-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
  font-size: 12px;
}
.bt-metric-label {
  color: var(--text-alt-muted);
}
.bt-metric-val {
  font-weight: 700;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px;
}
.bt-metric-val.green { color: #67c23a; }
.bt-metric-val.red { color: #f56c6c; }

/* ── IC回测 图表行 ── */
.bt-chart-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.bt-chart-box {
  flex: 1;
  min-width: 300px;
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-radius: 8px;
  padding: 10px 12px 6px;
  transition: all 0.3s ease;
}
.bt-chart-box.bt-chart-expanded {
  flex: 2;
  min-width: 90%;
}
.bt-chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.bt-chart-title {
  font-size: 12px;
  color: var(--text-alt-secondary);
  font-weight: 600;
}
.bt-expand-btn {
  color: var(--text-alt-muted) !important;
  font-size: 14px !important;
  padding: 0 4px !important;
  min-height: 20px !important;
}
.bt-expand-btn:hover {
  color: var(--text-secondary) !important;
}

/* ── 趋势箭头 ── */
.trend-arrow {
  display: inline-block;
  font-size: 10px;
  margin-left: 2px;
  font-weight: 700;
}
.trend-up { color: #67c23a; }
.trend-down { color: #f56c6c; }

/* ── 数值等宽字体 ── */
.bt-metric-val {
  font-variant-numeric: tabular-nums;
}

/* ── IC回测 趋势 ── */
.bt-trend-section {
  margin-top: 8px;
}
.bt-trend-toggle {
  color: var(--text-alt-secondary) !important;
}
.bt-trend-chart {
  height: 260px;
  margin-top: 8px;
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-radius: 8px;
  padding: 8px;
}

/* ── 因子选股 ── */
.factor-bars { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.factor-bar-item { display: flex; align-items: center; gap: 4px; width: calc(50% - 6px); }
.fb-label { font-size: 11px; color: var(--text-alt-secondary); min-width: 60px; white-space: nowrap; }
.factor-bar-item .el-progress { flex: 1; }

/* ── 评分进度弹窗 ── */
.sc-progress-box {
  background: linear-gradient(135deg, var(--bg-card-alt) 0%, var(--bg-deep-soft) 100%);
  border: 1px solid var(--border-alt);
  border-radius: 10px;
  padding: 28px 20px;
}
.sc-progress-step {
  margin-bottom: 16px; text-align: center;
  color: var(--text-alt-secondary); font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  min-height: 20px;
}
.sc-progress-bar-wrap {
  padding: 0 4px;
}
.sc-progress-bar-wrap .el-progress {
  /* Make track darker for contrast */
  --el-progress-track-color: var(--bg-deep);
}
.sc-progress-bar-wrap .el-progress-bar__outer {
  background-color: var(--bg-deep) !important;
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.5);
}
.sc-progress-bar-wrap .el-progress-bar__inner {
  box-shadow: 0 0 8px rgba(64,158,255,0.4);
  transition: width 0.4s ease, box-shadow 0.4s ease;
}
.sc-progress-eta {
  text-align: center; color: var(--text-alt-muted); font-size: 11px;
  margin-top: 8px; font-family: 'SF Mono', 'Fira Code', monospace;
}
.sc-progress-hint {
  text-align: center; color: var(--text-alt-muted); font-size: 11px;
  margin-top: 14px; font-style: italic;
}

/* ── 相关性 ── */
.heatmap-wrapper { background: var(--bg-card-alt); border: 1px solid var(--border-alt); border-radius: 6px; padding: 8px; }
.corr-legend { display: flex; gap: 16px; margin-top: 8px; justify-content: center; flex-wrap: wrap; }
.corr-legend-item { font-size: 12px; color: var(--text-alt-secondary); display: flex; align-items: center; }

/* ── 使用说明 ── */
.help-card { line-height: 1.8; font-size: 14px; }
.help-card h3 { color: var(--text-primary); }
.help-card h4 { color: var(--text-secondary); margin: 16px 0 8px; font-size: 15px; }
.help-card h5 { color: var(--text-alt-secondary); margin: 12px 0 6px; font-size: 14px; }
.help-card p { color: var(--text-muted); }
.help-card ul { padding-left: 20px; }
.help-card li { color: var(--text-muted); margin: 4px 0; }
.help-card li b { color: var(--text-secondary); }
.help-card code {
  background: var(--bg-card-alt); color: var(--code-text); padding: 1px 6px;
  border-radius: 3px; font-size: 13px;
}
.help-code {
  background: #0d1117; color: #e0e0e0; padding: 16px; border-radius: 6px;
  font-size: 13px; border: 1px solid var(--border-alt); overflow-x: auto;
  line-height: 1.6; font-family: 'SF Mono', 'Fira Code', monospace;
}

/* ── 方向徽章 ── */
.direction-badge {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 700; line-height: 1.4;
}
.direction-normal {
  background: rgba(103,194,58,0.18); color: #67c23a; border: 1px solid rgba(103,194,58,0.35);
}
.direction-inverse {
  background: rgba(245,108,108,0.18); color: #f56c6c; border: 1px solid rgba(245,108,108,0.35);
}
.dir-arrow { font-size: 14px; }
.dir-label { font-size: 10px; opacity: 0.8; }

/* ── 权重总和告警 ── */
.weight-sum-label {
  color: var(--text-muted); font-size: 12px; margin-right: 8px;
}
.weight-ok {
  color: #67c23a; font-size: 14px;
  transition: color 0.3s ease;
}
.weight-alert {
  color: #f56c6c; font-size: 14px;
  animation: weightPulse 1.2s ease-in-out infinite;
}
@keyframes weightPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ── 有效性单元格 ── */
.validity-cell {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px;
}
.validity-status-tag { flex-shrink: 0; padding: 0 4px !important; height: 18px !important; line-height: 18px !important; }
.validity-ic { font-weight: 600; }
.ic-positive { color: #67c23a; }
.ic-negative { color: #f56c6c; }
.validity-sep { color: var(--text-alt-muted); margin: 0 2px; font-size: 10px; }
.validity-ir { font-weight: 500; }
.ir-good { color: #67c23a; }
.ir-weak { color: var(--text-muted); }
.validity-na { color: var(--text-alt-muted); font-size: 11px; }

/* ── 紧凑表格 ── */
.compact-table { --factor-row-height: 32px; }
.compact-table .el-table__row > td { padding-top: 2px !important; padding-bottom: 2px !important; }
.compact-table .el-slider__runway { height: 4px; }
.compact-table .el-slider__button { width: 12px; height: 12px; }
.compact-table .el-tag { padding: 0 4px; font-size: 10px; height: 18px; line-height: 18px; }

/* ── 斑马纹与行高亮增强 ── */
.factor-lab .el-table__body tr.el-table__row--striped td {
  background: var(--bg-hover-subtle);
}
.factor-lab .el-table__body tr.el-table__row--striped:hover td {
  background: rgba(64,158,255,0.06);
}
.factor-lab .el-table__body tr:hover td {
  background: rgba(64,158,255,0.05);
}
.factor-lab .el-table__body tr.current-row > td {
  background: rgba(64,158,255,0.08) !important;
  box-shadow: inset 3px 0 0 #409eff;
}
.factor-row { transition: background 0.15s ease; }
</style>
