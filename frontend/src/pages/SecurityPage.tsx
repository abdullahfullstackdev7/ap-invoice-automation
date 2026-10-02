import { PageHero } from '@/components/layout/PageHero'
import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { securityTiles } from '@/lib/content/home'

const dataHandlingPoints = [
  'About 70% of invoices are processed by deterministic rules alone and never reach a language model.',
  'When a language model is used, only the specific region of text that failed deterministic parsing is sent - never the full document by default.',
  'The model has no tools and cannot take actions; its output is validated against a strict schema, and anything that does not match is discarded.',
  'Matching, approval routing and payment scheduling are deterministic code, not model output - the kind of decision that moves money is never left to inference.',
]

export function SecurityPage() {
  return (
    <>
      <PageHero
        eyebrow="Security"
        title="Controls, described plainly"
        subtitle="This page describes the controls this platform implements. It does not claim any third-party certification."
      />
      <Section>
        <Container>
          <SectionHeading align="left" title="Access and data protection" />
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {securityTiles.map((tile) => (
              <div key={tile.title} className="rounded-xl border border-slate-200 p-6">
                <tile.icon className="size-7 text-brand-navy" aria-hidden="true" />
                <h3 className="mt-3 text-base font-semibold text-brand-navy">{tile.title}</h3>
                <p className="mt-2 text-sm text-slate-600">{tile.description}</p>
              </div>
            ))}
          </div>
        </Container>
      </Section>
      <Section tone="muted">
        <Container className="max-w-2xl">
          <SectionHeading align="left" title="How AI is used, and how data is handled" />
          <ul className="mt-8 space-y-4">
            {dataHandlingPoints.map((point) => (
              <li
                key={point}
                className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-700"
              >
                {point}
              </li>
            ))}
          </ul>
        </Container>
      </Section>
    </>
  )
}
