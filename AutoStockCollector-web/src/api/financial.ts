import client from './client';
import type { FinancialRecord } from '@/types';

export interface FinancialResponse {
  success: boolean;
  data?: FinancialRecord[];
  error?: string;
}

export interface FinancialParams {
  report_date?: string;
}

export async function getFinancial(code: string, params?: FinancialParams) {
  const response = await client.get<{ data: FinancialResponse }>(`/financial/${code}`, params);
  return response.data?.data?.data || [];
}

export async function collectFinancial(codes?: string[]) {
  const response = await client.post<{ success: boolean; results: unknown[] }>('/collect/financial', { codes });
  return response.data;
}