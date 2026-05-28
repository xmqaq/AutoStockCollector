import client from './client';
import type { DragonTigerRecord } from '@/types';

interface DragonTigerParams {
  start_date?: string;
  end_date?: string;
  code?: string;
  limit?: number;
}

export async function getDragonTiger(params?: DragonTigerParams) {
  return client.get<{ success: boolean; data: DragonTigerRecord[]; count: number }>('/dragon-tiger', { params });
}