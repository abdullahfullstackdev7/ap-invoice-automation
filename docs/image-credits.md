# Image credits

Plan.md section 10 asks for free stock photography (Unsplash/Pexels) and
open illustration sets (unDraw/Storyset) for the public marketing site,
plus a real Playwright-captured screenshot of the running app for the
hero and dashboard visuals.

**This environment could not reach those external services** (see the
`feedback_repo_isolation_ap_invoice_automation` note on this sandbox's
throttled network), and no seeded, screenshot-ready instance of the app
was running when the marketing pages were built. Rather than fabricate
credits for images that were never actually fetched, every visual on the
public site is one of:

- An inline SVG icon from `lucide-react` (MIT licensed, bundled as a
  dependency, no attribution required beyond the license file in
  `node_modules/lucide-react`).
- A CSS-built mockup (`src/pages/home/DashboardMockup.tsx`): gradients,
  bar/line shapes, and the same copy a real dashboard would show,
  explicitly commented in the source as a documented stand-in rather
  than a real screenshot.
- Plain CSS gradients and typography (the role-value and platform
  section panels), with no image asset at all.

No real company logos, customer photos, or third-party stock images are
used anywhere on the site. The "trust strip" wordmarks and customer
story cards are explicitly labeled as illustrative in the UI.

**If this is deployed somewhere with outbound network access**, the
straightforward next step is to replace `DashboardMockup` with a real
screenshot captured by a Playwright script against a seeded instance of
the authenticated app (once Phase 11 exists to screenshot), and to swap
the CSS panels in `RoleValue`/`PlatformPage`/`SolutionsPage` for sourced
Unsplash/Pexels photography or unDraw/Storyset illustrations, with
credits recorded in this file at that time.
