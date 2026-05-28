import client from './client';
import type { SectorItem } from '@/types';

export interface SectorResponse {
  success: boolean;
  data?: SectorItem[];
  error?: string;
}

export async function getSectorList() {
  const response = await client.get<{ data: SectorResponse }>('/sector');
  return response.data;
}

export async function getSectorStocks(sectorName: string) {
  const response = await client.get<{ data: SectorResponse }>(`/sector/${encodeURIComponent(sectorName)}/stocks`);
  return response.data;
}

export async function collectSector(params?: { codes?: string[] }) {
  const response = await client.post<SectorResponse>('/collect/sector', params);
  return response.data;
}