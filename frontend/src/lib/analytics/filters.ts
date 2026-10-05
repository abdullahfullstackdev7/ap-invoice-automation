export type DatePreset = '30d' | '90d' | 'ytd' | '12m' | '24m' | 'custom'

export interface AnalyticsFilterState {
  preset: DatePreset
  from: string
  to: string
  vendorId: string | null
  category: string | null
  compare: boolean
}

export const PRESET_LABELS: Record<DatePreset, string> = {
  '30d': 'Last 30 days',
  '90d': 'Last 90 days',
  ytd: 'Year to date',
  '12m': 'Last 12 months',
  '24m': 'Last 24 months',
  custom: 'Custom',
}

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10)
}

export function rangeForPreset(
  preset: DatePreset,
  today: Date = new Date(),
): { from: string; to: string } {
  const to = new Date(today)
  const from = new Date(today)
  switch (preset) {
    case '30d':
      from.setDate(from.getDate() - 29)
      break
    case '90d':
      from.setDate(from.getDate() - 89)
      break
    case 'ytd':
      from.setMonth(0, 1)
      break
    case '12m':
      from.setFullYear(from.getFullYear() - 1)
      from.setDate(from.getDate() + 1)
      break
    case '24m':
      from.setFullYear(from.getFullYear() - 2)
      from.setDate(from.getDate() + 1)
      break
    case 'custom':
      break
  }
  return { from: isoDate(from), to: isoDate(to) }
}

export function defaultFilters(today: Date = new Date()): AnalyticsFilterState {
  const range = rangeForPreset('12m', today)
  return {
    preset: '12m',
    from: range.from,
    to: range.to,
    vendorId: null,
    category: null,
    compare: false,
  }
}

export function filtersToSearchParams(state: AnalyticsFilterState): URLSearchParams {
  const params = new URLSearchParams()
  params.set('preset', state.preset)
  params.set('from', state.from)
  params.set('to', state.to)
  if (state.vendorId) params.set('vendor', state.vendorId)
  if (state.category) params.set('category', state.category)
  if (state.compare) params.set('compare', '1')
  return params
}

export function filtersFromSearchParams(
  params: URLSearchParams,
  today: Date = new Date(),
): AnalyticsFilterState {
  const base = defaultFilters(today)
  const preset = (params.get('preset') as DatePreset | null) ?? base.preset
  const range =
    preset === 'custom'
      ? { from: params.get('from') ?? base.from, to: params.get('to') ?? base.to }
      : rangeForPreset(preset, today)
  return {
    preset,
    from: range.from,
    to: range.to,
    vendorId: params.get('vendor'),
    category: params.get('category'),
    compare: params.get('compare') === '1',
  }
}

export function toApiParams(state: AnalyticsFilterState): Record<string, string> {
  const params: Record<string, string> = { date_from: state.from, date_to: state.to }
  if (state.vendorId) params.vendor_id = state.vendorId
  if (state.category) params.category = state.category
  return params
}
