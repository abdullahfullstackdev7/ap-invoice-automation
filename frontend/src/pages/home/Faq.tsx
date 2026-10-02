import { Accordion } from '@/components/ui/Accordion'
import { Container } from '@/components/ui/Container'
import { Section, SectionHeading } from '@/components/ui/Section'
import { faqItems } from '@/lib/content/home'

export function Faq() {
  return (
    <Section tone="muted">
      <Container className="max-w-3xl">
        <SectionHeading eyebrow="FAQ" title="Common questions" />
        <div className="mt-12">
          <Accordion items={faqItems} />
        </div>
      </Container>
    </Section>
  )
}
