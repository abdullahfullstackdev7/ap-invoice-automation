import { Globe, Mail, Rss } from 'lucide-react'
import { useId, useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { footerColumns } from '@/lib/content/nav'

export function Footer() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const newsletterId = useId()

  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-[1240px] px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-6">
          <div className="col-span-2">
            <Link to="/" className="flex items-center gap-2 text-lg font-semibold text-brand-navy">
              <span
                aria-hidden="true"
                className="flex size-8 items-center justify-center rounded-lg bg-brand-blue text-sm font-bold text-white"
              >
                V
              </span>
              Veridian Payables
            </Link>
            <p className="mt-4 max-w-xs text-sm text-slate-500">
              Every invoice matched, verified and paid with confidence.
            </p>
            <form
              className="mt-6"
              onSubmit={(event) => {
                event.preventDefault()
                setSubmitted(true)
              }}
            >
              <label
                htmlFor={newsletterId}
                className="mb-2 block text-sm font-medium text-brand-navy"
              >
                Get product updates
              </label>
              <div className="flex gap-2">
                <input
                  id={newsletterId}
                  type="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@company.com"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus-visible:border-brand-blue"
                />
                <Button type="submit" size="sm">
                  {submitted ? 'Thanks!' : 'Subscribe'}
                </Button>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                Front-end only in this sample deployment; nothing is sent anywhere.
              </p>
            </form>
          </div>

          {footerColumns.map((column) => (
            <div key={column.heading}>
              <p className="mb-3 text-sm font-semibold text-brand-navy">{column.heading}</p>
              <ul className="flex flex-col gap-2">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link to={link.href} className="text-sm text-slate-500 hover:text-brand-navy">
                      {link.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-slate-200 pt-8 sm:flex-row">
          <p className="text-xs text-slate-500">
            &copy; {new Date().getFullYear()} Veridian Payables. Sample product for demonstration;
            not a real company.
          </p>
          <div className="flex items-center gap-4 text-slate-400">
            <Link to="/resources" aria-label="Blog" className="hover:text-brand-navy">
              <Rss className="size-4" aria-hidden="true" />
            </Link>
            <Link to="/contact" aria-label="Contact" className="hover:text-brand-navy">
              <Mail className="size-4" aria-hidden="true" />
            </Link>
            <Link to="/" aria-label="Home" className="hover:text-brand-navy">
              <Globe className="size-4" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
