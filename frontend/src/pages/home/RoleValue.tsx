import { Check } from 'lucide-react'

import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { Tabs } from '@/components/ui/Tabs'
import { roleValueTabs } from '@/lib/content/home'

export function RoleValue() {
  return (
    <Section>
      <Container>
        <SectionHeading
          eyebrow="Built for your role"
          title="One platform, tuned to how each team works"
        />
        <div className="mt-14">
          <Tabs
            items={roleValueTabs.map((tab) => ({
              id: tab.id,
              label: tab.label,
              content: (
                <div className="mx-auto grid max-w-4xl items-center gap-10 lg:grid-cols-2">
                  <div>
                    <h3 className="font-serif text-2xl font-semibold text-brand-navy">
                      {tab.title}
                    </h3>
                    <ul className="mt-6 space-y-3">
                      {tab.bullets.map((bullet) => (
                        <li key={bullet} className="flex gap-3 text-sm text-slate-600">
                          <Check
                            className="mt-0.5 size-5 shrink-0 text-brand-teal"
                            aria-hidden="true"
                          />
                          {bullet}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div
                    className="flex aspect-[4/3] items-center justify-center rounded-2xl bg-gradient-to-br from-brand-navy to-brand-blue text-white"
                    aria-hidden="true"
                  >
                    <span className="font-serif text-5xl font-semibold opacity-40">
                      {tab.label}
                    </span>
                  </div>
                </div>
              ),
            }))}
          />
        </div>
      </Container>
    </Section>
  )
}
