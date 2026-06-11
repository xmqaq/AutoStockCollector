<template>
  <div class="workflow-canvas">
    <div class="canvas-toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="workflowName"
          placeholder="工作流名称"
          size="small"
          style="width: 200px"
        />
        <el-input
          v-model="workflowDescription"
          placeholder="工作流描述"
          size="small"
          style="width: 300px"
        />
      </div>
      <div class="toolbar-center">
        <el-button size="small" @click="addNode('start')">
          <el-icon><VideoPlay /></el-icon> 起始节点
        </el-button>
        <el-button size="small" @click="addNode('filter')">
          <el-icon><Filter /></el-icon> 筛选节点
        </el-button>
        <el-button size="small" @click="addNode('score')">
          <el-icon><Star /></el-icon> 评分节点
        </el-button>
        <el-button size="small" @click="addNode('ai_agent')">
          <el-icon><User /></el-icon> AI节点
        </el-button>
        <el-button size="small" @click="addNode('combine')">
          <el-icon><Collection /></el-icon> 组合节点
        </el-button>
        <el-button size="small" @click="addNode('risk_control')">
          <el-icon><CircleCheck /></el-icon> 风控节点
        </el-button>
        <el-button size="small" @click="addNode('end')">
          <el-icon><CircleClose /></el-icon> 结束节点
        </el-button>
        <el-button size="small" @click="addNode('data_fetch')">
          <el-icon><DataBoard /></el-icon> 数据获取
        </el-button>
        <el-button size="small" @click="addNode('technical_indicator')">
          <el-icon><TrendCharts /></el-icon> 技术指标
        </el-button>
        <el-button size="small" @click="addNode('fundamental_filter')">
          <el-icon><Reading /></el-icon> 基本面
        </el-button>
        <el-button size="small" @click="addNode('market_sentiment')">
          <el-icon><ChatLineSquare /></el-icon> 市场情绪
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-button size="small" @click="undo" :disabled="!canUndo" title="撤销 (Ctrl+Z)">
          <el-icon><RefreshLeft /></el-icon>
        </el-button>
        <el-button size="small" @click="redo" :disabled="!canRedo" title="重做 (Ctrl+Y)">
          <el-icon><RefreshRight /></el-icon>
        </el-button>
        <el-button size="small" @click="exportWorkflow" title="导出工作流">
          <el-icon><Download /></el-icon> 导出
        </el-button>
        <el-button size="small" @click="triggerImport" title="导入工作流">
          <el-icon><Upload /></el-icon> 导入
        </el-button>
        <input type="file" ref="importInput" @change="importWorkflow" accept=".json" style="display: none" />
        <el-divider direction="vertical" />
        <el-button size="small" @click="handleCancel">取消</el-button>
        <el-button type="primary" size="small" @click="handleSave">保存</el-button>
      </div>
    </div>

    <div class="canvas-main">
      <div class="node-palette">
        <div class="palette-title">节点面板</div>
        <div
          v-for="nodeType in nodeTypes"
          :key="nodeType.type"
          class="palette-item"
          draggable="true"
          @dragstart="onDragStart($event, nodeType)"
        >
          <el-icon>
            <component :is="getNodeIcon(nodeType.icon)" />
          </el-icon>
          <span>{{ nodeType.label }}</span>
        </div>
      </div>

      <div
        class="canvas-area"
        ref="canvasRef"
        @drop="onDrop"
        @dragover.prevent
        @click="onCanvasClick"
        @keydown="onKeyDown"
        tabindex="0"
      >
        <div
          v-for="node in nodes"
          :key="node.id"
          class="workflow-node"
          :class="[`node-type-${node.type}`, { selected: selectedNode?.id === node.id, hovering: hoveringNode?.id === node.id }]"
          :style="{ left: node.x + 'px', top: node.y + 'px', '--node-color': getNodeColor(node.type) }"
          @click.stop="selectNode(node)"
          @mousedown="startDrag($event, node)"
          @mouseenter="hoveringNode = node"
          @mouseleave="hoveringNode = null"
        >
          <div class="node-header">
            <el-icon>
              <component :is="getNodeIcon(node.type)" />
            </el-icon>
            <span>{{ node.label }}</span>
          </div>
          <div class="node-body">
            <span class="node-type-label">{{ getNodeTypeLabel(node.type) }}</span>
          </div>
          <div class="node-ports">
            <div
              v-for="input in node.inputs"
              :key="input"
              class="port port-input"
              :class="{ connecting: connecting && connectingType === 'output' }"
              @click.stop="connecting ? completeConnection(node, input) : startConnect(node, input, 'input')"
            >
              <div class="port-dot"></div>
              <span class="port-label">{{ input }}</span>
            </div>
            <div
              v-for="output in node.outputs"
              :key="output"
              class="port port-output"
              :class="{ connecting: connecting && connectingType === 'input' }"
              @click.stop="connecting ? completeConnection(node, output) : startConnect(node, output, 'output')"
            >
              <div class="port-dot"></div>
              <span class="port-label">{{ output }}</span>
            </div>
          </div>
        </div>

        <svg class="edges-svg" v-if="edges.length > 0">
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#409eff" />
            </marker>
          </defs>
          <path
            v-for="edge in edges"
            :key="edge.id"
            :d="getEdgePath(edge)"
            fill="none"
            stroke="#409eff"
            stroke-width="2"
            marker-end="url(#arrowhead)"
            class="workflow-edge"
            @click.stop="selectEdge(edge)"
          />
        </svg>
      </div>
    </div>

    <div v-if="selectedNode || connecting || selectedEdge" class="properties-panel">
      <div class="panel-header">
        <span>{{ selectedNode ? '节点配置' : selectedEdge ? '连线配置' : '连接中...' }}</span>
        <el-button
          v-if="selectedNode"
          type="danger"
          size="small"
          text
          @click="deleteSelectedNode"
        >
          <el-icon><Delete /></el-icon> 删除节点
        </el-button>
        <el-button
          v-if="selectedEdge"
          type="danger"
          size="small"
          text
          @click="deleteSelectedEdge"
        >
          <el-icon><Delete /></el-icon> 删除连线
        </el-button>
      </div>
      <div v-if="selectedNode" class="panel-body">
        <el-form label-width="100px" size="small">
          <el-form-item label="节点名称">
            <el-input v-model="selectedNode.label" @change="updateNode" />
          </el-form-item>
          <el-form-item
            v-for="(config, key) in getNodeConfigSchema(selectedNode.type)"
            :key="key"
            :label="config.label"
          >
            <el-select
              v-if="config.type === 'select'"
              v-model="selectedNode.config[key]"
              @change="updateNode"
            >
              <el-option
                v-for="opt in config.options"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
            <el-input-number
              v-else-if="config.type === 'number'"
              v-model="selectedNode.config[key]"
              @change="updateNode"
            />
            <el-switch
              v-else-if="config.type === 'boolean'"
              v-model="selectedNode.config[key]"
              @change="updateNode"
            />
            <el-input
              v-else
              v-model="selectedNode.config[key]"
              @change="updateNode"
            />
          </el-form-item>
        </el-form>
      </div>
      <div v-else-if="selectedEdge" class="panel-body">
        <el-form label-width="80px" size="small">
          <el-form-item label="连线标签">
            <el-input v-model="selectedEdge.label" placeholder="可选" />
          </el-form-item>
          <el-form-item label="源节点">
            <span>{{ getNodeLabel(selectedEdge.source) }}</span>
          </el-form-item>
          <el-form-item label="目标节点">
            <span>{{ getNodeLabel(selectedEdge.target) }}</span>
          </el-form-item>
        </el-form>
      </div>
      <div v-else-if="connecting" class="panel-body connecting-hint">
        <p>点击另一个节点的端口完成连接</p>
        <p class="hint-sub">或点击画布取消</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  VideoPlay, Filter, Star, User, Collection, CircleCheck, CircleClose,
  Delete, VideoPause, Connection, Operation, Timer, TrendCharts,
  DataLine, Reading, ChatLineSquare, DataAnalysis, DataBoard,
  RefreshLeft, RefreshRight, Download, Upload
} from '@element-plus/icons-vue'
import type { Workflow, WorkflowNode, WorkflowEdge, WorkflowTemplate } from '@/api/workflow'

const props = defineProps<{
  workflow: Workflow | null
  templates: WorkflowTemplate[]
}>()

const emit = defineEmits<{
  (e: 'save', workflow: Workflow): void
  (e: 'cancel'): void
}>()

const canvasRef = ref<HTMLElement>()
const importInput = ref<HTMLInputElement>()
let autoSaveTimer: number | null = null
const autoSaveInterval = 30000
const nodes = ref<WorkflowNode[]>([])
const edges = ref<WorkflowEdge[]>([])
const workflowName = ref('')
const workflowDescription = ref('')
const selectedNode = ref<WorkflowNode | null>(null)
const selectedEdge = ref<WorkflowEdge | null>(null)
const connecting = ref(false)
const connectingNode = ref<WorkflowNode | null>(null)
const connectingPort = ref('')
const connectingType = ref<'input' | 'output'>('input')
const selectedNodes = ref<Set<string>>(new Set())

const undoStack = ref<{ nodes: WorkflowNode[], edges: WorkflowEdge[] }[]>([])
const redoStack = ref<{ nodes: WorkflowNode[], edges: WorkflowEdge[] }[]>([])
const maxHistorySize = 50

function saveHistory() {
  undoStack.value.push({
    nodes: JSON.parse(JSON.stringify(nodes.value)),
    edges: JSON.parse(JSON.stringify(edges.value))
  })
  if (undoStack.value.length > maxHistorySize) {
    undoStack.value.shift()
  }
  redoStack.value = []
}

function undo() {
  if (undoStack.value.length === 0) return
  redoStack.value.push({
    nodes: JSON.parse(JSON.stringify(nodes.value)),
    edges: JSON.parse(JSON.stringify(edges.value))
  })
  const state = undoStack.value.pop()!
  nodes.value = state.nodes
  edges.value = state.edges
  selectedNode.value = null
  selectedEdge.value = null
  ElMessage.success('已撤销')
}

function redo() {
  if (redoStack.value.length === 0) return
  undoStack.value.push({
    nodes: JSON.parse(JSON.stringify(nodes.value)),
    edges: JSON.parse(JSON.stringify(edges.value))
  })
  const state = redoStack.value.pop()!
  nodes.value = state.nodes
  edges.value = state.edges
  selectedNode.value = null
  selectedEdge.value = null
  ElMessage.success('已重做')
}

const canUndo = computed(() => undoStack.value.length > 0)
const canRedo = computed(() => redoStack.value.length > 0)

const nodeTypes = [
  { type: 'start', label: '起始节点', icon: 'play', color: '#67c23a', description: '定义数据来源' },
  { type: 'filter', label: '筛选节点', icon: 'filter', color: '#409eff', description: '按条件过滤' },
  { type: 'score', label: '评分节点', icon: 'star', color: '#e6a23c', description: '多维度评分' },
  { type: 'ai_agent', label: 'AI节点', icon: 'robot', color: '#9b59b6', description: 'AI深度分析' },
  { type: 'combine', label: '组合节点', icon: 'collection', color: '#3498db', description: '结果组合' },
  { type: 'risk_control', label: '风控节点', icon: 'shield', color: '#e74c3c', description: '风险控制' },
  { type: 'end', label: '结束节点', icon: 'stop', color: '#95a5a6', description: '输出结果' },
  { type: 'data_fetch', label: '数据获取', icon: 'database', color: '#1abc9c', description: '获取多源数据' },
  { type: 'technical_indicator', label: '技术指标', icon: 'line-chart', color: '#2ecc71', description: '计算技术指标' },
  { type: 'fundamental_filter', label: '基本面筛选', icon: 'reading', color: '#16a085', description: '财务指标筛选' },
  { type: 'market_sentiment', label: '市场情绪', icon: 'chat', color: '#f39c12', description: '市场情绪分析' },
  { type: 'index_components', label: '指数成分', icon: 'collection', color: '#8e44ad', description: '获取指数成分股' },
  { type: 'compare', label: '对比分析', icon: 'analysis', color: '#c0392b', description: '多股对比分析' },
  { type: 'chanlun_zs', label: '中枢识别', icon: 'circle', color: '#d35400', description: '缠论中枢识别' },
  { type: 'chanlun_bc', label: '背驰判断', icon: 'trend', color: '#c0392b', description: '缠论背驰判断' },
  { type: 'chanlun_buy1', label: '缠论一买', icon: 'first', color: '#27ae60', description: '第一类买点' },
  { type: 'chanlun_buy2', label: '缠论二买', icon: 'second', color: '#2980b9', description: '第二类买点' },
  { type: 'chanlun_buy3', label: '缠论三买', icon: 'third', color: '#8e44ad', description: '第三类买点' }
]

const nodeConfigSchemas: Record<string, any> = {
  start: {
    source: {
      type: 'select',
      label: '数据源',
      options: [
        { value: 'all', label: '全部股票' },
        { value: 'watchlist', label: '自选股' },
        { value: 'sector', label: '板块' }
      ]
    },
    sector: { type: 'text', label: '板块名称' }
  },
  filter: {
    filter_type: {
      type: 'select',
      label: '筛选类型',
      options: [
        { value: 'price_range', label: '价格区间' },
        { value: 'volume_ratio', label: '成交量放大' },
        { value: 'pe_range', label: 'PE范围' },
        { value: 'pb_range', label: 'PB范围' },
        { value: 'trend', label: '趋势筛选' },
        { value: 'fund_flow', label: '资金流向' },
        { value: 'market_cap', label: '市值筛选' },
        { value: 'exclude_st', label: '排除ST' },
        { value: 'news_sentiment', label: '舆情筛选' },
        { value: 'sector', label: '板块筛选' }
      ]
    },
    min_price: { type: 'number', label: '最低价' },
    max_price: { type: 'number', label: '最高价' },
    threshold: { type: 'number', label: '阈值' },
    direction: {
      type: 'select',
      label: '方向',
      options: [
        { value: 'positive', label: '正向' },
        { value: 'negative', label: '负向' }
      ]
    },
    min_pe: { type: 'number', label: '最小PE' },
    max_pe: { type: 'number', label: '最大PE' },
    min_pb: { type: 'number', label: '最小PB' },
    max_pb: { type: 'number', label: '最大PB' },
    trend_type: {
      type: 'select',
      label: '趋势类型',
      options: [
        { value: 'up', label: '上涨' },
        { value: 'down', label: '下跌' }
      ]
    },
    min_cap: { type: 'number', label: '最小市值(亿)' },
    max_cap: { type: 'number', label: '最大市值(亿)' },
    min_positive_ratio: { type: 'number', label: '最小正面舆情比例' },
    sector: { type: 'text', label: '板块名称' }
  },
  score: {
    score_type: {
      type: 'select',
      label: '评分类型',
      options: [
        { value: 'weighted', label: '加权评分' },
        { value: 'technical', label: '技术面评分' },
        { value: 'fundamental', label: '基本面评分' },
        { value: 'fund_flow', label: '资金流评分' },
        { value: 'sentiment', label: '舆情评分' }
      ]
    },
    technical_weight: { type: 'number', label: '技术面权重' },
    fundamental_weight: { type: 'number', label: '基本面权重' }
  },
  ai_agent: {
    agent_id: { type: 'text', label: 'Agent ID' },
    top_n: { type: 'number', label: '分析前N只' }
  },
  combine: {
    strategy: {
      type: 'select',
      label: '组合策略',
      options: [
        { value: 'top_n', label: '取前N名' },
        { value: 'min_score', label: '最低分过滤' },
        { value: 'diversify', label: '分散配置' }
      ]
    },
    top_n: { type: 'number', label: '数量' },
    min_score: { type: 'number', label: '最低分' }
  },
  risk_control: {
    max_positions: { type: 'number', label: '最大持仓数' },
    max_position_ratio: { type: 'number', label: '单只最大比例' },
    exclude_st: { type: 'boolean', label: '排除ST股票' }
  },
  end: {
    output: {
      type: 'select',
      label: '输出类型',
      options: [
        { value: 'list', label: '列表' },
        { value: 'export', label: '导出' }
      ]
    },
    top_n: { type: 'number', label: '输出数量' }
  },
  data_fetch: {
    data_type: {
      type: 'select',
      label: '数据类型',
      options: [
        { value: 'kline', label: 'K线数据' },
        { value: 'realtime', label: '实时行情' },
        { value: 'financial', label: '财务数据' },
        { value: 'fund_flow', label: '资金流向' },
        { value: 'sentiment', label: '舆情数据' },
        { value: 'dragon_tiger', label: '龙虎榜' },
        { value: 'margin', label: '融资融券' },
        { value: 'signals', label: '交易信号' }
      ]
    },
    days: { type: 'number', label: '历史天数' },
    limit: { type: 'number', label: '数据条数' }
  },
  technical_indicator: {
    indicator_type: {
      type: 'select',
      label: '指标类型',
      options: [
        { value: 'ma', label: '均线(MA)' },
        { value: 'ema', label: '指数均线(EMA)' },
        { value: 'macd', label: 'MACD' },
        { value: 'kdj', label: 'KDJ' },
        { value: 'rsi', label: 'RSI' },
        { value: 'boll', label: '布林带(BOLL)' }
      ]
    },
    params: { type: 'text', label: '参数配置', placeholder: '如: 5,20,60' }
  },
  fundamental_filter: {
    filter_type: {
      type: 'select',
      label: '财务指标',
      options: [
        { value: 'pe', label: '市盈率(PE)' },
        { value: 'pb', label: '市净率(PB)' },
        { value: 'roe', label: '净资产收益率(ROE)' },
        { value: 'revenue_growth', label: '营收增长率' },
        { value: 'profit_growth', label: '净利润增长率' }
      ]
    },
    operator: {
      type: 'select',
      label: '比较运算符',
      options: [
        { value: 'gt', label: '大于' },
        { value: 'lt', label: '小于' },
        { value: 'between', label: '区间' }
      ]
    },
    value: { type: 'number', label: '阈值' },
    min_value: { type: 'number', label: '最小值' },
    max_value: { type: 'number', label: '最大值' }
  },
  market_sentiment: {
    analysis_type: {
      type: 'select',
      label: '分析类型',
      options: [
        { value: 'overall', label: '整体情绪' },
        { value: 'hot_sectors', label: '热点板块' },
        { value: 'capital_flow', label: '资金流向' },
        { value: 'news_impact', label: '新闻影响' }
      ]
    },
    threshold: { type: 'number', label: '情绪阈值' }
  },
  index_components: {
    index_code: {
      type: 'select',
      label: '指数',
      options: [
        { value: '000300.sh', label: '沪深300' },
        { value: '000905.sh', label: '中证500' },
        { value: '000001.sh', label: '上证指数' },
        { value: '399001.sz', label: '深证成指' },
        { value: '399006.sz', label: '创业板指' }
      ]
    }
  },
  compare: {
    compare_type: {
      type: 'select',
      label: '对比维度',
      options: [
        { value: 'price', label: '价格对比' },
        { value: 'performance', label: '涨跌幅对比' },
        { value: 'valuation', label: '估值对比' },
        { value: 'fund_flow', label: '资金流向对比' }
      ]
    },
    ranking: {
      type: 'select',
      label: '排序方式',
      options: [
        { value: 'desc', label: '降序' },
        { value: 'asc', label: '升序' }
      ]
    }
  },
  chanlun_zs: {
    level: {
      type: 'select',
      label: '级别',
      options: [
        { value: '1min', label: '1分钟' },
        { value: '5min', label: '5分钟' },
        { value: '15min', label: '15分钟' },
        { value: '30min', label: '30分钟' },
        { value: '60min', label: '60分钟' },
        { value: 'daily', label: '日线' }
      ]
    },
    min_bars: { type: 'number', label: '中枢最小K线数' }
  },
  chanlun_bc: {
    bc_type: {
      type: 'select',
      label: '背驰类型',
      options: [
        { value: 'divergence', label: '背驰判断' },
        { value: 'new_high_low', label: '新高新低' }
      ]
    },
    threshold: { type: 'number', label: '背驰阈值' }
  },
  chanlun_buy1: {
    min_price: { type: 'number', label: '最低价' },
    max_price: { type: 'number', label: '最高价' },
    rsi_oversold: { type: 'number', label: 'RSI超卖值' },
    kdj_oversold: { type: 'number', label: 'KDJ超卖值' }
  },
  chanlun_buy2: {
    min_price: { type: 'number', label: '最低价' },
    max_price: { type: 'number', label: '最高价' }
  },
  chanlun_buy3: {
    min_price: { type: 'number', label: '最低价' },
    max_price: { type: 'number', label: '最高价' },
    vol_threshold: { type: 'number', label: '放量倍数阈值' }
  }
}

function getNodeIcon(iconName: string) {
  const icons: Record<string, any> = {
    play: VideoPlay,
    filter: Filter,
    star: Star,
    robot: User,
    collection: Collection,
    shield: CircleCheck,
    stop: CircleClose,
    timer: Timer,
    trend: TrendCharts,
    connection: Connection,
    operation: Operation,
    database: DataBoard,
    'line-chart': TrendCharts,
    reading: Reading,
    chat: ChatLineSquare,
    chatLineSquare: ChatLineSquare,
    analysis: DataAnalysis,
    dataAnalysis: DataAnalysis,
    circle: Timer,
    first: Timer,
    second: Timer,
    third: Timer
  }
  return icons[iconName] || Operation
}

function getNodeTypeLabel(type: string) {
  const node = nodeTypes.find(n => n.type === type)
  return node ? node.description : type
}

function getNodeColor(type: string): string {
  const node = nodeTypes.find(n => n.type === type)
  return node?.color || '#409eff'
}

function getNodeConfigSchema(type: string) {
  return nodeConfigSchemas[type] || {}
}

const previewNode = ref<WorkflowNode | null>(null)
const hoveringNode = ref<WorkflowNode | null>(null)

function showNodePreview(node: WorkflowNode) {
  previewNode.value = node
  hoveringNode.value = node
}

function hideNodePreview() {
  previewNode.value = null
  hoveringNode.value = null
}

function getNodeConfigSummary(node: WorkflowNode): Record<string, any> {
  const schema = getNodeConfigSchema(node.type)
  const summary: Record<string, any> = {}

  for (const [key, config] of Object.entries(schema)) {
    if (node.config[key] !== undefined && node.config[key] !== '' && node.config[key] !== null) {
      const label = (config as any).label || key
      let value = node.config[key]

      if ((config as any).type === 'select') {
        const option = (config as any).options?.find((o: any) => o.value === value)
        value = option?.label || value
      }

      summary[label] = value
    }
  }

  return summary
}

function generateId() {
  return Math.random().toString(36).substr(2, 9)
}

function addNode(type: string) {
  saveHistory()
  const nodeType = nodeTypes.find(n => n.type === type)
  const nodeWidth = 200
  const nodeHeight = 100
  const horizontalGap = 280
  const verticalGap = 140
  const existingCount = nodes.value.length
  const baseX = 100
  const baseY = 100
  const col = existingCount % 5
  const row = Math.floor(existingCount / 5)
  const newNode: WorkflowNode = {
    id: generateId(),
    type,
    label: nodeType?.label || type,
    x: baseX + col * horizontalGap,
    y: baseY + row * verticalGap,
    config: getDefaultConfig(type),
    inputs: ['input'],
    outputs: ['output']
  }

  if (type === 'start') {
    newNode.inputs = []
    newNode.outputs = ['stocks']
  } else if (type === 'end') {
    newNode.inputs = ['result']
    newNode.outputs = []
  } else if (type === 'index_components') {
    newNode.inputs = []
    newNode.outputs = ['stocks']
  } else {
    const ioConfig = getNodeIOConfig(type)
    newNode.inputs = ioConfig.inputs
    newNode.outputs = ioConfig.outputs
  }

  nodes.value.push(newNode)
  selectedNode.value = newNode
}

function getNodeIOConfig(type: string): { inputs: string[], outputs: string[] } {
  const ioConfigs: Record<string, { inputs: string[], outputs: string[] }> = {
    filter: { inputs: ['stocks'], outputs: ['filtered_stocks'] },
    data_fetch: { inputs: ['stocks'], outputs: ['stock_data'] },
    technical_indicator: { inputs: ['stock_data'], outputs: ['indicators'] },
    score: { inputs: ['indicators', 'fund_data'], outputs: ['scores'] },
    ai_agent: { inputs: ['stocks'], outputs: ['analysis'] },
    combine: { inputs: ['scores', 'analysis'], outputs: ['combined'] },
    risk_control: { inputs: ['candidates'], outputs: ['risk_checked'] },
    fundamental_filter: { inputs: ['stocks'], outputs: ['filtered_stocks'] },
    market_sentiment: { inputs: ['market_data'], outputs: ['sentiment'] },
    compare: { inputs: ['stocks'], outputs: ['comparison'] },
    chanlun_zs: { inputs: ['kline_data'], outputs: ['zs_data'] },
    chanlun_bc: { inputs: ['kline_data', 'zs_data'], outputs: ['bc_data'] },
    chanlun_buy1: { inputs: ['kline_data'], outputs: ['buy1_data'] },
    chanlun_buy2: { inputs: ['kline_data', 'buy1_data'], outputs: ['buy2_data'] },
    chanlun_buy3: { inputs: ['kline_data', 'zs_data'], outputs: ['buy3_data'] }
  }
  return ioConfigs[type] || { inputs: ['input'], outputs: ['output'] }
}

function getDefaultConfig(type: string): Record<string, any> {
  const defaults: Record<string, any> = {
    start: { source: 'all' },
    filter: { filter_type: 'price_range', min_price: 0, max_price: 1000 },
    score: { score_type: 'weighted' },
    ai_agent: { agent_id: '', top_n: 20 },
    combine: { strategy: 'top_n', top_n: 20 },
    risk_control: { max_positions: 10, max_position_ratio: 0.1, exclude_st: true },
    end: { output: 'list', top_n: 10 },
    data_fetch: { data_type: 'kline', days: 60, limit: 100 },
    technical_indicator: { indicator_type: 'ma', params: '5,20,60' },
    fundamental_filter: { filter_type: 'pe', operator: 'lt', value: 25 },
    market_sentiment: { analysis_type: 'overall', threshold: 50 },
    index_components: { index_code: '000300.sh' },
    compare: { compare_type: 'performance', ranking: 'desc' },
    chanlun_zs: { level: '60min', min_bars: 3 },
    chanlun_bc: { bc_type: 'divergence', threshold: 0.1 },
    chanlun_buy1: { min_price: 2, max_price: 100, rsi_oversold: 30, kdj_oversold: 20 },
    chanlun_buy2: { min_price: 2, max_price: 100 },
    chanlun_buy3: { min_price: 5, max_price: 100, vol_threshold: 1.5 }
  }
  return defaults[type] || {}
}

function selectNode(node: WorkflowNode) {
  selectedNode.value = node
  selectedEdge.value = null
}

function selectEdge(edge: WorkflowEdge) {
  selectedEdge.value = edge
  selectedNode.value = null
}

function updateNode() {
  const index = nodes.value.findIndex(n => n.id === selectedNode.value?.id)
  if (index !== -1) {
    nodes.value[index] = { ...selectedNode.value! }
  }
}

function getNodeLabel(nodeId: string): string {
  const node = nodes.value.find(n => n.id === nodeId)
  return node ? node.label : nodeId
}

function deleteSelectedNode() {
  if (!selectedNode.value) return

  nodes.value = nodes.value.filter(n => n.id !== selectedNode.value?.id)
  edges.value = edges.value.filter(
    e => e.source !== selectedNode.value?.id && e.target !== selectedNode.value?.id
  )
  selectedNode.value = null
}

function startConnect(node: WorkflowNode, port: string, type: 'input' | 'output') {
  saveHistory()
  connecting.value = true
  connectingNode.value = node
  connectingPort.value = port
  connectingType.value = type
}

function onCanvasClick() {
  if (connecting.value && connectingNode.value) {
    connecting.value = false
    connectingNode.value = null
  }
  selectedNode.value = null
  selectedEdge.value = null
  selectedNodes.value.clear()
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedNode.value) {
      deleteSelectedNode()
    } else if (selectedEdge.value) {
      deleteSelectedEdge()
    }
  } else if (e.key === 'Escape') {
    if (connecting.value) {
      connecting.value = false
      connectingNode.value = null
    }
    selectedNode.value = null
    selectedEdge.value = null
  } else if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    handleSave()
  } else if (e.key === 'z' && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
    e.preventDefault()
    undo()
  } else if ((e.key === 'y' && (e.ctrlKey || e.metaKey)) || (e.key === 'z' && (e.ctrlKey || e.metaKey) && e.shiftKey)) {
    e.preventDefault()
    redo()
  } else if (e.key === 'c' && !connecting.value) {
    if (selectedNode.value) {
      copiedNode.value = { ...selectedNode.value }
      ElMessage.success('节点已复制，按 Ctrl+V 粘贴')
    }
  } else if (e.key === 'v' && (e.ctrlKey || e.metaKey)) {
    if (copiedNode.value) {
      pasteNode()
    }
  } else if (e.key === 'a' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    selectAllNodes()
  }
}

function selectAllNodes() {
  selectedNodes.value = new Set(nodes.value.map(n => n.id))
  ElMessage.info(`已选择 ${nodes.value.length} 个节点`)
}

const copiedNode = ref<WorkflowNode | null>(null)

function pasteNode() {
  if (!copiedNode.value) return
  saveHistory()
  const newNode: WorkflowNode = {
    ...JSON.parse(JSON.stringify(copiedNode.value)),
    id: generateId(),
    x: copiedNode.value.x + 50,
    y: copiedNode.value.y + 50
  }
  nodes.value.push(newNode)
  selectNode(newNode)
  ElMessage.success('节点已粘贴')
}

function completeConnection(targetNode: WorkflowNode, targetPort: string) {
  if (!connecting.value || !connectingNode.value) return

  saveHistory()
  const sourceNode = connectingNode.value
  const sourcePort = connectingPort.value
  const sourceType = connectingType.value

  if (sourceType === 'output' && targetNode.inputs.includes(targetPort)) {
    if (sourceNode.id !== targetNode.id) {
      const exists = edges.value.some(
        e => e.source === sourceNode.id && e.target === targetNode.id
      )
      if (!exists) {
        edges.value.push({
          id: generateId(),
          source: sourceNode.id,
          target: targetNode.id,
          sourceHandle: sourcePort,
          targetHandle: targetPort
        })
      }
    }
  } else if (sourceType === 'input' && targetNode.outputs.includes(targetPort)) {
    if (sourceNode.id !== targetNode.id) {
      const exists = edges.value.some(
        e => e.source === targetNode.id && e.target === sourceNode.id
      )
      if (!exists) {
        edges.value.push({
          id: generateId(),
          source: targetNode.id,
          target: sourceNode.id,
          sourceHandle: targetPort,
          targetHandle: sourcePort
        })
      }
    }
  }

  connecting.value = false
  connectingNode.value = null
}

function deleteSelectedEdge() {
  if (!selectedEdge.value) return
  saveHistory()
  edges.value = edges.value.filter(e => e.id !== selectedEdge.value?.id)
  selectedEdge.value = null
}

let draggingNode = ref<WorkflowNode | null>(null)
let dragStartX = 0
let dragStartY = 0
let nodeStartX = 0
let nodeStartY = 0

function startDrag(event: MouseEvent, node: WorkflowNode) {
  saveHistory()
  draggingNode.value = node
  dragStartX = event.clientX
  dragStartY = event.clientY
  nodeStartX = node.x
  nodeStartY = node.y

  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(event: MouseEvent) {
  if (!draggingNode.value || !canvasRef.value) return

  const dx = event.clientX - dragStartX
  const dy = event.clientY - dragStartY

  const node = nodes.value.find(n => n.id === draggingNode.value?.id)
  if (node) {
    node.x = Math.max(0, nodeStartX + dx)
    node.y = Math.max(0, nodeStartY + dy)
  }
}

function stopDrag() {
  draggingNode.value = null
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

let draggedNodeType: string | null = null

function onDragStart(event: DragEvent, nodeType: any) {
  draggedNodeType = nodeType.type
  event.dataTransfer?.setData('text/plain', nodeType.type)
}

function onDrop(event: DragEvent) {
  if (!draggedNodeType) return

  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return

  const existingCount = nodes.value.length
  const baseX = 100
  const baseY = 100
  const col = existingCount % 5
  const row = Math.floor(existingCount / 5)
  const horizontalGap = 280
  const verticalGap = 140

  const x = baseX + col * horizontalGap
  const y = baseY + row * verticalGap

  const nodeType = nodeTypes.find(n => n.type === draggedNodeType)
  let nodeInputs: string[] = []
  let nodeOutputs: string[] = []

  if (draggedNodeType === 'start') {
    nodeInputs = []
    nodeOutputs = ['stocks']
  } else if (draggedNodeType === 'end') {
    nodeInputs = ['result']
    nodeOutputs = []
  } else if (draggedNodeType === 'index_components') {
    nodeInputs = []
    nodeOutputs = ['stocks']
  } else {
    const ioConfig = getNodeIOConfig(draggedNodeType)
    nodeInputs = ioConfig.inputs
    nodeOutputs = ioConfig.outputs
  }

  const newNode: WorkflowNode = {
    id: generateId(),
    type: draggedNodeType,
    label: nodeType?.label || draggedNodeType,
    x,
    y,
    config: getDefaultConfig(draggedNodeType),
    inputs: nodeInputs,
    outputs: nodeOutputs
  }

  nodes.value.push(newNode)
  selectedNode.value = newNode
  draggedNodeType = null
}

function getEdgePath(edge: WorkflowEdge) {
  const sourceNode = nodes.value.find(n => n.id === edge.source)
  const targetNode = nodes.value.find(n => n.id === edge.target)

  if (!sourceNode || !targetNode) return ''

  const startX = sourceNode.x + 200
  const startY = sourceNode.y + 40
  const endX = targetNode.x
  const endY = targetNode.y + 40

  const midX = (startX + endX) / 2

  return `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`
}

function handleSave() {
  if (!workflowName.value.trim()) {
    return
  }

  const workflow: Workflow = {
    id: props.workflow?.id || '',
    name: workflowName.value,
    description: workflowDescription.value,
    nodes: nodes.value,
    edges: edges.value,
    enabled: true,
    run_count: props.workflow?.run_count || 0,
    tags: props.workflow?.tags || []
  }

  emit('save', workflow)
}

function handleCancel() {
  emit('cancel')
}

function initFromProps() {
  if (props.workflow) {
    workflowName.value = props.workflow.name
    workflowDescription.value = props.workflow.description
    nodes.value = props.workflow.nodes.map(n => ({ ...n }))
    edges.value = props.workflow.edges.map(e => ({ ...e }))
  } else {
    workflowName.value = '新建工作流'
    workflowDescription.value = ''
    nodes.value = []
    edges.value = []
  }
}

watch(() => props.workflow, initFromProps, { immediate: true })

function startAutoSave() {
  if (autoSaveTimer) clearInterval(autoSaveTimer)
  autoSaveTimer = window.setInterval(() => {
    if (nodes.value.length > 0 && workflowName.value.trim()) {
      localStorage.setItem('workflow_draft', JSON.stringify({
        name: workflowName.value,
        description: workflowDescription.value,
        nodes: nodes.value,
        edges: edges.value,
        updatedAt: new Date().toISOString()
      }))
    }
  }, autoSaveInterval)
}

function loadDraft() {
  const draft = localStorage.getItem('workflow_draft')
  if (draft && nodes.value.length === 0) {
    try {
      const data = JSON.parse(draft)
      workflowName.value = data.name || '草稿-' + new Date().toLocaleDateString()
      workflowDescription.value = data.description || ''
      nodes.value = data.nodes || []
      edges.value = data.edges || []
      ElMessage.info('已恢复上次未保存的编辑')
    } catch {
      localStorage.removeItem('workflow_draft')
    }
  }
}

function exportWorkflow() {
  if (!workflowName.value.trim()) {
    ElMessage.warning('请先输入工作流名称')
    return
  }
  const workflow: Workflow = {
    id: props.workflow?.id || '',
    name: workflowName.value,
    description: workflowDescription.value,
    nodes: nodes.value,
    edges: edges.value,
    enabled: true,
    run_count: props.workflow?.run_count || 0,
    tags: props.workflow?.tags || []
  }
  const blob = new Blob([JSON.stringify(workflow, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${workflowName.value}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

function triggerImport() {
  importInput.value?.click()
}

function importWorkflow(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target?.result as string)
      if (data.nodes && data.edges) {
        saveHistory()
        workflowName.value = data.name || '导入工作流'
        workflowDescription.value = data.description || ''
        nodes.value = data.nodes
        edges.value = data.edges
        undoStack.value = []
        redoStack.value = []
        ElMessage.success('导入成功')
      } else {
        ElMessage.error('文件格式不正确')
      }
    } catch {
      ElMessage.error('文件解析失败')
    }
  }
  reader.readAsText(file)
  input.value = ''
}

onMounted(() => {
  startAutoSave()
  loadDraft()
})
</script>

<style scoped>
.workflow-canvas {
  display: flex;
  flex-direction: column;
  height: 80vh;
  background: var(--bg-card);
  border-radius: 8px;
}

.canvas-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--border-color);
  border-bottom: 1px solid var(--border-strong);
}

.toolbar-left, .toolbar-right {
  display: flex;
  gap: 12px;
}

.toolbar-center {
  display: flex;
  gap: 8px;
}

.canvas-main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.node-palette {
  width: 180px;
  background: var(--border-color);
  border-right: 1px solid var(--border-strong);
  padding: 16px;
  overflow-y: auto;
}

.palette-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 12px;
  text-transform: uppercase;
}

.palette-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 8px;
  background: var(--border-strong);
  border-radius: 6px;
  cursor: grab;
  transition: all 0.2s;
}

.palette-item:hover {
  background: #409eff;
  color: #fff;
}

.palette-item:active {
  cursor: grabbing;
}

.canvas-area {
  flex: 1;
  position: relative;
  overflow: auto;
  background: var(--bg-soft);
  background-image:
    linear-gradient(var(--bg-hover) 1px, transparent 1px),
    linear-gradient(90deg, var(--bg-hover) 1px, transparent 1px);
  background-size: 20px 20px;
}

.workflow-node {
  position: absolute;
  width: 200px;
  background: var(--border-strong);
  border: 2px solid var(--node-color, var(--border-heavy));
  border-radius: 8px;
  cursor: move;
  user-select: none;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.workflow-node:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.workflow-node.hovering {
  z-index: 100;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), 0 0 0 2px var(--node-color, #409eff);
}

.workflow-node.selected {
  border-color: var(--node-color, #409eff);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--node-color, #409eff) 30%, transparent);
}

.workflow-node.node-type-start {
  border-color: #67c23a;
}

.workflow-node.node-type-end {
  border-color: #f56c6c;
}

.workflow-node.node-type-ai_agent {
  border-color: #9b59b6;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--border-heavy);
  border-radius: 6px 6px 0 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 3px solid var(--node-color, #409eff);
}

.node-body {
  padding: 10px 12px;
}

.node-type-label {
  font-size: 11px;
  color: var(--text-muted);
}

.node-ports {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  border-top: 1px solid var(--border-heavy);
}

.port {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.port-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--text-faint);
  border: 2px solid var(--text-muted);
  transition: all 0.2s;
}

.port:hover .port-dot {
  background: #409eff;
  border-color: #409eff;
  transform: scale(1.2);
}

.port.connecting .port-dot {
  background: #e6a23c;
  border-color: #e6a23c;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.3); }
}

.port-input .port-dot {
  background: #67c23a;
  border-color: #67c23a;
}

.port-output .port-dot {
  background: #409eff;
  border-color: #409eff;
}

.port-label {
  font-size: 10px;
  color: var(--text-muted);
}

.edges-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
}

.workflow-edge {
  pointer-events: stroke;
  cursor: pointer;
}

.workflow-edge:hover {
  stroke-width: 3;
}

.properties-panel {
  width: 300px;
  background: var(--border-color);
  border-left: 1px solid var(--border-strong);
  overflow-y: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--border-strong);
  border-bottom: 1px solid var(--border-heavy);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.panel-body {
  padding: 16px;
}

.panel-body :deep(.el-form-item) {
  margin-bottom: 12px;
}

.panel-body :deep(.el-form-item__label) {
  color: var(--text-muted);
  font-size: 12px;
}

.connecting-hint {
  text-align: center;
  padding: 32px 16px;
}

.connecting-hint p {
  margin: 0 0 8px 0;
  color: #e6a23c;
  font-size: 14px;
}

.connecting-hint .hint-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.node-preview {
  padding: 8px 0;
}

.preview-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.preview-type {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-strong);
}

.preview-config {
  margin-bottom: 8px;
}

.preview-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 12px;
}

.preview-key {
  color: var(--text-muted);
}

.preview-value {
  color: var(--text-primary);
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-ports {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-strong);
}

.preview-port {
  font-size: 11px;
  color: #67c23a;
  padding: 2px 0;
}
</style>
