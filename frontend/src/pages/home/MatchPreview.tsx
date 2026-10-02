import { AlertTriangle } from 'lucide-react'
import { useState } from 'react'

import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { cn } from '@/lib/utils'

interface MatchScenario {
  id: string
  label: string
  reasonCode: string
  invoice: { qty: string; price: string; total: string; highlight?: 'qty' | 'price' | 'total' }
  po: { qty: string; price: string; total: string }
  receipt: { qty: string; note: string }
  explanation: string
}

const scenarios: MatchScenario[] = [
  {
    id: 'price-drift',
    label: 'Price drift',
    reasonCode: 'PRICE_VARIANCE',
    invoice: { qty: '100', price: '$12.50', total: '$1,250.00', highlight: 'price' },
    po: { qty: '100', price: '$10.00', total: '$1,000.00' },
    receipt: { qty: '100', note: 'Received in full' },
    explanation:
      'Invoiced unit price is 25% above the purchase order price, above the 5% tolerance.',
  },
  {
    id: 'short-receipt',
    label: 'Short receipt',
    reasonCode: 'QTY_NOT_RECEIVED',
    invoice: { qty: '100', price: '$10.00', total: '$1,000.00', highlight: 'qty' },
    po: { qty: '100', price: '$10.00', total: '$1,000.00' },
    receipt: { qty: '60', note: 'Partially received' },
    explanation:
      'Invoice bills for 100 units, but only 60 have been received against the PO so far.',
  },
  {
    id: 'duplicate',
    label: 'Duplicate',
    reasonCode: 'DUPLICATE_EXACT',
    invoice: { qty: '40', price: '$22.00', total: '$880.00', highlight: 'total' },
    po: { qty: '40', price: '$22.00', total: '$880.00' },
    receipt: { qty: '40', note: 'Received in full' },
    explanation: 'Same vendor and invoice number already paid last week. Blocked before release.',
  },
]

export function MatchPreview() {
  const [activeId, setActiveId] = useState(scenarios[0]?.id)
  const scenario = scenarios.find((s) => s.id === activeId) ?? scenarios[0]!

  return (
    <Section>
      <Container>
        <SectionHeading
          eyebrow="See it in action"
          title="Variances are surfaced the moment they happen"
          subtitle="A static preview of the 3-way match. Toggle a scenario to see what gets flagged."
        />

        <div className="mt-10 flex justify-center gap-2" role="tablist" aria-label="Match scenario">
          {scenarios.map((s) => (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={s.id === scenario.id}
              onClick={() => setActiveId(s.id)}
              className={cn(
                'rounded-full px-4 py-2 text-sm font-medium transition-colors',
                s.id === scenario.id
                  ? 'bg-brand-navy text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
              )}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          <MatchColumn
            title="Invoice"
            rows={[
              ['Qty', scenario.invoice.qty, scenario.invoice.highlight === 'qty'],
              ['Unit price', scenario.invoice.price, scenario.invoice.highlight === 'price'],
              ['Total', scenario.invoice.total, scenario.invoice.highlight === 'total'],
            ]}
          />
          <MatchColumn
            title="Purchase order"
            rows={[
              ['Qty', scenario.po.qty, false],
              ['Unit price', scenario.po.price, false],
              ['Total', scenario.po.total, false],
            ]}
          />
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
            <p className="text-sm font-semibold text-brand-navy">Goods receipt</p>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">Qty received</dt>
                <dd className="font-medium text-slate-700">{scenario.receipt.qty}</dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-slate-500">{scenario.receipt.note}</p>
          </div>
        </div>

        <div className="mx-auto mt-6 flex max-w-2xl items-start gap-3 rounded-xl border border-(--color-warning-bg) bg-(--color-warning-bg) p-4">
          <AlertTriangle
            className="mt-0.5 size-5 shrink-0 text-(--color-warning)"
            aria-hidden="true"
          />
          <div>
            <p className="text-sm font-semibold text-(--color-warning)">{scenario.reasonCode}</p>
            <p className="mt-1 text-sm text-slate-700">{scenario.explanation}</p>
          </div>
        </div>
      </Container>
    </Section>
  )
}

function MatchColumn({ title, rows }: { title: string; rows: [string, string, boolean][] }) {
  return (
    <div className="rounded-xl border border-slate-200 p-5">
      <p className="text-sm font-semibold text-brand-navy">{title}</p>
      <dl className="mt-4 space-y-2 text-sm">
        {rows.map(([label, value, highlighted]) => (
          <div key={label} className="flex justify-between">
            <dt className="text-slate-500">{label}</dt>
            <dd
              className={cn(
                'font-medium',
                highlighted ? 'text-(--color-danger)' : 'text-slate-700',
              )}
            >
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
