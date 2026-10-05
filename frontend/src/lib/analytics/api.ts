import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '@/lib/api-client'

export type Params = Record<string, string | number | undefined>

function withQuery(path: string, params: Params): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

export function useAnalytics<T>(path: string, params: Params, enabled = true) {
  return useQuery({
    queryKey: ['analytics', path, params],
    queryFn: () => apiRequest<T>(withQuery(`/analytics/${path}`, params)),
    enabled,
    placeholderData: (previous) => previous,
  })
}

export interface KpiComparison {
  current: number | string | null
  previous: number | string | null
  pct_change: number | null
}

export interface KpisResponse {
  total_invoices: KpiComparison
  total_value: KpiComparison
  stp_rate: KpiComparison
  exception_rate: KpiComparison
  avg_cycle_time_hours: KpiComparison
  discounts_captured: KpiComparison
  discounts_missed: KpiComparison
}

export interface VolumeValuePoint {
  period: string
  invoices_count: number
  value: string
}

export interface SpendByVendorResponse {
  items: { vendor_id: string | null; vendor_name: string; invoices_count: number; value: string }[]
  total: number
}

export interface SpendByCategoryResponse {
  items: { category: string; invoices_count: number; value: string }[]
  total: number
}

export interface SavingsTrendPoint {
  period: string
  invoice_value: string
  savings_prevented: string
  discounts_captured: string
  discounts_missed: string
}

export interface ExceptionsByReasonItem {
  reason_code: string
  count: number
  pct: number
}

export interface ExceptionsTrendPoint {
  period: string
  count: number
}

export interface CycleTimeResponse {
  distribution: Record<string, number>
  p50_hours: number | null
  p95_hours: number | null
  trend: { period: string; avg_hours: number }[]
  sample_size: number
}

export interface SlaComplianceResponse {
  resolved_count: number
  sla_met_count: number
  sla_compliance_pct: number | null
  overdue_open_count: number
}

export interface HeatmapTimeCell {
  weekday: number
  hour: number
  count: number
}

export interface WorkflowFunnelItem {
  status: string
  count: number
}

export interface VendorScorecard {
  vendor_id: string
  vendor_name: string
  invoices_count: number
  value: string
  exception_count: number
  exception_rate: number | null
  stp_rate: number | null
}

export interface VendorScorecardsResponse {
  items: VendorScorecard[]
  total: number
}

export interface AgingBucket {
  bucket: string
  count: number
  value: string
}

export interface CashflowWeek {
  week_starting: string
  amount: string
}

export interface LlmUsageResponse {
  by_provider: Record<
    string,
    { calls: number; tokens_in: number; tokens_out: number; avg_latency_ms: number }
  >
  total_calls: number
  calls_avoided_by_rules: number
  rules_only_rate: number | null
}

export interface LlmUsageDailyPoint {
  day: string
  provider: string
  calls: number
  tokens_in: number
  tokens_out: number
}

export interface ExtractionAccuracyResponse {
  extraction: { overall?: Record<string, { precision: number; recall: number; f1: number }> } | null
  matching: { overall?: { precision: number; recall: number } } | null
  note: string
}
