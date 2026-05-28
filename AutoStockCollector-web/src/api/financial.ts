import client from './client';
import type { FinancialRecord } from '@/types';

export async function getFinancial(code: string, report_date?: string) {
  return client.get<FinancialRecord[]>(`/financial/${code}`, {
    params: { report_date },
  });
}