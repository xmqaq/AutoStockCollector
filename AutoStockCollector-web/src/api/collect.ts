import client from './client';
import type { CollectProgressResponse } from '@/types';

interface CollectHistoryBody {
  start_date: string;
  end_date: string;
  task_types?: string[];
}

export async function getProgressAll() {
  return client.get<CollectProgressResponse>('/collect/progress_all');
}

export async function collectHistory(body: CollectHistoryBody) {
  return client.post('/collect/history', body);
}

export async function clearDatabase(collections?: string[]) {
  return client.post('/db/clear', { collections });
}

export async function getHealth() {
  return client.get<{ status: string }>('/health');
}