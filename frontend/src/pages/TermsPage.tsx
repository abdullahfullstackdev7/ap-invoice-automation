import { PageHero } from '@/components/layout/PageHero'
import { Container } from '@/components/ui/Container'
import { Section } from '@/components/ui/Section'

export function TermsPage() {
  return (
    <>
      <PageHero
        eyebrow="Legal"
        title="Terms of use"
        subtitle="Last updated: this is a sample document for demonstration."
      />
      <Section>
        <Container className="max-w-2xl space-y-8 text-sm leading-relaxed text-slate-700">
          <section>
            <h2 className="mb-2 text-base font-semibold text-brand-navy">Sample product</h2>
            <p>
              Veridian Payables is a fictional product built to demonstrate an accounts-payable
              automation platform. This sample deployment is provided for demonstration purposes
              only, without warranty of any kind, and is not a commercial offering.
            </p>
          </section>
          <section>
            <h2 className="mb-2 text-base font-semibold text-brand-navy">Acceptable use</h2>
            <p>
              The demo deployment is intended for evaluation only. Do not upload real invoices, real
              personal data, or any information you would not want stored in a sample environment.
            </p>
          </section>
          <section>
            <h2 className="mb-2 text-base font-semibold text-brand-navy">
              No certifications claimed
            </h2>
            <p>
              This site describes the security controls implemented in the application. It does not
              claim SOC 2, ISO 27001, or any other third-party certification.
            </p>
          </section>
        </Container>
      </Section>
    </>
  )
}
