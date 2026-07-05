# Roadmap & Status

Phases reproduce Odoo website/portal functionality incrementally.
Status: ✅ done · 🚧 in progress · ⬜ planned.

## Phase 1 — Foundation + core commerce/content (implemented; runtime testing pending)

| Area | Addon | Block | Status |
|---|---|---|---|
| API core, webhooks, sitemap, site config | odusite_base | core | ✅ |
| JWT auth, /my home, account, addresses, security | odusite_portal | portal | ✅ |
| Blog (posts, tags, comments read) | odusite_blog | blog | ✅ |
| Contact forms → crm.lead | odusite_crm | forms | ✅ |
| Catalog, variants, cart, checkout, portal orders (sign/decline/pay) | odusite_sale | shop | ✅ |
| Headless payments (Stripe first) | odusite_payment | shop/portal | ✅ |
| Portal invoices (+ pay, PDF) | odusite_account | portal | ✅ |
| Portal projects/tasks (+ chatter) | odusite_project | portal | ✅ |
| Events (listing, detail, free registration) | odusite_event | events | ✅ |
| Jobs (listing, detail, application) | odusite_hr_recruitment | jobs | ✅ |
| Partners/references directory | odusite_partner | partners | ✅ |
| Forum (read, ask/answer/vote with JWT) | odusite_forum | forum | ✅ |
| Courses (catalog, course page, enroll public, progress) | odusite_slides | courses | ✅ |
| Newsletter subscribe (footer form) | odusite_mass_mailing | newsletter | ✅ |
| Unified site search (`/search`) | odusite_base | core | ✅ |
| Astro scaffold, theming, default dark theme | — | — | ✅ |
| CI (addon tests on odoo:19.0 + site check/build) | — | — | ✅ |

## Phase 2 — Extended commerce & portal

- Paid event tickets through cart (website_event_sale), event tracks/agenda,
  booths, exhibitors.
- Wishlist, comparison, stock display rules (website_sale_stock), loyalty
  coupons/promo codes, pickup points/click&collect.
- Subscriptions portal + subscription checkout (sale_subscription).
- Helpdesk: public team pages + ticket form + /my/tickets.
- Appointments: public booking flow + /my/appointments.
- More PSPs (PayPal redirect flow, Adyen), saved-token management UX, MFA login.

## Phase 3 — Long tail

- Knowledge public articles, Documents share links, Sign portal signing flow,
  rentals (date pickers, availability), memberships, eLearning certifications,
  livechat (separate realtime channel), multi-website deployments,
  visitor analytics bridge.

## Explicitly out of scope

- Odoo website builder (QWeb snippets, drag&drop) and `website.page` HTML
  passthrough — marketing pages are authored in Astro.
- Odoo frontend assets/JS; `web_studio`, `website_studio`, dashboards and other
  backend tooling.
