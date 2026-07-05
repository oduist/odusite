# Odusite Specifications

The specs are the source of truth: the full system (Odoo addons + Astro site)
must be re-creatable from them. Keep them updated with every architectural or
API change. Do not put code here — routes, models, fields, relations, flows.

## Index

- `00-overview.md` — goal, components, module mapping
- `01-architecture.md` — components, rendering, security, state
- `02-api-conventions.md` — transport, headers, envelope, pagination
- `03-auth.md` — JWT portal auth, refresh tokens, signup/reset
- `04-payments.md` — headless payment flow (Stripe first)
- `05-media-seo-i18n.md` — images proxy, SEO, sitemap, languages
- `06-cache-invalidation.md` — Odoo→site webhooks, cache tags
- `07-roadmap.md` — phases and status
- `decisions.md` — ADR log
- `modules/*.md` — one spec per Odoo addon (endpoints, models, fields)
- `site/*.md` — Astro structure, blocks, theming, deploy
