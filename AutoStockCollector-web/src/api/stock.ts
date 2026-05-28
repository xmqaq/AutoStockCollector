import client from './client';
import type { StockInfo } from '@/types';

export async function getStockInfo(code: string) {
  return client.get<StockInfo>(`/stock/${code}/info`);
}

export async function getStockIndices(code: string) {
  return client.get(`/stock/${code}/indices`);
}