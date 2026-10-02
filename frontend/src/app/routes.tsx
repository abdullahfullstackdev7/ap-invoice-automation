import { Route, Routes } from 'react-router-dom'

import { PublicLayout } from '@/components/layout/PublicLayout'
import { AboutPage } from '@/pages/AboutPage'
import { AppStubPage } from '@/pages/AppStubPage'
import { ContactPage } from '@/pages/ContactPage'
import { CookieNoticePage } from '@/pages/CookieNoticePage'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PlatformPage } from '@/pages/PlatformPage'
import { PrivacyPage } from '@/pages/PrivacyPage'
import { ResourceArticlePage } from '@/pages/ResourceArticlePage'
import { ResourcesPage } from '@/pages/ResourcesPage'
import { SecurityPage } from '@/pages/SecurityPage'
import { ServerErrorPage } from '@/pages/ServerErrorPage'
import { SolutionsPage } from '@/pages/SolutionsPage'
import { TermsPage } from '@/pages/TermsPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/platform" element={<PlatformPage />} />
        <Route path="/solutions" element={<SolutionsPage />} />
        <Route path="/security" element={<SecurityPage />} />
        <Route path="/resources" element={<ResourcesPage />} />
        <Route path="/resources/:slug" element={<ResourceArticlePage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/cookies" element={<CookieNoticePage />} />
        <Route path="/500" element={<ServerErrorPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/app" element={<AppStubPage />} />
    </Routes>
  )
}
