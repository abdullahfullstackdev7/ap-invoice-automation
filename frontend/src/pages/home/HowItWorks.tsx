import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { howItWorksSteps } from '@/lib/content/home'

export function HowItWorks() {
  return (
    <Section tone="muted">
      <Container>
        <SectionHeading eyebrow="How it works" title="From inbox to paid, in four steps" />
        <div className="relative mt-16 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div
            className="absolute top-6 right-0 left-0 hidden h-px bg-slate-200 lg:block"
            aria-hidden="true"
          />
          {howItWorksSteps.map((step) => (
            <div key={step.step} className="relative text-center">
              <div className="relative z-10 mx-auto flex size-12 items-center justify-center rounded-full bg-brand-blue font-serif text-lg font-semibold text-white">
                {step.step}
              </div>
              <h3 className="mt-4 text-base font-semibold text-brand-navy">{step.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{step.description}</p>
            </div>
          ))}
        </div>
      </Container>
    </Section>
  )
}
