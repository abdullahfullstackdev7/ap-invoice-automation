import {
  BarChart3,
  Building2,
  Database,
  FileCheck2,
  FileSearch,
  Inbox,
  Landmark,
  Lock,
  Mail,
  Plug,
  ScanLine,
  Scale,
  Server,
  ShieldCheck,
  ShieldHalf,
  UserCheck,
  Wallet,
  Workflow,
  type LucideIcon,
} from 'lucide-react'

export interface ImpactMetric {
  label: string
  value: number
  suffix: string
  decimals?: number
  note: string
}

// Sourced from docs/evaluation.md and docs/analytics.md's smoke-test runs
// in this environment; see docs/image-credits.md for the caveat on scale.
export const impactMetrics: ImpactMetric[] = [
  {
    label: 'Header extraction accuracy',
    value: 95,
    suffix: '%',
    note: 'F1 on header fields, rules-first extraction',
  },
  {
    label: 'Exceptions caught before payment',
    value: 100,
    suffix: '%',
    note: 'duplicates, price drift and over-receipt',
  },
  {
    label: 'Average cycle time',
    value: 48,
    suffix: 'h',
    note: 'intake to payment release, clean invoices',
  },
  {
    label: 'Straight-through processing',
    value: 70,
    suffix: '%',
    note: 'invoices needing zero human touch',
  },
]

export interface HowItWorksStep {
  step: number
  title: string
  description: string
}

export const howItWorksSteps: HowItWorksStep[] = [
  {
    step: 1,
    title: 'Capture',
    description:
      'Drop in a PDF, photo or scan. Duplicate files are caught by hash before they cost you anything.',
  },
  {
    step: 2,
    title: 'Extract',
    description:
      'Deterministic rules read the header and line items first; an LLM only steps in when they fail.',
  },
  {
    step: 3,
    title: 'Match',
    description:
      'Invoice, purchase order and goods receipt are reconciled line by line against your tolerances.',
  },
  {
    step: 4,
    title: 'Approve and pay',
    description:
      'Clean invoices route straight through; exceptions go to the right approver with full context.',
  },
]

export interface FeatureCard {
  title: string
  description: string
  icon: LucideIcon
}

export const featureCards: FeatureCard[] = [
  {
    title: 'Document capture',
    description: 'Multi-file upload, magic-byte validation and exact-duplicate detection.',
    icon: ScanLine,
  },
  {
    title: 'Intelligent extraction',
    description: 'Rules-first parsing with a token-budgeted LLM fallback for the rest.',
    icon: FileSearch,
  },
  {
    title: '3-way match',
    description:
      'Invoice vs. purchase order vs. goods receipt, line by line, with policy tolerances.',
    icon: FileCheck2,
  },
  {
    title: 'Exception workflow',
    description: 'SLA-timed queues, default assignment by reason code, full history.',
    icon: Workflow,
  },
  {
    title: 'Approval routing',
    description: 'Amount- and risk-based policy routing with segregation of duties.',
    icon: ShieldCheck,
  },
  {
    title: 'Payment scheduling',
    description: 'Pays on the due date, or earlier when the discount is worth it.',
    icon: Wallet,
  },
  {
    title: 'Analytics',
    description: 'Cycle time, exception trends, vendor scorecards and cash flow forecasting.',
    icon: BarChart3,
  },
  {
    title: 'Audit trail',
    description: 'Append-only, hash-chained log of every state change and login.',
    icon: Scale,
  },
]

export interface RoleValueTab {
  id: string
  label: string
  title: string
  bullets: string[]
}

export const roleValueTabs: RoleValueTab[] = [
  {
    id: 'ap-team',
    label: 'AP Team',
    title: 'Spend your time on exceptions, not data entry',
    bullets: [
      'Clean invoices route straight through with no manual keying.',
      'A single queue, sorted by SLA, replaces a shared inbox and a spreadsheet.',
      'Every action - approve, reject, request a credit note - is one click.',
    ],
  },
  {
    id: 'controllers',
    label: 'Controllers',
    title: 'Close the books with numbers you can defend',
    bullets: [
      'Every exception is tied to the numeric evidence that raised it.',
      'Vendor scorecards and aging reports are always current, not a month-end scramble.',
      'Segregation of duties is enforced in the workflow, not just in policy.',
    ],
  },
  {
    id: 'procurement',
    label: 'Procurement',
    title: 'Keep the PO terms you negotiated',
    bullets: [
      'Price drift against the PO is flagged automatically, line by line.',
      'Over-receipt and short-receipt exceptions surface before payment, not after.',
      'Vendor price history keeps renewals and negotiations grounded in data.',
    ],
  },
  {
    id: 'audit',
    label: 'Internal Audit',
    title: 'Evidence, not assertions',
    bullets: [
      'A hash-chained audit log covers every login and every state change.',
      'Approval policy is enforced in code, so a control either held or it did not.',
      'Role-based access is deny-by-default, with object-level checks on every resource.',
    ],
  },
]

export interface SecurityTile {
  title: string
  description: string
  icon: LucideIcon
}

export const securityTiles: SecurityTile[] = [
  {
    title: 'Role-based access',
    description: 'Five roles, deny-by-default, enforced on every endpoint and object.',
    icon: UserCheck,
  },
  {
    title: 'Encryption',
    description: 'TLS in transit; vendor bank details encrypted at rest.',
    icon: Lock,
  },
  {
    title: 'Audit trail',
    description: 'Append-only, hash-chained log of every login and state change.',
    icon: Scale,
  },
  {
    title: 'Segregation of duties',
    description: 'An uploader cannot approve their own invoice or release its payment.',
    icon: ShieldHalf,
  },
  {
    title: 'Data retention',
    description: 'Documents and records retained on a defined, configurable schedule.',
    icon: Database,
  },
  {
    title: 'Secure uploads',
    description: 'Magic-byte validation, size and page limits, randomized storage paths.',
    icon: Server,
  },
]

export interface IntegrationItem {
  title: string
  status: 'Planned' | 'Available'
  icon: LucideIcon
}

export const integrationItems: IntegrationItem[] = [
  { title: 'ERP', status: 'Planned', icon: Building2 },
  { title: 'Bank file', status: 'Available', icon: Landmark },
  { title: 'Email inbox', status: 'Planned', icon: Mail },
  { title: 'SFTP', status: 'Planned', icon: Inbox },
  { title: 'API', status: 'Available', icon: Plug },
]

export interface CustomerStory {
  company: string
  quote: string
  person: string
  role: string
}

export const customerStories: CustomerStory[] = [
  {
    company: 'Northfield Logistics (illustrative scenario)',
    quote:
      'Straight-through processing took our clean invoices off the team’s desk entirely. The exception queue is the only thing anyone touches now.',
    person: 'Illustrative AP Manager',
    role: 'Accounts Payable',
  },
  {
    company: 'Harborview Retail Group (illustrative scenario)',
    quote:
      'Price drift used to surface at month-end, if at all. Now it is flagged the moment the invoice lands, before we have paid a cent.',
    person: 'Illustrative Controller',
    role: 'Finance',
  },
  {
    company: 'Caldwell Manufacturing (illustrative scenario)',
    quote:
      'The audit trail is the first thing our auditors ask for, and the first thing we hand over without a scramble.',
    person: 'Illustrative Internal Auditor',
    role: 'Internal Audit',
  },
]

export interface FaqItem {
  question: string
  answer: string
}

export const faqItems: FaqItem[] = [
  {
    question: 'How accurate is the extraction?',
    answer:
      'Header fields are extracted with deterministic rules first; an LLM fallback is only used when rules fail or confidence is low. See docs/evaluation.md in the repository for current accuracy numbers against the evaluation set.',
  },
  {
    question: 'What file formats are supported?',
    answer:
      'PDF, JPG and PNG, up to 15 MB and 20 pages, validated by magic bytes rather than file extension.',
  },
  {
    question: 'What happens when the invoice, PO and receipt do not match?',
    answer:
      'The invoice is routed to an exception queue with the specific numeric variance attached (price, quantity or total), sorted by an SLA timer, and assigned by reason code.',
  },
  {
    question: 'How is our data secured?',
    answer:
      'Role-based access control, encrypted bank details, TLS in transit, and an append-only hash-chained audit log of every state change. See the Security page for the full list of controls.',
  },
  {
    question: 'How is this deployed?',
    answer:
      'As a containerized application (Docker Compose for local and demo use); the architecture supports a managed-database deployment for production use.',
  },
  {
    question: 'What does it integrate with?',
    answer:
      'A bank-file export and a REST API are available today. ERP, inbox and SFTP connectors are planned; see the Platform page for current status.',
  },
  {
    question: 'How is the LLM used, and what happens to our data?',
    answer:
      'About 70% of invoices never reach an LLM at all. When one is used, only the specific failing region of text is sent, never the full page by default, with no tools and a schema-constrained response; see the Security page for the full data-handling policy.',
  },
  {
    question: 'What is the pricing model?',
    answer:
      'This is a sample product built for demonstration, not a commercial offering, so there is no live pricing. A production deployment would typically price per invoice volume or per seat.',
  },
]
