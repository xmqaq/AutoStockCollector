import client from './client';
import type { KlineRecord } from '@/types';

export interface KlineParams {
  start_date?: string;
  end_date?: string;
}

export interface KlineResponse {
  success: boolean;
  code: string;
  count: number;
  data: KlineRecord[];
}

export async function getKline(code: string, params?: KlineParams): Promise<KlineRecord[]> {
  const response = await client.get<KlineResponse>(`/kline/${code}`, params);
  return response.data?.data || [];
}

export async function getLatestKline(code: string) {
  const response = await client.get<{ success: boolean; data: KlineRecord }>(`/kline/${code}/latest`);
  return response.data?.data;
}

export async function collectKline(codes: string[], start_date?: string, end_date?: string, adjust = 'qfq') {
  const response = await client.post<{ success: boolean; code_count: number; collected_count: number }>('/collect/kline', {
    codes,
    start_date,
    end_date,
    adjust,
  });
  return response.data;
}

export async function collectIncremental(codes?: string[]) {
  const response = await client.post<{ success: boolean; results: unknown[] }>('/collect/incremental', { codes });
  return response.data;
}