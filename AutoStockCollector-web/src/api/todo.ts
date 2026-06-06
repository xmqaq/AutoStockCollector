import client from './client'

export interface TodoItem {
  id: string
  text: string
  category: 'todo' | 'plan' | 'suggestion'
  done: boolean
  createdAt: string
  updatedAt: string
}

export const todoApi = {
  list() {
    return client.get('/api/v1/todo')
  },
  create(data: { text: string; category: string }) {
    return client.post('/api/v1/todo', data)
  },
  update(id: string, data: Partial<Pick<TodoItem, 'text' | 'category' | 'done'>>) {
    return client.put(`/api/v1/todo/${id}`, data)
  },
  remove(id: string) {
    return client.delete(`/api/v1/todo/${id}`)
  },
}
