import client from './client'

export interface WorkflowNode {
  id: string
  type: string
  label: string
  x: number
  y: number
  config: Record<string, any>
  inputs: string[]
  outputs: string[]
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  label?: string
  sourceHandle?: string
  targetHandle?: string
}

export interface Workflow {
  id: string
  name: string
  description: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  enabled: boolean
  created_at?: string
  updated_at?: string
  last_run_at?: string
  run_count: number
  tags: string[]
}

export interface WorkflowResult {
  success: boolean
  workflow_id: string
  result_count: number
  duration: number
  results: any[]
  execution_time: string
  error?: string
}

export interface WorkflowExecution {
  id: string
  workflow_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  current_node: string
  current_step: string
  steps: ExecutionStep[]
  result?: WorkflowResult
  error?: string
  started_at: string
  finished_at?: string
}

export interface ExecutionStep {
  node_id: string
  node_label: string
  step: string
  progress: number
  detail?: Record<string, any>
  timestamp: string
}

export interface RunResponse {
  success: boolean
  execution_id: string
  message?: string
  error?: string
}

export interface ProgressResponse {
  success: boolean
  data: WorkflowExecution
}

export interface NodeTypeConfig {
  type: string
  label: string
  description: string
  icon: string
  config_schema: Record<string, any>
}

export interface WorkflowTemplate {
  id: string
  name: string
  description: string
  tags: string[]
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
}

export const workflowApi = {
  list() {
    return client.get('/api/v1/workflow')
  },
  get(id: string) {
    return client.get(`/api/v1/workflow/${id}`)
  },
  create(data: Partial<Workflow>) {
    return client.post('/api/v1/workflow', data)
  },
  update(id: string, data: Partial<Workflow>) {
    return client.put(`/api/v1/workflow/${id}`, data)
  },
  delete(id: string) {
    return client.delete(`/api/v1/workflow/${id}`)
  },
  run(id: string, params?: Record<string, any>): Promise<{ data: RunResponse }> {
    return client.post(`/api/v1/workflow/${id}/run`, params || {})
  },
  getExecutionProgress(workflowId: string, executionId: string): Promise<{ data: ProgressResponse }> {
    return client.get(`/api/v1/workflow/${workflowId}/execution/${executionId}/progress`)
  },
  cancelExecution(workflowId: string, executionId: string) {
    return client.post(`/api/v1/workflow/${workflowId}/execution/${executionId}/cancel`)
  },
  listExecutions(workflowId: string, limit: number = 20) {
    return client.get(`/api/v1/workflow/${workflowId}/executions`, { params: { limit } })
  },
  getTemplates() {
    return client.get('/api/v1/workflow/templates')
  },
  getNodeTypes() {
    return client.get('/api/v1/workflow/node-types')
  }
}
