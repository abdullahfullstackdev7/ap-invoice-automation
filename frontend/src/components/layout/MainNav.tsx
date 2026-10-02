import { ChevronDown, Menu, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'

import { LinkButton } from '@/components/ui/LinkButton'
import { companyMenuItems, platformMenuItems, solutionsMenuItems } from '@/lib/content/nav'
import { cn } from '@/lib/utils'

type MenuKey = 'platform' | 'solutions' | 'company'

function useCloseOnEscape(onClose: () => void) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])
}

function DesktopDropdown({
  label,
  menuKey,
  openMenu,
  setOpenMenu,
  children,
}: {
  label: string
  menuKey: MenuKey
  openMenu: MenuKey | null
  setOpenMenu: (key: MenuKey | null) => void
  children: React.ReactNode
}) {
  const isOpen = openMenu === menuKey
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpenMenu(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen, setOpenMenu])

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-expanded={isOpen}
        aria-haspopup="true"
        onClick={() => setOpenMenu(isOpen ? null : menuKey)}
        className="flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:text-brand-navy"
      >
        {label}
        <ChevronDown
          className={cn('size-4 transition-transform', isOpen && 'rotate-180')}
          aria-hidden="true"
        />
      </button>
      {isOpen ? (
        <div className="absolute top-full left-1/2 z-40 mt-2 w-screen max-w-xl -translate-x-1/3 rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
          {children}
        </div>
      ) : null}
    </div>
  )
}

export function MainNav() {
  const [openMenu, setOpenMenu] = useState<MenuKey | null>(null)
  const [mobileOpen, setMobileOpen] = useState(false)

  useCloseOnEscape(() => {
    setOpenMenu(null)
    setMobileOpen(false)
  })

  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [mobileOpen])

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-[1240px] items-center justify-between px-4 py-3 sm:px-6 lg:px-8"
      >
        <Link to="/" className="flex items-center gap-2 text-lg font-semibold text-brand-navy">
          <span
            aria-hidden="true"
            className="flex size-8 items-center justify-center rounded-lg bg-brand-blue text-sm font-bold text-white"
          >
            V
          </span>
          Veridian Payables
        </Link>

        <div className="hidden items-center gap-1 lg:flex">
          <DesktopDropdown
            label="Platform"
            menuKey="platform"
            openMenu={openMenu}
            setOpenMenu={setOpenMenu}
          >
            <ul className="grid grid-cols-2 gap-1">
              {platformMenuItems.map((item) => (
                <li key={item.href}>
                  <Link
                    to={item.href}
                    onClick={() => setOpenMenu(null)}
                    className="flex gap-3 rounded-lg p-3 hover:bg-slate-50"
                  >
                    <item.icon
                      className="mt-0.5 size-5 shrink-0 text-brand-blue"
                      aria-hidden="true"
                    />
                    <span>
                      <span className="block text-sm font-semibold text-brand-navy">
                        {item.title}
                      </span>
                      <span className="block text-xs text-slate-500">{item.description}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </DesktopDropdown>

          <DesktopDropdown
            label="Solutions"
            menuKey="solutions"
            openMenu={openMenu}
            setOpenMenu={setOpenMenu}
          >
            <ul className="grid gap-1">
              {solutionsMenuItems.map((item) => (
                <li key={item.href}>
                  <Link
                    to={item.href}
                    onClick={() => setOpenMenu(null)}
                    className="block rounded-lg p-3 hover:bg-slate-50"
                  >
                    <span className="block text-sm font-semibold text-brand-navy">
                      {item.title}
                    </span>
                    {item.description ? (
                      <span className="block text-xs text-slate-500">{item.description}</span>
                    ) : null}
                  </Link>
                </li>
              ))}
            </ul>
          </DesktopDropdown>

          <NavLink
            to="/resources"
            className="rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:text-brand-navy"
          >
            Resources
          </NavLink>

          <DesktopDropdown
            label="Company"
            menuKey="company"
            openMenu={openMenu}
            setOpenMenu={setOpenMenu}
          >
            <ul className="grid gap-1">
              {companyMenuItems.map((item) => (
                <li key={item.href}>
                  <Link
                    to={item.href}
                    onClick={() => setOpenMenu(null)}
                    className="block rounded-lg p-3 text-sm font-medium text-brand-navy hover:bg-slate-50"
                  >
                    {item.title}
                  </Link>
                </li>
              ))}
            </ul>
          </DesktopDropdown>
        </div>

        <div className="hidden items-center gap-3 lg:flex">
          <Link to="/login" className="text-sm font-medium text-slate-700 hover:text-brand-navy">
            Log in
          </Link>
          <LinkButton to="/contact" size="sm">
            Request a demo
          </LinkButton>
        </div>

        <button
          type="button"
          className="rounded-md p-2 text-brand-navy lg:hidden"
          aria-expanded={mobileOpen}
          aria-controls="mobile-nav-drawer"
          aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
          onClick={() => setMobileOpen((open) => !open)}
        >
          {mobileOpen ? (
            <X className="size-6" aria-hidden="true" />
          ) : (
            <Menu className="size-6" aria-hidden="true" />
          )}
        </button>
      </nav>

      {mobileOpen ? (
        <div
          id="mobile-nav-drawer"
          className="fixed inset-0 top-[57px] z-40 overflow-y-auto bg-white p-6 lg:hidden"
        >
          <div className="flex flex-col gap-6">
            <MobileSection
              title="Platform"
              items={platformMenuItems}
              onNavigate={() => setMobileOpen(false)}
            />
            <MobileSection
              title="Solutions"
              items={solutionsMenuItems}
              onNavigate={() => setMobileOpen(false)}
            />
            <Link
              to="/resources"
              onClick={() => setMobileOpen(false)}
              className="text-base font-semibold text-brand-navy"
            >
              Resources
            </Link>
            <MobileSection
              title="Company"
              items={companyMenuItems}
              onNavigate={() => setMobileOpen(false)}
            />
            <div className="flex flex-col gap-3 border-t border-slate-200 pt-6">
              <Link
                to="/login"
                onClick={() => setMobileOpen(false)}
                className="text-center text-base font-medium text-brand-navy"
              >
                Log in
              </Link>
              <LinkButton to="/contact" onClick={() => setMobileOpen(false)}>
                Request a demo
              </LinkButton>
            </div>
          </div>
        </div>
      ) : null}
    </header>
  )
}

function MobileSection({
  title,
  items,
  onNavigate,
}: {
  title: string
  items: { title: string; href: string }[]
  onNavigate: () => void
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">{title}</p>
      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item.href}>
            <Link
              to={item.href}
              onClick={onNavigate}
              className="text-base font-medium text-brand-navy"
            >
              {item.title}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
