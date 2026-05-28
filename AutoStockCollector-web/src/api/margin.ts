import client from './client';
import type { MarginRecord } from '@/types';

export interface MarginResponse {
  success: boolean;
  count?: number;
  data?: MarginRecord[];
  error?: string;
}

export interface MarginParams {
  start_date?: string;
  end_date?: string;
  code?: string;
  limit?: number;
}

export async function getMargin(params?: MarginParams) {
  const response = await client.get<{ data: MarginResponse }>('/margin', params);
  return response.data;
}

export async function collectMargin(params?: { start_date?: string; end_date?: string }) {
  const response = await client.post<MarginResponse>('/collect/margin', params);
  return response.data;
}