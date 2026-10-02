import { AnalyticsShowcase } from '@/pages/home/AnalyticsShowcase'
import { CustomerStories } from '@/pages/home/CustomerStories'
import { Faq } from '@/pages/home/Faq'
import { FeatureGrid } from '@/pages/home/FeatureGrid'
import { FinalCta } from '@/pages/home/FinalCta'
import { Hero } from '@/pages/home/Hero'
import { HowItWorks } from '@/pages/home/HowItWorks'
import { ImpactMetrics } from '@/pages/home/ImpactMetrics'
import { Integrations } from '@/pages/home/Integrations'
import { MatchPreview } from '@/pages/home/MatchPreview'
import { RoleValue } from '@/pages/home/RoleValue'
import { SecurityGovernance } from '@/pages/home/SecurityGovernance'
import { TrustStrip } from '@/pages/home/TrustStrip'

export function HomePage() {
  return (
    <>
      <Hero />
      <TrustStrip />
      <ImpactMetrics />
      <HowItWorks />
      <MatchPreview />
      <FeatureGrid />
      <RoleValue />
      <AnalyticsShowcase />
      <SecurityGovernance />
      <Integrations />
      <CustomerStories />
      <Faq />
      <FinalCta />
    </>
  )
}
