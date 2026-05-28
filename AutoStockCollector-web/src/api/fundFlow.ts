import client from './client';
import type { FundFlowRecord } from '@/types';

export async function getFundFlow(code: string) {
  return client.get<FundFlowRecord[]>(`/fund-flow/${code}`);
}