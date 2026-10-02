import { PageHero } from '@/components/layout/PageHero'
import { Container } from '@/components/ui/Container'
import { Section } from '@/components/ui/Section'

const cookies = [
  {
    name: 'access_token',
    purpose: 'Short-lived session credential (15 minutes).',
    type: 'Strictly necessary',
  },
  {
    name: 'refresh_token',
    purpose: 'Rotating credential used to renew a session (7 days).',
    type: 'Strictly necessary',
  },
  {
    name: 'csrf_token',
    purpose: 'Double-submit CSRF protection for state-changing requests.',
    type: 'Strictly necessary',
  },
]

export function CookieNoticePage() {
  return (
    <>
      <PageHero eyebrow="Legal" title="Cookie notice" />
      <Section>
        <Container className="max-w-2xl text-sm leading-relaxed text-slate-700">
          <p>
            This application uses a small number of strictly necessary cookies to keep you signed in
            and to protect against cross-site request forgery. It does not use advertising or
            third-party tracking cookies.
          </p>
          <table className="mt-8 w-full border-collapse overflow-hidden rounded-xl border border-slate-200 text-left text-xs">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">
                  Cookie
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Purpose
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Type
                </th>
              </tr>
            </thead>
            <tbody>
              {cookies.map((cookie) => (
                <tr key={cookie.name} className="border-t border-slate-100">
                  <td className="px-4 py-3 font-mono text-[11px] text-brand-navy">{cookie.name}</td>
                  <td className="px-4 py-3 text-slate-600">{cookie.purpose}</td>
                  <td className="px-4 py-3 text-slate-600">{cookie.type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Container>
      </Section>
    </>
  )
}
