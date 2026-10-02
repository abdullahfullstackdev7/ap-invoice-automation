import { Outlet } from 'react-router-dom'

import { Footer } from '@/components/layout/Footer'
import { MainNav } from '@/components/layout/MainNav'
import { TopUtilityBar } from '@/components/layout/TopUtilityBar'

export function PublicLayout() {
  return (
    <div className="flex min-h-svh flex-col">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <TopUtilityBar />
      <MainNav />
      <main id="main-content" className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
