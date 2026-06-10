import client from './client'

export interface TodoItem {
  id: string
  text: string
  category: 'todo' | 'plan' | 'suggestion'
  done: boolean
  submitterIp?: string
  createdAt: string
  updatedAt: string
}

export interface TodoListParams {
  page?: number
  pageSize?: number
  category?: 'todo' | 'plan' | 'suggestion' | 'all'
}

export interface TodoListResult {
  success: boolean
  data: TodoItem[]
  pagination: { page: number; pageSize: number; total: number }
  stats: { total: number; done: number; pending: number }
}

export const todoApi = {
  list(params?: TodoListParams) {
    return client.get<TodoListResult>('/api/v1/todo', { params })
  },
  create(data: { text: string; category: string }) {
    return client.post<{ success: boolean; data: TodoItem }>('/api/v1/todo', data)
  },
  update(id: string, data: Partial<Pick<TodoItem, 'text' | 'category' | 'done'>>) {
    return client.put<{ success: boolean; data: TodoItem }>(`/api/v1/todo/${id}`, data)
  },
  remove(id: string) {
    return client.delete<{ success: boolean; deleted: string }>(`/api/v1/todo/${id}`)
  },
}
