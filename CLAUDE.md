# Odusite — Odoo as Headless CMS + Astro Frontend

## What this project is

Odusite re-creates the entire public website and customer portal of Odoo 19.0 as a
standalone [Astro](https://astro.build) site deployed on Cloudflare Workers, with Odoo
acting as a headless CMS/backend. Odoo's own website rendering (QWeb, snippets,
website builder) is **not** used. The Astro site talks to Odoo exclusively through the
REST API provided by the `odusite_*` addons, authenticated with a shared secret sent in
the `X-Odusite-Token` HTTP header (value comes from the `ODUSITE_TOKEN` env var on both
sides).

Reference Odoo sources (read-only, for studying upstream behavior):
- Community addons: `~/Dev/odoo_19/addons`
- Enterprise addons: `~/Dev/odoo_enterprise`

## Repository layout

```
addons/          Odoo 19 addons. One addon per functional area: odusite_base,
                 odusite_portal, odusite_blog, odusite_crm, odusite_sale, ...
                 Each depends on (inherits from) the standard Odoo module it exposes
                 (crm, sale, website_blog, ...) and contains mostly HTTP controllers.
site/            The Astro frontend (pnpm, TypeScript, @astrojs/cloudflare adapter).
specs/           Architecture & module specifications (English). The specs are the
                 source of truth: the whole system must be re-creatable from them.
docs/admin/      Administrator documentation (installation, configuration) — English.
docs/user/       End-user documentation — English.
```

## Core architectural decisions (do not silently change; see specs/decisions.md)

1. **Transport**: REST-style JSON API under `/odusite/v1/...` on the Odoo side.
   Every request must carry `X-Odusite-Token`. User context (portal) is an additional
   `Authorization: Bearer <JWT>` header. See `specs/02-api-conventions.md`.
2. **Portal auth**: JWT issued by Odoo (`odusite_portal`): short-lived access token +
   rotating refresh tokens stored hashed in Odoo. No Odoo session cookies are used.
3. **Payments**: fully headless. Odoo creates `payment.transaction`, the frontend runs
   the provider's JS (Stripe Payment Element first); provider webhooks go directly to
   Odoo's standard webhook routes. See `specs/04-payments.md`.
4. **Rendering**: hybrid SSR on Cloudflare Workers. Marketing pages prerendered/edge
   cached, catalog/cart/portal SSR. Odoo pushes webhooks to invalidate cache.
5. **Content**: marketing pages live in Astro (content collections / components).
   Odoo is the source of *entity* data only (products, posts, events, jobs, ...).
   `website.page` QWeb pages are intentionally not exposed.
6. **Cart**: stateless w.r.t. Odoo sessions — the cart is a draft `sale.order`
   addressed by `id` + `access_token`, stored in a first-party cookie on the site.

## Conventions

### Odoo addons (`addons/`)
- Target Odoo 19.0, Python ≥ 3.10. Follow Odoo coding guidelines (module structure,
  `_inherit`, no monkey-patching). License: LGPL-3, `'author': 'Odusite'`.
- Naming: `odusite_<odoo module it builds on>` (e.g. `odusite_sale` extends `sale` /
  `website_sale`). Everything shared (token check, JSON envelope, pagination, image
  URLs, webhooks) lives in `odusite_base` — never duplicate it.
- Controllers use the `route()` helper from
  `odoo.addons.odusite_base.controllers.api` (wraps token check, JWT resolution, JSON
  parsing, error mapping, lang activation). Never write a raw `@http.route` returning
  JSON by hand in odusite modules.
- All read endpoints must filter with `is_published` / `website_domain()` exactly like
  the upstream website controllers do, and must never leak non-published records.
- Security: never trust client-provided ids without access checks. Documents are
  accessed either through the JWT user (record rules) or via `access_token`
  (`_document_check_access` pattern). API errors must not leak internals.
- Each new endpoint or field = update the module's spec in `specs/modules/` first
  (or in the same change), then the implementation, then docs.

### Astro site (`site/`)
- Node ≥ 20, pnpm, TypeScript strict. Adapter: `@astrojs/cloudflare` (SSR) with
  `prerender = true` for static marketing pages.
- **Blocks**: functionality is grouped into build-time-activated blocks
  (`blog`, `shop`, `portal`, `events`, `jobs`, `partners`, `forum`, `courses`, ...).
  Activation via `odusite.config.mjs` + `ODUSITE_BLOCK_*` env overrides. A disabled
  block must contribute zero routes and zero JS. See `specs/site/01-blocks.md`.
- **Themes**: all visual styling flows through the theme layer
  (`src/themes/<name>/`): design tokens (CSS custom properties) + overridable
  components resolved through the `@theme` alias. Default theme: `default` (dark).
  Never hardcode colors/spacing in block components — use tokens.
- All Odoo access goes through `src/lib/api/` (typed client). Components never fetch
  Odoo directly. `ODUSITE_TOKEN` and other secrets are server-side only — never ship
  them to the browser bundle.
- Images: use the `/img/**` proxy (Worker route that forwards to Odoo `/web/image/**`
  with long-lived caching keyed by the `unique` checksum).

### Specs (`specs/`)
- English (all specs, docs, code and comments are in English; conversation with the
  project owner is in Russian). Purpose: the complete system must be re-creatable
  from specs alone.
- Keep them concise: describe routes, models, fields, relations, flows and decisions —
  do not paste code.
- Any architectural decision gets a numbered entry in `specs/decisions.md` (ADR-style:
  context → decision → consequences).

### Docs (`docs/`)
- English. `docs/admin/` — installation, Odoo settings, tokens, Cloudflare deploy,
  per-module configuration. `docs/user/` — how the site/portal works for end users.
- Documentation is part of "done" for every module: new module/block ⇒ new/updated
  admin + user doc pages.

### Git
- Do not add `Co-Authored-By` trailers. Commit messages in English, imperative.

## Definition of done for a new functional area

1. Spec in `specs/modules/odusite_<x>.md` (routes, models, fields, flows).
2. Addon in `addons/odusite_<x>` (controllers + minimal models), installable on
   Odoo 19 with its upstream dependency.
3. Astro block in `site/src/blocks/<x>` behind build-time activation, themed via
   tokens only.
4. `docs/admin/<x>.md` + `docs/user/<x>.md`.
5. `specs/07-roadmap.md` status table updated.

## Environment variables

| Var | Where | Purpose |
|---|---|---|
| `ODUSITE_TOKEN` | Odoo (system param `odusite.token`) + site secret | server-to-server auth, sent as `X-Odusite-Token` |
| `ODOO_URL` | site | base URL of the Odoo instance |
| `ODUSITE_JWT_SECRET` | Odoo (system param `odusite.jwt_secret`) | HS256 signing key, auto-generated |
| `ODUSITE_BLOCK_*` | site build | enable/disable blocks (`1`/`0`) |
| `ODUSITE_THEME` | site build | theme name (default: `default`) |
| `STRIPE_PUBLISHABLE_KEY` | site | Stripe Elements (public) |
| `ODUSITE_REVALIDATE_SECRET` | site + Odoo webhook | HMAC secret for cache-invalidation webhooks |
