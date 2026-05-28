import client from './client';
import type { SectorItem } from '@/types';

interface SectorStock {
  code: string;
  name: string;
  change_rate: number;
  net_flow: number;
}

export async function getSectorList() {
  return client.get<{ success: boolean; data: SectorItem[] }>('/sector/list');
}

export async function getSectorStocks(name: string) {
  return client.get<{ success: boolean; data: SectorStock[] }>(`/sector/${encodeURIComponent(name)}/stocks`);
}