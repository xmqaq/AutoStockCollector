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
          <el-icon><Database /></el-icon> 数据获取
        </el-button>
        <el-button size="small" @click="addNode('technical_indicator')">
          <el-icon><TrendCharts /></el-icon> 技术指标
        </el-button>
      </div>
      <div class="toolbar-right">
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
      >
        <div
          v-for="node in nodes"
          :key="node.id"
          class="workflow-node"
          :class="[`node-type-${node.type}`, { selected: selectedNode?.id === node.id }]"
          :style="{ left: node.x + 'px', top: node.y + 'px' }"
          @click.stop="selectNode(node)"
          @mousedown="startDrag($event, node)"
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
              @click.stop="startConnect(node, input, 'input')"
            >
              <div class="port-dot"></div>
              <span class="port-label">{{ input }}</span>
            </div>
            <div
              v-for="output in node.outputs"
              :key="output"
              class="port port-output"
              @click.stop="startConnect(node, output, 'output')"
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

    <div v-if="selectedNode || connecting" class="properties-panel">
      <div class="panel-header">
        <span>{{ selectedNode ? '节点配置' : '连接中...' }}</span>
        <el-button
          v-if="selectedNode"
          type="danger"
          size="small"
          text
          @click="deleteSelectedNode"
        >
          <el-icon><Delete /></el-icon> 删除
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import {
  VideoPlay, Filter, Star, User, Collection, CircleCheck, CircleClose,
  Delete, VideoPause, Connection, Operation, Timer, TrendCharts,
  DataLine, Reading, ChatLineSquare, DataAnalysis, DataBoard
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

const nodeTypes = [
  { type: 'start', label: '起始节点', icon: 'play', description: '定义数据来源' },
  { type: 'filter', label: '筛选节点', icon: 'filter', description: '按条件过滤' },
  { type: 'score', label: '评分节点', icon: 'star', description: '多维度评分' },
  { type: 'ai_agent', label: 'AI节点', icon: 'robot', description: 'AI深度分析' },
  { type: 'combine', label: '组合节点', icon: 'collection', description: '结果组合' },
  { type: 'risk_control', label: '风控节点', icon: 'shield', description: '风险控制' },
  { type: 'end', label: '结束节点', icon: 'stop', description: '输出结果' },
  { type: 'data_fetch', label: '数据获取', icon: 'database', description: '获取多源数据' },
  { type: 'technical_indicator', label: '技术指标', icon: 'line-chart', description: '计算技术指标' },
  { type: 'fundamental_filter', label: '基本面筛选', icon: 'reading', description: '财务指标筛选' },
  { type: 'market_sentiment', label: '市场情绪', icon: 'chat', description: '市场情绪分析' },
  { type: 'index_components', label: '指数成分', icon: 'collection', description: '获取指数成分股' },
  { type: 'compare', label: '对比分析', icon: 'analysis', description: '多股对比分析' }
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
        { value: 'fund_flow', label: '资金流向' }
      ]
    },
    min_price: { type: 'number', label: '最低价' },
    max_price: { type: 'number', label: '最高价' },
    threshold: { type: 'number', label: '阈值' },
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
    }
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
    dataAnalysis: DataAnalysis
  }
  return icons[iconName] || Operation
}

function getNodeTypeLabel(type: string) {
  const node = nodeTypes.find(n => n.type === type)
  return node ? node.description : type
}

function getNodeConfigSchema(type: string) {
  return nodeConfigSchemas[type] || {}
}

function generateId() {
  return Math.random().toString(36).substr(2, 9)
}

function addNode(type: string) {
  const nodeType = nodeTypes.find(n => n.type === type)
  const newNode: WorkflowNode = {
    id: generateId(),
    type,
    label: nodeType?.label || type,
    x: 200 + nodes.value.length * 50,
    y: 200 + nodes.value.length * 30,
    config: getDefaultConfig(type),
    inputs: ['input'],
    outputs: ['output']
  }

  if (type === 'start') {
    newNode.inputs = []
  } else if (type === 'end') {
    newNode.outputs = []
  }

  nodes.value.push(newNode)
  selectedNode.value = newNode
}

function getDefaultConfig(type: string): Record<string, any> {
  const defaults: Record<string, any> = {
    start: { source: 'all' },
    filter: { filter_type: 'price_range', min_price: 0, max_price: 1000 },
    score: { score_type: 'weighted' },
    ai_agent: { agent_id: '', top_n: 20 },
    combine: { strategy: 'top_n', top_n: 20 },
    risk_control: { max_positions: 10, max_position_ratio: 0.1, exclude_st: true },
    end: { output: 'list', top_n: 10 }
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

function deleteSelectedNode() {
  if (!selectedNode.value) return

  nodes.value = nodes.value.filter(n => n.id !== selectedNode.value?.id)
  edges.value = edges.value.filter(
    e => e.source !== selectedNode.value?.id && e.target !== selectedNode.value?.id
  )
  selectedNode.value = null
}

function startConnect(node: WorkflowNode, port: string, type: 'input' | 'output') {
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
}

let draggingNode = ref<WorkflowNode | null>(null)
let dragStartX = 0
let dragStartY = 0
let nodeStartX = 0
let nodeStartY = 0

function startDrag(event: MouseEvent, node: WorkflowNode) {
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

  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  const nodeType = nodeTypes.find(n => n.type === draggedNodeType)
  const newNode: WorkflowNode = {
    id: generateId(),
    type: draggedNodeType,
    label: nodeType?.label || draggedNodeType,
    x,
    y,
    config: getDefaultConfig(draggedNodeType),
    inputs: draggedNodeType === 'start' ? [] : ['input'],
    outputs: draggedNodeType === 'end' ? [] : ['output']
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
</script>

<style scoped>
.workflow-canvas {
  display: flex;
  flex-direction: column;
  height: 80vh;
  background: #1f1f1f;
  border-radius: 8px;
}

.canvas-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #2c2c2c;
  border-bottom: 1px solid #3c3c3c;
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
  background: #2c2c2c;
  border-right: 1px solid #3c3c3c;
  padding: 16px;
  overflow-y: auto;
}

.palette-title {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 12px;
  text-transform: uppercase;
}

.palette-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 8px;
  background: #3c3c3c;
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
  background: #252525;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 20px 20px;
}

.workflow-node {
  position: absolute;
  width: 200px;
  background: #3c3c3c;
  border: 2px solid #4c4c4c;
  border-radius: 8px;
  cursor: move;
  user-select: none;
  transition: box-shadow 0.2s;
}

.workflow-node:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.workflow-node.selected {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.3);
}

.workflow-node.node-type-start {
  border-color: #67c23a;
}

.workflow-node.node-type-end {
  border-color: #f56c6c;
}

.workflow-node.node-type-ai_agent {
  border-color: #e6a23c;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #4c4c4c;
  border-radius: 6px 6px 0 0;
  font-size: 13px;
  font-weight: 600;
  color: #e5eaf3;
}

.node-body {
  padding: 10px 12px;
}

.node-type-label {
  font-size: 11px;
  color: #909399;
}

.node-ports {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  border-top: 1px solid #4c4c4c;
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
  background: #606266;
  border: 2px solid #909399;
  transition: all 0.2s;
}

.port:hover .port-dot {
  background: #409eff;
  border-color: #409eff;
  transform: scale(1.2);
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
  color: #909399;
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
  background: #2c2c2c;
  border-left: 1px solid #3c3c3c;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #3c3c3c;
  border-bottom: 1px solid #4c4c4c;
  font-size: 13px;
  font-weight: 600;
  color: #e5eaf3;
}

.panel-body {
  padding: 16px;
}

.panel-body :deep(.el-form-item) {
  margin-bottom: 12px;
}

.panel-body :deep(.el-form-item__label) {
  color: #909399;
  font-size: 12px;
}
</style>
