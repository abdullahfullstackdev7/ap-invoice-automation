import { ArrowRight, Play } from 'lucide-react'
import { useState } from 'react'

import { Container } from '@/components/ui/Container'
import { LinkButton } from '@/components/ui/LinkButton'
import { DashboardMockup } from '@/pages/home/DashboardMockup'
import { TourModal } from '@/pages/home/TourModal'

export function Hero() {
  const [tourOpen, setTourOpen] = useState(false)

  return (
    <div className="relative overflow-hidden bg-gradient-to-b from-slate-50 to-white">
      <Container className="grid items-center gap-12 py-16 sm:py-20 lg:grid-cols-2 lg:py-28">
        <div>
          <h1 className="font-serif text-4xl font-semibold text-brand-navy sm:text-5xl lg:text-[56px] lg:leading-[1.05]">
            Every invoice matched, verified and paid with confidence
          </h1>
          <p className="mt-6 max-w-xl text-lg text-slate-600">
            Veridian Payables reconciles every invoice against the purchase order and goods receipt
            automatically, routes the real exceptions to the right person, and pays on time - or
            early, when the discount is worth it.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <LinkButton to="/login" size="lg">
              Log in to the platform
              <ArrowRight className="size-4" aria-hidden="true" />
            </LinkButton>
            <button
              type="button"
              onClick={() => setTourOpen(true)}
              className="inline-flex items-center gap-2 text-sm font-medium text-brand-navy hover:text-brand-blue"
            >
              <span className="flex size-10 items-center justify-center rounded-full border border-slate-300">
                <Play className="size-4" aria-hidden="true" />
              </span>
              Watch the product tour
            </button>
          </div>
        </div>
        <div className="relative">
          <DashboardMockup />
        </div>
      </Container>
      <TourModal open={tourOpen} onClose={() => setTourOpen(false)} />
    </div>
  )
}
