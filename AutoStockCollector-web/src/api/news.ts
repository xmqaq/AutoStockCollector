import client from './client';
import type { NewsItem } from '@/types';

interface NewsParams {
  code?: string;
  limit?: number;
}

export async function getNews(params?: NewsParams) {
  return client.get<{ success: boolean; data: NewsItem[]; count: number }>('/news', { params });
}