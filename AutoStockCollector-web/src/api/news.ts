import client from './client';
import type { NewsItem } from '@/types';

export interface NewsResponse {
  success: boolean;
  count: number;
  data: NewsItem[];
}

export interface NewsParams {
  code?: string;
  limit?: number;
}

export async function getNews(params?: NewsParams) {
  const response = await client.get<NewsResponse>('/news', params);
  return response.data;
}

export async function collectNews() {
  const response = await client.post<{ success: boolean; results: unknown[] }>('/collect/news');
  return response;
}