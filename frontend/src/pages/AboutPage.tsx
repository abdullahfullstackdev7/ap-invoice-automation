import { PageHero } from '@/components/layout/PageHero'
import { Badge } from '@/components/ui/Badge'
import { Container } from '@/components/ui/Container'
import { Section } from '@/components/ui/Section'

export function AboutPage() {
  return (
    <>
      <PageHero eyebrow="About" title="A sample product, built to show the real thing" />
      <Section>
        <Container className="max-w-2xl">
          <Badge tone="warning" className="mb-6">
            Sample product for demonstration
          </Badge>
          <p className="text-base leading-relaxed text-slate-700">
            Veridian Payables is a fictional company and product, built to demonstrate a complete
            accounts-payable automation platform end to end: document intake and OCR, extraction,
            3-way matching, exception handling, approval routing, payment scheduling and analytics -
            not a marketing page describing features that do not exist behind it.
          </p>
          <p className="mt-5 text-base leading-relaxed text-slate-700">
            Every control and number described on this site reflects something actually built and
            tested in the underlying application: the extraction accuracy figures come from
            evaluation runs, the audit trail is a real hash-chained log, and the segregation-of-
            duties rules are enforced in the API, not just described here.
          </p>
          <p className="mt-5 text-base leading-relaxed text-slate-700">
            Customer names and quotes on this site are illustrative scenarios, clearly labeled as
            such, and no real company logos are used anywhere.
          </p>
        </Container>
      </Section>
    </>
  )
}
