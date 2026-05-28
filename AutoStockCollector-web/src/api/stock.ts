import client from './client';
import type { StockInfo } from '@/types';

export interface StockInfoResponse {
  success: boolean;
  data?: StockInfo;
  error?: string;
}

export async function getStockInfo(code: string) {
  const response = await client.get<StockInfoResponse>(`/stock/${code}/info`);
  return response.data;
}

export async function getStockIndices(code: string) {
  const response = await client.get(`/stock/${code}/indices`);
  return response.data;
}