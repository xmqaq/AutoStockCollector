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

export async function getNews(params?: NewsParams): Promise<NewsResponse | undefined> {
  const response = await client.get<NewsResponse>('/news', params);
  return response.data;
}