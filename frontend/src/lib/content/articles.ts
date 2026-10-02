export interface Article {
  slug: string
  title: string
  excerpt: string
  readingTime: string
  category: string
  body: string[]
}

export const articles: Article[] = [
  {
    slug: 'what-is-3-way-match',
    title: 'What is 3-way match, and why most teams skip it',
    excerpt:
      'The theory is simple: invoice, PO and receipt should agree. The practice is where it breaks down.',
    readingTime: '6 min read',
    category: '3-way match',
    body: [
      'A 3-way match checks that what was ordered, what was received and what is being billed all agree before a payment is released. In principle, every AP team already knows this. In practice, most teams only do it for invoices above a dollar threshold, because matching by hand does not scale.',
      'The cost of skipping it is not abstract: price drift that goes unnoticed, invoices for quantities never received, and duplicate payments that only surface during a reconciliation months later. None of these are rare. They are the default outcome of a process that relies on a person remembering to check.',
      'Automating the match does not remove judgment from the process, it relocates it. Instead of a person deciding whether to check an invoice, a person decides what to do about an invoice that already failed a check, with the specific numeric variance in front of them.',
    ],
  },
  {
    slug: 'reducing-ap-cycle-time',
    title: 'Reducing AP cycle time without adding headcount',
    excerpt:
      'Cycle time rarely improves by working faster. It improves by removing the invoices that never needed a human in the first place.',
    readingTime: '5 min read',
    category: 'Operations',
    body: [
      'Most AP cycle-time projects start by asking the team to work faster. This has a ceiling: a person can only review so many invoices a day, and rushing the review is how exceptions get missed.',
      'The more durable lever is reducing the number of invoices that need a human at all. A clean invoice against an open PO, within tolerance on price and quantity, does not need judgment. It needs confirmation, which a rules engine can give in milliseconds.',
      'That reframes the team’s job: instead of reviewing every invoice, they review the ones the system could not clear on its own, each one already annotated with exactly what failed and by how much.',
    ],
  },
  {
    slug: 'price-variance-detection',
    title: 'Catching price variance before you pay, not after',
    excerpt:
      'A 5% price drift on a recurring order compounds fast. Most teams find out at month-end, or never.',
    readingTime: '4 min read',
    category: '3-way match',
    body: [
      'Price variance is one of the quieter ways AP leaks money. A vendor raises a unit price by a few percent, the invoice still looks plausible on its face, and it gets paid. Multiply that by every recurring order and the leakage adds up well before anyone notices a pattern.',
      'Catching it requires comparing the invoiced price against the purchase order price at the line level, every time, not just on invoices above a review threshold. That only becomes practical when the comparison itself is automatic.',
      'The useful threshold is not binary either: a small drift within tolerance should pass silently, a moderate drift should be a warning, and a drift that crosses a real line should block payment until someone looks at it.',
    ],
  },
  {
    slug: 'segregation-of-duties-in-ap',
    title: 'Segregation of duties is a workflow problem, not a policy document',
    excerpt:
      'Writing down that the uploader cannot approve their own invoice does not stop it from happening.',
    readingTime: '5 min read',
    category: 'Audit and controls',
    body: [
      'Most finance teams can describe their segregation-of-duties policy without hesitation: the person who uploads an invoice should not be the person who approves it, and the person who approves a payment should not be the person who releases it.',
      'The gap is usually not in the policy, it is in enforcement. If the system that processes invoices does not check who uploaded what, the policy is only as good as everyone remembering to follow it, under deadline pressure, every time.',
      'Enforcing it in the workflow itself - rejecting an approval attempt from the uploader, rejecting a batch release from its creator - turns a policy statement into something an auditor can actually test.',
    ],
  },
  {
    slug: 'early-pay-discounts',
    title: 'The early-pay discount math most AP teams leave on the table',
    excerpt:
      'A 2/10 net 30 term is worth more annualized than it looks. Most invoices pay on day 30 anyway.',
    readingTime: '4 min read',
    category: 'Payments',
    body: [
      'A vendor term like "2/10 net 30" offers a 2% discount for paying within 10 days instead of the normal 30. On its face, 2% does not sound dramatic. Annualized, it is a return well above most companies’ cost of capital.',
      'The reason it goes uncaptured is rarely a decision not to take it. It is that invoices move through approval queues at their own pace, and by the time one is approved, the 10-day window has already closed.',
      'Capturing it systematically means comparing the discount’s annualized return against a hurdle rate at the moment an invoice is approved, and scheduling payment inside the discount window whenever it clears that bar - not leaving it to whoever happens to notice the terms.',
    ],
  },
  {
    slug: 'llm-use-in-finance-workflows',
    title: 'Where an LLM belongs in a finance workflow, and where it does not',
    excerpt:
      'Extraction is a reasonable place for a language model. Matching and routing money are not.',
    readingTime: '6 min read',
    category: 'Technology',
    body: [
      'It is tempting to point a large language model at an entire AP workflow: read the invoice, decide if it matches, decide who should approve it. Each of those is a different kind of problem, and only one of them benefits from a model that reasons in natural language.',
      'Extracting a vendor name or a total from unstructured text is exactly the kind of fuzzy, high-variance task a language model is good at, especially as a fallback after a deterministic parser has already done the easy cases for free.',
      'Deciding whether a price is within tolerance, or which approver a $12,000 exception should route to, is not a language problem. It is arithmetic and policy, and arithmetic should be computed, not inferred. Keeping the model out of matching and routing is not a limitation, it is what makes the result auditable.',
    ],
  },
]
