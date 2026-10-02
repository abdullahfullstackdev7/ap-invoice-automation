import { Check } from 'lucide-react'

import { PageHero } from '@/components/layout/PageHero'
import { Container } from '@/components/ui/Container'
import { Section } from '@/components/ui/Section'
import { roleValueTabs } from '@/lib/content/home'

export function SolutionsPage() {
  return (
    <>
      <PageHero
        eyebrow="Solutions"
        title="Solutions by role"
        subtitle="The same reconciliation engine, presented the way each team actually works."
      />
      {roleValueTabs.map((tab, index) => (
        <Section key={tab.id} id={tab.id} tone={index % 2 === 0 ? 'default' : 'muted'}>
          <Container className="grid items-center gap-10 lg:grid-cols-2">
            <div className={index % 2 === 1 ? 'lg:order-2' : undefined}>
              <p className="text-sm font-semibold tracking-wide text-brand-blue uppercase">
                {tab.label}
              </p>
              <h2 className="mt-3 font-serif text-2xl font-semibold text-brand-navy sm:text-3xl">
                {tab.title}
              </h2>
              <ul className="mt-6 space-y-3">
                {tab.bullets.map((bullet) => (
                  <li key={bullet} className="flex gap-3 text-sm text-slate-600">
                    <Check className="mt-0.5 size-5 shrink-0 text-brand-teal" aria-hidden="true" />
                    {bullet}
                  </li>
                ))}
              </ul>
            </div>
            <div
              className="flex aspect-[4/3] items-center justify-center rounded-2xl bg-gradient-to-br from-brand-navy to-brand-blue text-white"
              aria-hidden="true"
            >
              <span className="font-serif text-5xl font-semibold opacity-40">{tab.label}</span>
            </div>
          </Container>
        </Section>
      ))}
    </>
  )
}
