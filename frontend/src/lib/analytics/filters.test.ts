import { describe, expect, it } from 'vitest'

import {
  defaultFilters,
  filtersFromSearchParams,
  filtersToSearchParams,
  rangeForPreset,
  toApiParams,
} from '@/lib/analytics/filters'
import { formatCurrency, formatPercent } from '@/lib/format'

const TODAY = new Date('2026-10-05T12:00:00Z')

describe('analytics date presets', () => {
  it('computes a 30-day window ending today, inclusive', () => {
    expect(rangeForPreset('30d', TODAY)).toEqual({ from: '2026-09-06', to: '2026-10-05' })
  })

  it('computes year-to-date from January 1st', () => {
    expect(rangeForPreset('ytd', TODAY).from).toBe('2026-01-01')
  })

  it('computes trailing 24 months starting the day after two years ago', () => {
    expect(rangeForPreset('24m', TODAY)).toEqual({ from: '2024-10-06', to: '2026-10-05' })
  })
})

describe('analytics filter URL round trip', () => {
  it('serializes vendor, category and comparison and reads them back', () => {
    const state = {
      ...defaultFilters(TODAY),
      vendorId: '11111111-1111-1111-1111-111111111111',
      category: 'Office',
      compare: true,
    }
    const restored = filtersFromSearchParams(filtersToSearchParams(state), TODAY)
    expect(restored.vendorId).toBe(state.vendorId)
    expect(restored.category).toBe('Office')
    expect(restored.compare).toBe(true)
  })

  it('uses explicit dates for a custom range', () => {
    const params = new URLSearchParams('preset=custom&from=2026-03-01&to=2026-03-31')
    const restored = filtersFromSearchParams(params, TODAY)
    expect(restored.from).toBe('2026-03-01')
    expect(restored.to).toBe('2026-03-31')
  })

  it('builds API query params with the same date window and filters', () => {
    const state = { ...defaultFilters(TODAY), vendorId: 'v1', category: null }
    const api = toApiParams(state)
    expect(api.date_from).toBe(state.from)
    expect(api.date_to).toBe(state.to)
    expect(api.vendor_id).toBe('v1')
    expect(api.category).toBeUndefined()
  })
})

describe('formatting', () => {
  it('formats currency without cents and handles null', () => {
    expect(formatCurrency(1234.56)).toBe('$1,235')
    expect(formatCurrency(null)).toBe('-')
  })

  it('formats percentages to one decimal place', () => {
    expect(formatPercent(12.345)).toBe('12.3%')
    expect(formatPercent(null)).toBe('-')
  })
})
