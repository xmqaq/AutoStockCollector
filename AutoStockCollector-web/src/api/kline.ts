import client from './client';
import type { KlineRecord } from '@/types';

interface KlineParams {
  start_date?: string;
  end_date?: string;
}

export async function getKline(code: string, params?: KlineParams) {
  return client.get<KlineRecord[]>(`/kline/${code}`, { params });
}

export async function getLatestKline(code: string) {
  return client.get<KlineRecord>(`/kline/${code}/latest`);
}