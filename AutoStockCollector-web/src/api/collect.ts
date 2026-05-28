import client from './client';

export interface TaskProgress {
  task_id: string;
  task_type: string;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  total: number;
  success: number;
  failed: number;
  error_message?: string;
  create_time?: string;
  message?: string;
}

export interface ProgressResponse {
  success: boolean;
  data?: {
    all_done?: boolean;
    tasks?: TaskProgress[];
  };
}

export async function getProgressAll() {
  const response = await client.get<ProgressResponse>('/collect/progress_all');
  return response.data;
}

export async function collectHistory(params: { start_date: string; end_date: string; task_types?: string[] }) {
  const response = await client.post<{ success: boolean; message?: string }>('/collect/history', params);
  return response.data;
}

export async function clearDatabase(collections?: string[]) {
  const response = await client.post<{ success: boolean; message?: string }>('/db/clear', { collections });
  return response.data;
}

export async function healthCheck() {
  const response = await client.get<{ status: string; timestamp: string }>('/health');
  return response;
}

export async function getTasks(status?: string, limit = 100) {
  const params: Record<string, string> = { limit: String(limit) };
  if (status) params.status = status;
  const response = await client.get<{ success: boolean; tasks: TaskProgress[] }>('/tasks', params);
  return response.tasks || [];
}

export async function getTask(taskId: string) {
  const response = await client.get<{ success: boolean; [key: string]: unknown }>(`/task/${taskId}`);
  return response;
}

export async function startTask(taskId: string) {
  const response = await client.post<{ success: boolean; message: string }>(`/task/${taskId}/start`);
  return response;
}

export async function cancelTask(taskId: string) {
  const response = await client.post<{ success: boolean; message: string }>(`/task/${taskId}/cancel`);
  return response;
}

export async function retryTask(taskId: string) {
  const response = await client.post<{ success: boolean; message: string }>(`/task/${taskId}/retry`);
  return response;
}

export async function getSchedulerStats() {
  const response = await client.get<{ success: boolean; stats: { running_tasks: number; pending_tasks: number; thread_pool_size: number; timestamp: string } }>('/scheduler/stats');
  return response.stats;
}