import {
  BarChart3,
  FileCheck2,
  FileSearch,
  Scale,
  ScanLine,
  ShieldCheck,
  Wallet,
  Workflow,
  type LucideIcon,
} from 'lucide-react'

export interface PlatformMenuItem {
  title: string
  description: string
  href: string
  icon: LucideIcon
}

export const platformMenuItems: PlatformMenuItem[] = [
  {
    title: 'Document capture',
    description: 'Multi-file upload with duplicate detection and OCR.',
    href: '/platform#capture',
    icon: ScanLine,
  },
  {
    title: 'Intelligent extraction',
    description: 'Rules-first parsing with an LLM fallback only when needed.',
    href: '/platform#extraction',
    icon: FileSearch,
  },
  {
    title: '3-way match',
    description: 'Invoice, purchase order and receipt reconciled automatically.',
    href: '/platform#match',
    icon: FileCheck2,
  },
  {
    title: 'Exception workflow',
    description: 'SLA-timed queues with a full audit trail on every action.',
    href: '/platform#exceptions',
    icon: Workflow,
  },
  {
    title: 'Approval routing',
    description: 'Policy-driven approvals with segregation of duties built in.',
    href: '/platform#approvals',
    icon: ShieldCheck,
  },
  {
    title: 'Payment scheduling',
    description: 'Early-pay discounts captured automatically when they pay off.',
    href: '/platform#payments',
    icon: Wallet,
  },
  {
    title: 'Analytics',
    description: 'Cycle time, exception trends and spend, in one dashboard.',
    href: '/platform#analytics',
    icon: BarChart3,
  },
  {
    title: 'Audit trail',
    description: 'Hash-chained, append-only log of every state change.',
    href: '/platform#audit',
    icon: Scale,
  },
]

export interface SimpleNavItem {
  title: string
  description?: string
  href: string
}

export const solutionsMenuItems: SimpleNavItem[] = [
  {
    title: 'For AP teams',
    href: '/solutions#ap-team',
    description: 'Clear fewer invoices by hand each month.',
  },
  {
    title: 'For controllers',
    href: '/solutions#controllers',
    description: 'Close the books with confidence.',
  },
  {
    title: 'For procurement',
    href: '/solutions#procurement',
    description: 'Keep PO terms honest at invoice time.',
  },
  {
    title: 'For internal audit',
    href: '/solutions#audit',
    description: 'Prove controls instead of describing them.',
  },
]

export const companyMenuItems: SimpleNavItem[] = [
  { title: 'About', href: '/about' },
  { title: 'Security', href: '/security' },
  { title: 'Contact sales', href: '/contact' },
  { title: 'Privacy', href: '/privacy' },
  { title: 'Terms', href: '/terms' },
  { title: 'Cookie notice', href: '/cookies' },
]

export const footerColumns: { heading: string; links: SimpleNavItem[] }[] = [
  {
    heading: 'Platform',
    links: platformMenuItems.map((item) => ({ title: item.title, href: item.href })),
  },
  {
    heading: 'Solutions',
    links: solutionsMenuItems,
  },
  {
    heading: 'Resources',
    links: [
      { title: 'All articles', href: '/resources' },
      { title: 'Platform overview', href: '/platform' },
      { title: 'Security', href: '/security' },
    ],
  },
  {
    heading: 'Company',
    links: [
      { title: 'About', href: '/about' },
      { title: 'Contact sales', href: '/contact' },
    ],
  },
  {
    heading: 'Legal',
    links: [
      { title: 'Privacy', href: '/privacy' },
      { title: 'Terms', href: '/terms' },
      { title: 'Cookie notice', href: '/cookies' },
    ],
  },
]
