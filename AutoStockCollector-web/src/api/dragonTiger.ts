import client from './client';
import type { DragonTigerRecord } from '@/types';

export interface DragonTigerResponse {
  success: boolean;
  count?: number;
  data?: DragonTigerRecord[];
  error?: string;
}

export interface DragonTigerParams {
  start_date?: string;
  end_date?: string;
  code?: string;
  limit?: number;
}

export async function getDragonTiger(params?: DragonTigerParams) {
  const response = await client.get<DragonTigerResponse>('/dragon_tiger', params);
  return response.data;
}

export async function collectDragonTiger() {
  const response = await client.post<{ success: boolean }>('/collect/dragon_tiger');
  return response;
}