import client from './client';
import type { FundFlowRecord } from '@/types';

export interface FundFlowResponse {
  success: boolean;
  data?: FundFlowRecord[];
  error?: string;
}

export async function getFundFlow(code: string) {
  const response = await client.get<FundFlowResponse>(`/fund-flow/${code}`);
  return response.data?.data || [];
}

export async function collectFundFlow(codes?: string[]) {
  const response = await client.post<{ success: boolean; results: FundFlowRecord[] }>('/collect/fund_flow', { codes });
  return response.data;
}