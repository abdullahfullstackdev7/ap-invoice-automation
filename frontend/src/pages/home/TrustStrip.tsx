import { Container } from '@/components/ui/Container'

const wordmarks = ['Northfield', 'Harborview', 'Caldwell', 'Union Ridge', 'Meridian', 'Stonegate']

export function TrustStrip() {
  return (
    <div className="border-y border-slate-200 bg-slate-50 py-10">
      <Container>
        <p className="text-center text-sm text-slate-500">
          Built for finance teams that process thousands of invoices a month
        </p>
        <ul
          className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-4"
          aria-label="Illustrative customer wordmarks"
        >
          {wordmarks.map((name) => (
            <li
              key={name}
              className="text-lg font-semibold tracking-wide text-slate-600 select-none"
            >
              {name}
            </li>
          ))}
        </ul>
        <p className="mt-4 text-center text-xs text-slate-500">
          Illustrative wordmarks, not real customer logos.
        </p>
      </Container>
    </div>
  )
}
