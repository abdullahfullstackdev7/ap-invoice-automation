import { PageHero } from '@/components/layout/PageHero'
import { Container } from '@/components/ui/Container'
import { Section } from '@/components/ui/Section'

export function PrivacyPage() {
  return (
    <>
      <PageHero
        eyebrow="Legal"
        title="Privacy policy"
        subtitle="Last updated: this is a sample document for demonstration."
      />
      <Section>
        <Container className="max-w-2xl space-y-8 text-sm leading-relaxed text-slate-700">
          <section>
            <h2 className="mb-2 text-base font-semibold text-brand-navy">What this document is</h2>
            <p>
              This is a sample privacy policy for Veridian Payables, a fictional product built to
              demonstrate an accounts-payable automation platform. It does not reflect a real
              company&apos;s data practices and should not be relied on as a legal document.
            </p>
          </section>
          <section>
            <h2 className="mb-2 text-base font-semibold text-brand-navy">
              Data this sample application stores
            </h2>
            <p>
              The demo deployment stores the documents, invoices and workflow records you create in
              it, account credentials (hashed, never in plain text), and an append-only audit log of
              actions taken. Contact-form submissions are stored so a response can be sent.
            </p>
          </section>
          <section>
            <h2 className="mb-2 text-base font-semibold text-brand-navy">How AI is used</h2>
            <p>
              Document text may be sent to a third-party language model when deterministic
              extraction fails. Only the specific failing region of text is sent, never the full
              document by default. See the Security page for the full policy.
            </p>
          </section>
          <section>
            <h2 className="mb-2 text-base font-semibold text-brand-navy">Contact</h2>
            <p>Questions about this sample deployment can be sent through the Contact page.</p>
          </section>
        </Container>
      </Section>
    </>
  )
}
