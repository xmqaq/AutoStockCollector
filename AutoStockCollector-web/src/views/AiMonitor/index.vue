<template>
  <div class="ai-monitor">
    <!-- Header -->
    <div class="monitor-header">
      <div class="header-left">
        <h2>AI 实时监控</h2>
        <span class="header-sub">主力资金 · 研报分析 · 长短线建议</span>
      </div>
      <div class="header-right">
        <el-tag v-if="lastRefresh" type="info" effect="plain" class="refresh-tag">
          上次刷新: {{ lastRefresh }}
        </el-tag>
        <el-button type="primary" :loading="refreshing" @click="handleRefresh" size="small">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" class="main-tabs">
      <el-tab-pane label="综合信号" name="signal" />
      <el-tab-pane label="新闻舆情" name="news_sentiment">
        <template #label>
          <span>新闻舆情 <el-tag v-if="sentimentBullishCount" size="small" type="danger" effect="light" class="sentiment-count">{{ sentimentBullishCount }}利好</el-tag></span>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- Signal View -->
    <template v-if="activeTab === 'signal'">
    <!-- Filter -->
    <div class="filter-bar">
      <el-input
        v-model="searchText"
        placeholder="搜索代码/名称"
        clearable
        size="small"
        class="search-input"
        @input="() => {}"
      />
      <el-select v-model="signalFilter" placeholder="信号筛选" size="small" clearable class="filter-select" @change="() => {}">
        <el-option label="全部" value="" />
        <el-option label="短期买入" value="short_buy" />
        <el-option label="短期卖出" value="short_sell" />
        <el-option label="长期买入" value="long_buy" />
        <el-option label="长期卖出" value="long_sell" />
      </el-select>
      <el-select v-model="typeFilter" placeholder="来源" size="small" clearable class="filter-select" @change="() => {}">
        <el-option label="全部" value="" />
        <el-option label="持仓" value="持仓" />
        <el-option label="自选" value="自选" />
      </el-select>
    </div>

    <!-- Stats -->
    <div class="stats-bar">
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">持仓监控</div>
        <div class="stat-value">{{ positionCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">自选监控</div>
        <div class="stat-value">{{ watchlistCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">短期买入</div>
        <div class="stat-value text-success">{{ shortBuyCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">长期买入</div>
        <div class="stat-value text-success">{{ longBuyCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">短期卖出</div>
        <div class="stat-value text-danger">{{ shortSellCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">长期卖出</div>
        <div class="stat-value text-danger">{{ longSellCount }}</div>
      </el-card>
    </div>

    <!-- Signal Grid -->
    <div class="signal-grid" v-loading="loading">
      <el-row :gutter="12">
        <el-col v-for="s in filteredSignals" :key="s.code" :xs="24" :sm="12" :lg="8" :xl="6">
          <el-card shadow="hover" class="signal-card" @click="showDetail(s)">
            <!-- Card Header -->
            <div class="card-header">
              <div class="card-title">
                <span class="stock-code">{{ s.code }}</span>
                <span class="stock-name">{{ s.name }}</span>
              </div>
              <el-tag :type="s.type === '持仓' ? 'warning' : 'info'" size="small" effect="plain">
                {{ s.type }}
              </el-tag>
            </div>

            <!-- Price -->
            <div class="card-price">
              <span class="price-val">{{ fmtPrice(s.price) }}</span>
              <span :class="['change', s.change_rate >= 0 ? 'up' : 'down']">
                {{ fmtChange(s.change_rate) }}
              </span>
            </div>

            <!-- Composite Badge -->
            <div class="composite-row">
              <el-tag :type="signalTagType(s.composite.signal)" size="small" effect="dark">
                {{ s.composite.label }}
              </el-tag>
              <span class="confidence">{{ (s.confidence * 100).toFixed(0) }}% 置信</span>
              <span class="profit-badge">{{ profitScore(s).toFixed(0) }}</span>
              <el-tag v-if="s.analysis.news_sentiment?.overall?.bullish" size="small" type="danger" effect="light" class="ns-card-badge">利好</el-tag>
              <el-tag v-else-if="s.analysis.news_sentiment?.overall?.signal === 'bearish'" size="small" type="success" effect="light" class="ns-card-badge">利空</el-tag>
            </div>

            <!-- Dual signal bars -->
            <div class="signal-bars">
              <div class="signal-bar-row">
                <span class="bar-label">短期</span>
                <el-progress
                  :percentage="s.short_term.score"
                  :color="scoreColor(s.short_term.score)"
                  :stroke-width="10"
                  :format="() => signalLabel(s.short_term.signal)"
                />
              </div>
              <div class="signal-bar-row">
                <span class="bar-label">长期</span>
                <el-progress
                  :percentage="s.long_term.score"
                  :color="scoreColor(s.long_term.score)"
                  :stroke-width="10"
                  :format="() => signalLabel(s.long_term.signal)"
                />
              </div>
            </div>

            <!-- Reasons preview -->
            <div class="reasons-preview">
              <div v-if="s.short_term.reasons?.length" class="reason-line short-reason">
                <el-icon size="12"><Top /></el-icon> {{ s.short_term.reasons[0] }}
              </div>
              <div v-if="s.long_term.reasons?.length" class="reason-line long-reason">
                <el-icon size="12"><Timer /></el-icon> {{ s.long_term.reasons[0] }}
              </div>
            </div>

            <!-- Price Prediction -->
            <div v-if="s.price_prediction?.target_price" class="pp-row">
              <el-tag :type="adviceTagType(s.trading_advice?.action_signal)" size="small" effect="dark" class="pp-action-tag">
                {{ s.trading_advice?.action || '--' }}
              </el-tag>
              <span class="pp-row-target">目标 <strong class="up">{{ fmtPrice(s.price_prediction.target_price) }}</strong></span>
              <span class="pp-row-stop">止损 <strong class="down">{{ fmtPrice(s.price_prediction.stop_loss) }}</strong></span>
              <span class="pp-row-return">预期 <strong :class="s.price_prediction.expected_return >= 0 ? 'up' : 'down'">{{ s.price_prediction.expected_return >= 0 ? '+' : '' }}{{ s.price_prediction.expected_return.toFixed(1) }}%</strong></span>
              <span :class="['pp-row-risk', riskLevelClass(s.price_prediction.risk_level)]">{{ s.price_prediction.risk_level }}</span>
            </div>

            <!-- Divergence -->
            <div v-if="s.composite.divergence" class="divergence-tip">
              {{ s.composite.divergence }}
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-if="!loading && filteredSignals.length === 0" description="暂无监控信号" />
    </div>

    </template>
    <!-- end signal view -->

    <!-- News Sentiment View -->
    <template v-if="activeTab === 'news_sentiment'">
      <div class="sentiment-page">
        <!-- Stats -->
        <div class="stats-bar">
          <el-card shadow="never" class="stat-card stat-bullish">
            <div class="stat-label">利好新闻</div>
            <div class="stat-value">{{ newsFeedPositive.length }}</div>
          </el-card>
          <el-card shadow="never" class="stat-card stat-bearish">
            <div class="stat-label">利空新闻</div>
            <div class="stat-value">{{ newsFeedNegative.length }}</div>
          </el-card>
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">涉及股票</div>
            <div class="stat-value">{{ signalsWithNewsCount }}</div>
          </el-card>
        </div>

        <!-- Filter -->
        <div class="filter-bar">
          <el-input
            v-model="newsSearchText"
            placeholder="搜索新闻标题/股票代码"
            clearable
            size="small"
            class="search-input"
          />
        </div>

        <!-- Positive News -->
        <div class="sentiment-group" v-if="filteredPositiveNews.length">
          <h3 class="sg-header sg-bullish">📈 利好新闻 <small>{{ filteredPositiveNews.length }} 条</small></h3>
          <div v-for="n in filteredPositiveNews" :key="n._key" class="news-feed-card card-bullish" @click="showStockDetail(n.code)">
            <div class="nfc-header">
              <span class="nfc-stock" @click.stop="showStockDetail(n.code)">
                <strong>{{ n.code }}</strong>
                <span class="nfc-name">{{ n.name }}</span>
              </span>
              <el-tag size="small" type="danger" effect="dark" class="nfc-tag">利好</el-tag>
            </div>
            <div class="nfc-title">{{ n.title }}</div>
            <div class="nfc-meta">
              <span class="nfc-date">{{ n.date }}</span>
              <span class="nfc-source">{{ n.source }}</span>
              <span class="nfc-kws" v-if="n.keywords?.length">
                <el-tag v-for="kw in n.keywords.slice(0,4)" :key="kw" size="small" type="danger" effect="plain">{{ kw }}</el-tag>
              </span>
            </div>
          </div>
        </div>

        <!-- Negative News -->
        <div class="sentiment-group" v-if="filteredNegativeNews.length">
          <h3 class="sg-header sg-bearish">⚠️ 利空新闻 <small>{{ filteredNegativeNews.length }} 条</small></h3>
          <div v-for="n in filteredNegativeNews" :key="n._key" class="news-feed-card card-bearish" @click="showStockDetail(n.code)">
            <div class="nfc-header">
              <span class="nfc-stock" @click.stop="showStockDetail(n.code)">
                <strong>{{ n.code }}</strong>
                <span class="nfc-name">{{ n.name }}</span>
              </span>
              <el-tag size="small" type="success" effect="dark" class="nfc-tag">利空</el-tag>
            </div>
            <div class="nfc-title">{{ n.title }}</div>
            <div class="nfc-meta">
              <span class="nfc-date">{{ n.date }}</span>
              <span class="nfc-source">{{ n.source }}</span>
              <span class="nfc-kws" v-if="n.keywords?.length">
                <el-tag v-for="kw in n.keywords.slice(0,4)" :key="kw" size="small" type="success" effect="plain">{{ kw }}</el-tag>
              </span>
            </div>
          </div>
        </div>

        <el-empty v-if="filteredPositiveNews.length === 0 && filteredNegativeNews.length === 0" description="暂无舆情新闻数据" />
      </div>
    </template>

    <!-- Detail Dialog -->
    <el-dialog
      v-model="detailVisible"
      :title="detailData?.name || detailData?.code"
      width="800px"
      top="5vh"
      class="detail-dialog"
      destroy-on-close
    >
      <template v-if="detailData">
        <div class="detail-header">
          <span class="dl-code">{{ detailData.code }}</span>
          <el-tag :type="detailData.type === '持仓' ? 'warning' : 'info'" size="small">
            {{ detailData.type }}
          </el-tag>
          <span v-if="detailData.industry" class="dl-industry">{{ detailData.industry }}</span>
        </div>
        <div class="detail-price">
          现价: <strong>{{ fmtPrice(detailData.price) }}</strong>
          <span :class="['change', detailData.change_rate >= 0 ? 'up' : 'down']">
            {{ fmtChange(detailData.change_rate) }}
          </span>
        </div>

        <!-- AI Trading Advice -->
        <el-card v-if="detailData.trading_advice" shadow="never" :class="['dl-advice', 'advice-' + (detailData.trading_advice.action_signal || 'hold')]">
          <div class="advice-header">
            <span class="advice-label">AI 操作建议</span>
            <el-tag :type="adviceTagType(detailData.trading_advice.action_signal)" size="large" effect="dark">
              {{ detailData.trading_advice.action }}
            </el-tag>
          </div>
          <div class="advice-body">
            <!-- 建议摘要 (核心一行) -->
            <div class="advice-summary">{{ detailData.trading_advice.advice?.summary || detailData.trading_advice.reason }}</div>

            <!-- 价格建议行 -->
            <div class="advice-price-row">
              <div class="adv-price-item" v-if="detailData.trading_advice.action_signal === 'buy'">
                <span class="ap-label">建议买入</span>
                <span class="ap-value up">{{ fmtPrice(detailData.trading_advice.advice?.buy_price_low) }} ~ {{ fmtPrice(detailData.trading_advice.advice?.buy_price_high) }}</span>
              </div>
              <div class="adv-price-item">
                <span class="ap-label">目标卖出</span>
                <span class="ap-value up">{{ fmtPrice(detailData.trading_advice.advice?.target_price) }} <small>(+{{ detailData.trading_advice.advice?.expected_return.toFixed(1) }}%)</small></span>
              </div>
              <div class="adv-price-item">
                <span class="ap-label">止损价</span>
                <span class="ap-value down">{{ fmtPrice(detailData.trading_advice.advice?.stop_loss_price) }} <small>(-{{ detailData.trading_advice.advice?.max_loss.toFixed(1) }}%)</small></span>
              </div>
              <div class="adv-price-item" v-if="detailData.trading_advice.advice?.hold_period">
                <span class="ap-label">持有策略</span>
                <span class="ap-value">{{ detailData.trading_advice.advice?.hold_period }}</span>
              </div>
            </div>

            <!-- 持有期 + 置信度 -->
            <div class="advice-tags-row">
              <el-tag v-if="detailData.trading_advice.advice?.time_horizon" size="small" type="info" effect="plain">
                建议持有期: {{ detailData.trading_advice.advice.time_horizon }}
              </el-tag>
              <el-tag v-if="detailData.trading_advice.advice?.confidence_level" size="small" :type="confLevelType(detailData.trading_advice.advice.confidence_level)" effect="dark">
                置信度 {{ detailData.trading_advice.advice.confidence_level }}
              </el-tag>
              <el-tag v-if="detailData.trading_advice.reflection?.summary" size="small" type="warning" effect="plain" class="reflection-tag">
                {{ detailData.trading_advice.reflection.summary }}
              </el-tag>
            </div>

            <!-- 维度分歧警告 -->
            <div v-if="detailData.trading_advice.divergence_warnings?.length" class="advice-divergence">
              <span class="div-icon">⚡</span>
              <span v-for="(w, i) in detailData.trading_advice.divergence_warnings" :key="i" class="div-item">{{ w }}</span>
            </div>
          </div>
          <div class="advice-metrics">
            <div class="adv-metric">
              <span class="adv-m-label">盈亏比</span>
              <span class="adv-m-val">{{ detailData.trading_advice.risk_reward_ratio }}</span>
            </div>
            <div class="adv-metric">
              <span class="adv-m-label">当前相对</span>
              <span class="adv-m-val">{{ detailData.trading_advice.current_position }}</span>
            </div>
            <div class="adv-metric">
              <span class="adv-m-label">距目标</span>
              <span class="adv-m-val">{{ detailData.trading_advice.distance_to_target }}</span>
            </div>
            <div class="adv-metric">
              <span class="adv-m-label">仓位建议</span>
              <span class="adv-m-val">{{ ((detailData.price_prediction?.position_size ?? 0) * 100).toFixed(0) }}%</span>
            </div>
          </div>
          <!-- 多维度评分条 -->
          <div v-if="detailData.trading_advice.details" class="advice-dims">
            <div v-for="(v, k) in detailData.trading_advice.details" :key="k" class="dim-row">
              <span class="dim-label">{{ dimLabel(k) }}</span>
              <div class="dim-bar-bg">
                <div class="dim-bar-fill" :style="{ width: v + '%', background: scoreColor(v) }"></div>
              </div>
              <span class="dim-score" :style="{ color: scoreColor(v) }">{{ v }}</span>
            </div>
          </div>
        </el-card>

        <!-- Signal Comparison -->
        <el-row :gutter="16" class="dl-signals">
          <el-col :span="12">
            <div class="dl-signal-box short-box">
              <div class="dl-signal-header">短期建议</div>
              <div class="dl-signal-value">
                <el-tag :type="signalTagType(detailData.short_term.signal)" size="large" effect="dark">
                  {{ detailData.short_term.signal_label || detailData.short_term.signal }}
                </el-tag>
                <span class="dl-score">{{ detailData.short_term.score }}</span>
              </div>
              <el-progress
                :percentage="detailData.short_term.score"
                :color="scoreColor(detailData.short_term.score)"
                :stroke-width="8"
                :show-text="false"
              />
              <div class="dl-breakdown">
                <div v-for="(v, k) in detailData.short_term.breakdown" :key="k" class="bd-item">
                  <span class="bd-label">{{ k }}</span>
                  <span :style="{ color: scoreColor(v) }">{{ v }}</span>
                </div>
              </div>
              <ul class="dl-reasons">
                <li v-for="(r, i) in detailData.short_term.reasons" :key="i">{{ r }}</li>
              </ul>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="dl-signal-box long-box">
              <div class="dl-signal-header">长期建议</div>
              <div class="dl-signal-value">
                <el-tag :type="signalTagType(detailData.long_term.signal)" size="large" effect="dark">
                  {{ detailData.long_term.signal_label || detailData.long_term.signal }}
                </el-tag>
                <span class="dl-score">{{ detailData.long_term.score }}</span>
              </div>
              <el-progress
                :percentage="detailData.long_term.score"
                :color="scoreColor(detailData.long_term.score)"
                :stroke-width="8"
                :show-text="false"
              />
              <div class="dl-breakdown">
                <div v-for="(v, k) in detailData.long_term.breakdown" :key="k" class="bd-item">
                  <span class="bd-label">{{ k }}</span>
                  <span :style="{ color: scoreColor(v) }">{{ v }}</span>
                </div>
              </div>
              <ul class="dl-reasons">
                <li v-for="(r, i) in detailData.long_term.reasons" :key="i">{{ r }}</li>
              </ul>
            </div>
          </el-col>
        </el-row>

        <!-- Composite + Price Prediction -->
        <el-row :gutter="16" class="dl-summary">
          <el-col :span="14">
            <el-card shadow="never" class="dl-composite">
              <div class="dl-comp-row">
                <span class="comp-label">综合评分</span>
                <span class="comp-score" :style="{ color: scoreColor(detailData.composite.score) }">
                  {{ detailData.composite.score }}
                </span>
                <el-tag :type="signalTagType(detailData.composite.signal)" effect="dark">
                  {{ detailData.composite.label }}
                </el-tag>
                <span class="comp-conf">置信度: {{ (detailData.confidence * 100).toFixed(0) }}%</span>
                <span v-if="detailData.composite.divergence" class="comp-div">
                  {{ detailData.composite.divergence }}
                </span>
              </div>
            </el-card>
          </el-col>
          <el-col :span="10">
            <el-card shadow="never" class="dl-composite" v-if="detailData.price_prediction">
              <div class="pp-summary">
                <div class="pp-sum-item">
                  <span class="pp-sum-label">买入区间</span>
                  <span class="pp-sum-val up">{{ fmtPrice(detailData.price_prediction.buy_zone_low) }} ~ {{ fmtPrice(detailData.price_prediction.buy_zone_high) }}</span>
                </div>
                <div class="pp-sum-item">
                  <span class="pp-sum-label">支撑/阻力</span>
                  <span class="pp-sum-val">{{ fmtPrice(detailData.price_prediction.support) }} / {{ fmtPrice(detailData.price_prediction.resistance) }}</span>
                </div>
                <div class="pp-sum-item">
                  <span class="pp-sum-label">波动率</span>
                  <span class="pp-sum-val">{{ detailData.price_prediction.volatility?.toFixed(1) }}%</span>
                </div>
                <div class="pp-sum-item">
                  <span class="pp-sum-label">风险</span>
                  <span :class="['pp-sum-val pp-risk-tag', riskLevelClass(detailData.price_prediction.risk_level)]">
                    {{ detailData.price_prediction.risk_level }}
                  </span>
                </div>
                <div class="pp-sum-item">
                  <span class="pp-sum-label">仓位建议</span>
                  <span class="pp-sum-val">{{ (detailData.price_prediction.position_size * 100).toFixed(0) }}%</span>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- Analysis Breakdown -->
        <el-tabs class="dl-tabs" v-model="detailTab">
          <el-tab-pane label="资金流向" name="fund_flow">
            <div class="tab-content">
              <div class="tab-sub">
                <h4>短期资金</h4>
                <p>评分: {{ detailData.analysis.fund_flow.short_term.score }} / 信号: {{ detailData.analysis.fund_flow.short_term.signal }}</p>
                <ul><li v-for="r in detailData.analysis.fund_flow.short_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
              <div class="tab-sub">
                <h4>长期资金</h4>
                <p>评分: {{ detailData.analysis.fund_flow.long_term.score }} / 信号: {{ detailData.analysis.fund_flow.long_term.signal }}</p>
                <ul><li v-for="r in detailData.analysis.fund_flow.long_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="研报分析" name="research">
            <div class="tab-content">
              <p>研报数量: {{ detailData.analysis.research.report_count || 0 }}</p>
              <div class="tab-sub">
                <h4>短期研报</h4>
                <p>评分: {{ detailData.analysis.research.short_term.score }} / 近{{ detailData.analysis.research.short_term.recent_count || 0 }}份</p>
                <ul><li v-for="r in detailData.analysis.research.short_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
              <div class="tab-sub">
                <h4>长期研报</h4>
                <p>评分: {{ detailData.analysis.research.long_term.score }} / 共{{ detailData.analysis.research.long_term.total_reports || 0 }}份</p>
                <ul><li v-for="r in detailData.analysis.research.long_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="技术面" name="technical">
            <div class="tab-content">
              <div class="tab-sub">
                <h4>短期技术</h4>
                <p>评分: {{ detailData.analysis.technical.short_term.score }} / 信号: {{ detailData.analysis.technical.short_term.signal }}</p>
                <ul><li v-for="r in detailData.analysis.technical.short_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
              <div class="tab-sub">
                <h4>长期技术</h4>
                <p>评分: {{ detailData.analysis.technical.long_term.score }} / 信号: {{ detailData.analysis.technical.long_term.signal }}</p>
                <ul><li v-for="r in detailData.analysis.technical.long_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="基本面" name="fundamental">
            <div class="tab-content">
              <p>评分: {{ detailData.analysis.fundamental.score }} / 信号: {{ detailData.analysis.fundamental.signal }}</p>
              <ul><li v-for="r in detailData.analysis.fundamental.reasons" :key="r">{{ r }}</li></ul>
              <div v-if="detailData.analysis.fundamental.details" class="detail-grid">
                <div v-for="(v, k) in detailData.analysis.fundamental.details" :key="k" class="detail-item">
                  <span class="di-label">{{ k }}</span>
                  <span class="di-value">{{ v ?? '--' }}</span>
                </div>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="估值面" name="valuation">
            <div class="tab-content" v-if="detailData.analysis.valuation">
              <p>评分: {{ detailData.analysis.valuation.score }} / 信号: {{ detailData.analysis.valuation.signal }}</p>
              <ul><li v-for="r in detailData.analysis.valuation.reasons" :key="r">{{ r }}</li></ul>
              <div v-if="detailData.analysis.valuation.details" class="detail-grid">
                <div v-for="(v, k) in detailData.analysis.valuation.details" :key="k" class="detail-item">
                  <span class="di-label">{{ k }}</span>
                  <span class="di-value">{{ v ?? '--' }}</span>
                </div>
              </div>
            </div>
          </el-tab-pane>

        </el-tabs>
        <!-- Price Prediction Detail (可折叠) -->
        <el-collapse v-if="detailData.price_prediction" class="pp-collapse">
          <el-collapse-item title="价格预测详情 (点击展开)" name="pp-detail">
            <div class="pp-detail-grid">
              <div class="pp-detail-item">
                <span class="pp-dl-label">买入区间</span>
                <span class="pp-dl-val">{{ fmtPrice(detailData.price_prediction.buy_zone_low) }} ~ {{ fmtPrice(detailData.price_prediction.buy_zone_high) }}</span>
              </div>
              <div class="pp-detail-item">
                <span class="pp-dl-label">支撑位</span>
                <span class="pp-dl-val">{{ fmtPrice(detailData.price_prediction.support) }}</span>
              </div>
              <div class="pp-detail-item">
                <span class="pp-dl-label">阻力位</span>
                <span class="pp-dl-val">{{ fmtPrice(detailData.price_prediction.resistance) }}</span>
              </div>
              <div class="pp-detail-item">
                <span class="pp-dl-label">年化波动率</span>
                <span class="pp-dl-val">{{ detailData.price_prediction.volatility.toFixed(1) }}%</span>
              </div>
              <div class="pp-detail-item">
                <span class="pp-dl-label">最大亏损</span>
                <span class="pp-dl-val down">{{ detailData.price_prediction.max_loss.toFixed(1) }}%</span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Refresh, Top, Timer } from '@element-plus/icons-vue'
import { monitorApi, type MonitorSignal } from '@/api/monitor'
import { ElMessage } from 'element-plus'

const signals = ref<MonitorSignal[]>([])
const loading = ref(false)
const refreshing = ref(false)
const lastRefresh = ref('')
const searchText = ref('')
const signalFilter = ref('')
const typeFilter = ref('')
const activeTab = ref('signal')
const detailVisible = ref(false)
const detailData = ref<MonitorSignal | null>(null)
const detailTab = ref('fund_flow')

let refreshTimer: ReturnType<typeof setInterval> | null = null

function profitScore(s: MonitorSignal): number {
  const pp = s.price_prediction
  const adv = s.trading_advice
  if (!pp) return s.composite.score || 50
  const expRet = pp.expected_return || 0
  const rr = adv?.risk_reward_ratio || 0
  const comp = s.composite.score || 50
  return comp * 0.40 + Math.min(Math.max(expRet, 0) * 2, 100) * 0.35 + Math.min(rr * 10, 100) * 0.25
}

const filteredSignals = computed(() => {
  let list = signals.value
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(s => s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q))
  }
  if (signalFilter.value) {
    switch (signalFilter.value) {
      case 'short_buy': list = list.filter(s => s.short_term.score >= 60); break
      case 'short_sell': list = list.filter(s => s.short_term.score < 40); break
      case 'long_buy': list = list.filter(s => s.long_term.score >= 60); break
      case 'long_sell': list = list.filter(s => s.long_term.score < 40); break
    }
  }
  if (typeFilter.value) {
    list = list.filter(s => s.type === typeFilter.value)
  }
  return list.sort((a, b) => profitScore(b) - profitScore(a))
})

const positionCount = computed(() => signals.value.filter(s => s.type === '持仓').length)
const watchlistCount = computed(() => signals.value.filter(s => s.type === '自选').length)
const shortBuyCount = computed(() => signals.value.filter(s => s.short_term.score >= 60).length)
const longBuyCount = computed(() => signals.value.filter(s => s.long_term.score >= 60).length)
const shortSellCount = computed(() => signals.value.filter(s => s.short_term.score < 40).length)
const longSellCount = computed(() => signals.value.filter(s => s.long_term.score < 40).length)

// ── News Feed view ──
const newsSearchText = ref('')

interface NewsFeedItem {
  _key: string
  code: string
  name: string
  title: string
  date: string
  source: string
  keywords: string[]
}

const newsFeedPositive = computed<NewsFeedItem[]>(() => {
  const items: NewsFeedItem[] = []
  for (const s of signals.value) {
    const ns = s.analysis.news_sentiment
    if (!ns?.recent_positive_news?.length) continue
    for (const n of ns.recent_positive_news) {
      items.push({
        _key: `${s.code}_pos_${n.title}_${n.date}`,
        code: s.code,
        name: s.name,
        title: n.title,
        date: n.date || '',
        source: n.source || '',
        keywords: n.keywords || [],
      })
    }
  }
  return items
})

const newsFeedNegative = computed<NewsFeedItem[]>(() => {
  const items: NewsFeedItem[] = []
  for (const s of signals.value) {
    const ns = s.analysis.news_sentiment
    if (!ns?.recent_negative_news?.length) continue
    for (const n of ns.recent_negative_news) {
      items.push({
        _key: `${s.code}_neg_${n.title}_${n.date}`,
        code: s.code,
        name: s.name,
        title: n.title,
        date: n.date || '',
        source: n.source || '',
        keywords: n.keywords || [],
      })
    }
  }
  return items
})

const filteredPositiveNews = computed(() => {
  if (!newsSearchText.value) return newsFeedPositive.value
  const q = newsSearchText.value.toLowerCase()
  return newsFeedPositive.value.filter(n =>
    n.title.toLowerCase().includes(q) ||
    n.code.toLowerCase().includes(q) ||
    n.name.toLowerCase().includes(q)
  )
})

const filteredNegativeNews = computed(() => {
  if (!newsSearchText.value) return newsFeedNegative.value
  const q = newsSearchText.value.toLowerCase()
  return newsFeedNegative.value.filter(n =>
    n.title.toLowerCase().includes(q) ||
    n.code.toLowerCase().includes(q) ||
    n.name.toLowerCase().includes(q)
  )
})

const signalsWithNewsCount = computed(() =>
  signals.value.filter(s => (s.analysis.news_sentiment?.news_count ?? 0) > 0).length
)

function fetchSignals() {
  loading.value = true
  monitorApi.getSignals().then(resp => {
    signals.value = (resp.data as any).data || []
  }).catch(() => {
    ElMessage.error('获取监控信号失败')
  }).finally(() => {
    loading.value = false
  })
}

function handleRefresh() {
  refreshing.value = true
  monitorApi.refresh().then(() => {
    ElMessage.success('刷新任务已启动')
    setTimeout(fetchSignals, 3000)
  }).catch(() => {
    ElMessage.error('刷新失败')
  }).finally(() => {
    refreshing.value = false
    lastRefresh.value = new Date().toLocaleTimeString()
  })
}

function showDetail(s: MonitorSignal) {
  detailData.value = s
  detailTab.value = 'fund_flow'
  detailVisible.value = true
}

function showStockDetail(code: string) {
  const s = signals.value.find(x => x.code === code)
  if (s) showDetail(s)
}

function signalLabel(sig: string): string {
  const map: Record<string, string> = { strong_buy: '强烈买入', buy: '买入', hold: '持有', sell: '卖出', strong_sell: '强烈卖出' }
  return map[sig] || sig
}

function signalTagType(sig: string): string {
  if (sig === 'strong_buy' || sig === 'buy') return 'danger'
  if (sig === 'sell' || sig === 'strong_sell') return 'success'
  return 'info'
}

function dimLabel(k: string): string {
  const m: Record<string, string> = { fund_flow_score: '主力资金', research_score: '研报', technical_score: '技术面', valuation_score: '估值', composite_score: '综合评分' }
  return m[k] || k
}

function adviceTagType(signal?: string): string {
  if (signal === 'buy') return 'danger'
  if (signal === 'sell') return 'success'
  if (signal === 'watch') return 'info'
  return 'warning'
}

function confLevelType(level: string): string {
  if (level === '高') return 'danger'
  if (level === '中') return 'warning'
  return 'info'
}

function riskLevelClass(level: string): string {
  if (level === '低') return 'risk-low'
  if (level === '高') return 'risk-high'
  return 'risk-mid'
}

function scoreColor(score: number): string {
  if (score >= 75) return '#f56c6c'
  if (score >= 60) return '#e6a23c'
  if (score >= 40) return '#909399'
  return '#67c23a'
}

function fmtPrice(v: number | undefined | null): string {
  if (v == null || v === 0) return '--'
  return '¥' + v.toFixed(2)
}

function fmtChange(v: number | undefined | null): string {
  if (v == null) return '--'
  const sign = v >= 0 ? '+' : ''
  return sign + v.toFixed(2) + '%'
}

onMounted(() => {
  fetchSignals()
  refreshTimer = setInterval(fetchSignals, 60000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.ai-monitor {
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-sub {
  font-size: 12px;
  color: var(--text-muted, #999);
  margin-left: 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.refresh-tag { font-size: 11px; }

.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.search-input { width: 200px; }
.filter-select { width: 140px; }

.stats-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.stat-card { flex: 1; min-width: 100px; }
.stat-label { font-size: 12px; color: var(--text-muted, #999); }
.stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }

.signal-grid {
  flex: 1;
  overflow-y: auto;
}

.signal-card {
  margin-bottom: 12px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.signal-card:hover {
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stock-code {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  color: var(--text-muted, #999);
}

.stock-name {
  font-size: 15px;
  font-weight: 600;
}

.card-price {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.price-val {
  font-size: 20px;
  font-weight: 700;
  font-family: 'IBM Plex Mono', monospace;
}

.change { font-size: 13px; font-weight: 600; }
.change.up { color: #f56c6c; }
.change.down { color: #67c23a; }

.composite-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.confidence { font-size: 12px; color: var(--text-muted, #999); }
.profit-badge {
  font-size: 10px;
  font-weight: 700;
  font-family: 'IBM Plex Mono', monospace;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--el-color-success-light-7, #e1f3d8);
  color: #67c23a;
}

.signal-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.signal-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar-label {
  font-size: 11px;
  color: var(--text-muted, #999);
  width: 28px;
  flex-shrink: 0;
}

.reasons-preview {
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.reason-line {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.short-reason { color: #e6a23c; }
.long-reason { color: #409eff; }

.ns-card-badge {
  margin-left: auto;
  font-size: 10px;
  padding: 0 4px;
  height: 18px;
  line-height: 18px;
}

.divergence-tip {
  margin-top: 6px;
  padding: 4px 8px;
  background: var(--el-color-warning-light-9, #fdf6ec);
  border-radius: 4px;
  font-size: 11px;
  color: #e6a23c;
}

/* ===== Main Tabs ===== */
.main-tabs { margin-top: 8px; }
.main-tabs .el-tabs__header { margin-bottom: 12px; }
.main-tabs .el-tabs__item { font-weight: 600; font-size: 14px; }
.sentiment-count { margin-left: 4px; }

/* ===== Sentiment Page (News Feed) ===== */
.sentiment-page { min-height: 60vh; }
.sentiment-group { margin-bottom: 24px; }
.sg-header {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 10px;
  padding: 6px 10px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.sg-header small { font-size: 12px; font-weight: 400; color: #999; }
.sg-bullish { background: #fef0f0; color: #f56c6c; }
.sg-bearish { background: #f0f9eb; color: #67c23a; }

.news-feed-card {
  padding: 10px 12px;
  margin-bottom: 8px;
  background: #fff;
  border-left: 3px solid #f56c6c;
  border-radius: 6px;
  cursor: pointer;
  transition: all .15s;
  box-shadow: 0 1px 2px rgba(0,0,0,.06);
}
.news-feed-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.1); transform: translateY(-1px); }
.news-feed-card.card-bearish { border-left-color: #67c23a; }

.nfc-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.nfc-stock { cursor: pointer; font-size: 13px; }
.nfc-stock:hover { color: #409eff; }
.nfc-name { font-size: 12px; color: #999; margin-left: 4px; }
.nfc-tag { margin-left: auto; font-size: 10px; height: 20px; line-height: 20px; }
.nfc-title { font-size: 13px; font-weight: 500; margin-bottom: 6px; line-height: 1.4; color: #333; }
.nfc-meta { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #999; flex-wrap: wrap; }
.nfc-date { white-space: nowrap; }
.nfc-source { white-space: nowrap; }
.nfc-kws { display: flex; gap: 2px; flex-wrap: wrap; }

.stat-bullish .stat-value { color: #f56c6c; }
.stat-bearish .stat-value { color: #67c23a; }

/* Price Prediction Row */
.pp-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  padding: 4px 6px;
  background: var(--el-color-info-light-9, #f4f4f5);
  border-radius: 4px;
  font-size: 11px;
  flex-wrap: wrap;
}
.pp-row-target, .pp-row-stop, .pp-row-return { white-space: nowrap; font-size: 10px; }
.pp-action-tag { font-size: 10px; padding: 0 4px; height: 18px; line-height: 18px; }
.pp-row-risk {
  margin-left: auto;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
}
.pp-row-risk.risk-low { background: #e1f3d8; color: #67c23a; }
.pp-row-risk.risk-mid { background: #faecd8; color: #e6a23c; }
.pp-row-risk.risk-high { background: #fde2e2; color: #f56c6c; }

/* Price Prediction Detail */
.pp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.pp-item { display: flex; flex-direction: column; }
.pp-label { font-size: 11px; color: #999; margin-bottom: 2px; }
.pp-val { font-size: 18px; font-weight: 700; }
.pp-val.risk-low { color: #67c23a; }
.pp-val.risk-mid { color: #e6a23c; }
.pp-val.risk-high { color: #f56c6c; }
.pp-detail {
  padding: 12px;
  background: var(--el-color-info-light-9, #f4f4f5);
  border-radius: 6px;
  font-size: 13px;
  line-height: 2;
}
.pp-detail strong { font-weight: 600; }

/* AI Trading Advice */
.dl-advice {
  margin-bottom: 16px;
  border-left: 4px solid #909399;
}
.dl-advice.advice-buy { border-left-color: #f56c6c; }
.dl-advice.advice-sell { border-left-color: #67c23a; }
.dl-advice.advice-watch { border-left-color: #909399; }
.dl-advice.advice-hold { border-left-color: #e6a23c; }
.advice-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.advice-label { font-size: 14px; font-weight: 700; }
.advice-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.advice-reason, .advice-exit {
  font-size: 13px;
  line-height: 1.5;
  padding: 6px 8px;
  background: var(--el-fill-color, #f5f5f5);
  border-radius: 4px;
}
.advice-summary {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 10px;
  line-height: 1.5;
}
.advice-tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 4px 0;
}
.reflection-tag {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.advice-divergence {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  padding: 6px 12px;
  margin-top: 6px;
  background: #fff7e6;
  border-radius: 4px;
  font-size: 12px;
  color: #d48806;
}
.advice-divergence .div-icon {
  font-size: 14px;
}
.advice-divergence .div-item {
  line-height: 1.4;
}
.advice-price-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 4px;
}
.adv-price-item {
  flex: 1;
  min-width: 120px;
  background: #fafafa;
  border-radius: 4px;
  padding: 6px 10px;
  text-align: center;
}
.adv-price-item .ap-label {
  display: block;
  font-size: 11px;
  color: #909399;
  margin-bottom: 2px;
}
.adv-price-item .ap-value {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
}
.adv-price-item .ap-value small {
  font-size: 11px;
  font-weight: 400;
}
.adv-icon { margin-right: 4px; }
.advice-metrics {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.adv-metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}
.adv-m-label { font-size: 10px; color: #999; }
.adv-m-val { font-size: 13px; font-weight: 600; }
.advice-dims {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dim-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.dim-label { font-size: 11px; color: #999; width: 56px; flex-shrink: 0; }
.dim-bar-bg {
  flex: 1;
  height: 6px;
  background: var(--el-fill-color, #f0f0f0);
  border-radius: 3px;
  overflow: hidden;
}
.dim-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.dim-score { font-size: 11px; font-weight: 600; width: 24px; text-align: right; }

/* Price Prediction Summary (在详情弹窗composite旁) */
.pp-summary {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.pp-sum-item { display: flex; flex-direction: column; align-items: center; min-width: 50px; }
.pp-sum-label { font-size: 10px; color: #999; }
.pp-sum-val { font-size: 14px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
.pp-sum-val.up { color: #f56c6c; }
.pp-sum-val.down { color: #67c23a; }
.pp-risk-tag { font-size: 11px; padding: 1px 4px; border-radius: 3px; }
.pp-risk-tag.risk-low { background: #e1f3d8; color: #67c23a; }
.pp-risk-tag.risk-mid { background: #faecd8; color: #e6a23c; }
.pp-risk-tag.risk-high { background: #fde2e2; color: #f56c6c; }

.dl-summary { margin-bottom: 16px; }

/* Price Prediction Collapse */
.pp-collapse { margin-bottom: 16px; }
.pp-detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.pp-detail-item {
  display: flex;
  flex-direction: column;
  padding: 6px 8px;
  background: var(--el-fill-color, #f5f5f5);
  border-radius: 4px;
}
.pp-dl-label { font-size: 11px; color: #999; }
.pp-dl-val { font-size: 14px; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
.pp-dl-val.down { color: #67c23a; }

/* Detail Dialog */
.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dl-code {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 14px;
  color: var(--text-muted, #999);
}

.dl-industry {
  font-size: 12px;
  color: var(--text-muted, #999);
}

.detail-price {
  margin-bottom: 16px;
  font-size: 14px;
}

.dl-signals { margin-bottom: 16px; }

.dl-signal-box {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #eee);
}

.short-box { border-left: 3px solid #e6a23c; }
.long-box { border-left: 3px solid #409eff; }

.dl-signal-header {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-muted, #999);
}

.dl-signal-value {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dl-score {
  font-size: 24px;
  font-weight: 700;
}

.dl-breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0;
}

.bd-item {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--el-fill-color, #f5f5f5);
  border-radius: 4px;
}

.bd-label { margin-right: 4px; color: var(--text-muted, #999); }

.dl-reasons {
  margin: 8px 0 0;
  padding-left: 16px;
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.dl-reasons li { margin-bottom: 2px; }

.dl-composite { margin-bottom: 16px; }

.dl-comp-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.comp-label { font-size: 12px; color: var(--text-muted, #999); }
.comp-score { font-size: 28px; font-weight: 700; }
.comp-conf { font-size: 12px; color: var(--text-muted, #999); }
.comp-div { font-size: 11px; color: #e6a23c; }

.dl-tabs { margin-top: 8px; }

.tab-content { padding: 8px 0; }
.tab-sub { margin-bottom: 12px; }
.tab-sub h4 { margin: 0 0 4px; font-size: 13px; }
.tab-sub p { font-size: 12px; color: var(--text-muted, #999); margin: 0 0 4px; }
.tab-sub ul { margin: 0; padding-left: 16px; font-size: 12px; }
.tab-sub li { margin-bottom: 2px; }

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.detail-item {
  padding: 6px 8px;
  background: var(--el-fill-color, #f5f5f5);
  border-radius: 4px;
}

.di-label {
  display: block;
  font-size: 11px;
  color: var(--text-muted, #999);
}

.di-value {
  display: block;
  font-size: 14px;
  font-weight: 600;
  font-family: 'IBM Plex Mono', monospace;
}
</style>
