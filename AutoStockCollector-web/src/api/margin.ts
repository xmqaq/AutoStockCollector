import client from './client';
import type { MarginRecord } from '@/types';

interface MarginParams {
  start_date?: string;
  end_date?: string;
  code?: string;
  limit?: number;
}

export async function getMargin(params?: MarginParams) {
  return client.get<{ success: boolean; data: MarginRecord[]; count: number }>('/margin', { params });
}