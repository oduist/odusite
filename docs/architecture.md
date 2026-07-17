# Architecture

Odusite splits cleanly into two halves joined by a single, deliberate seam:
an Astro frontend on Cloudflare Workers, and Odoo 19 acting as a headless
CMS/backend. The browser only ever talks to the Astro site; the site's Worker
talks to Odoo over a token-secured REST API.

```
Browser ⇄ Cloudflare Worker (Astro SSR + edge cache)
              │  HTTPS, X-Odusite-Token (+ Authorization: Bearer JWT)
              ▼
          Odoo 19 (addons/odusite_*)  ⇄  PostgreSQL
              │
              └─ webhooks (HMAC) → Worker /api/revalidate → edge cache purge
Stripe (and other PSPs) ⇄ browser (JS SDK) ; PSP webhooks → directly to Odoo
```

## The two halves

### Odoo addons (`addons/odusite_*`)

Each addon depends on (inherits from) a standard Odoo module — `sale`,
`website_blog`, `crm`, `project`, … — and adds HTTP controllers under
`/odusite/v1/...`. Odoo's own rendering (QWeb, snippets, the website builder)
is intentionally unused; the addons expose **data**, not HTML.

Everything shared lives in **`odusite_base`** and is never duplicated: the
token check, the JSON response envelope, pagination, image URLs and the
cache-invalidation webhooks. Controllers use a `route()` helper that wraps the
token check, JWT resolution, JSON parsing, error mapping and language
activation, so no addon writes a raw JSON route by hand.

### Astro site (`site/`)

Hybrid SSR on Cloudflare Workers with `@astrojs/cloudflare`. Functionality is
grouped into build-time **blocks** (`blog`, `shop`, `portal`, `events`, `jobs`,
`partners`, `forum`, `courses`, …) — a disabled block contributes zero routes
and zero JS. All visual styling flows through a **theme** layer of design
tokens; the default theme is dark. All Odoo access goes through a single typed
API client — components never fetch Odoo directly, and secrets stay
server-side.

## Rendering & caching

- **Marketing pages** (home, About, landings) are authored in Astro and
  prerendered (`prerender = true`) — static at the edge.
- **Catalog, detail pages, listings** render on demand (SSR) and are edge-cached
  by URL + language, tagged for targeted invalidation.
- **Cart, checkout, portal** render on demand without caching
  (`Cache-Control: private`).
- When published entities change in Odoo, a signed webhook hits the Worker's
  revalidate route and purges exactly the affected pages — no full rebuild.

## Authentication & security

- Every site→Odoo request carries **`X-Odusite-Token`**, checked in Odoo with a
  constant-time comparison against the `odusite.token` system parameter. Without
  it, any `/odusite/...` route returns `401`.
- Portal context is a short-lived **JWT** (HS256, secret `odusite.jwt_secret`,
  auto-generated on install) sent as `Authorization: Bearer`. No Odoo session
  cookies are used; refresh tokens rotate and are stored hashed in Odoo.
- Portal documents are reached either through the JWT user's record rules or the
  record's `access_token` (the `_document_check_access` pattern) — client-provided
  ids are never trusted without an access check.
- Public reads are always filtered like the stock website controllers
  (`is_published`, multi-website domain, publish date), so no unpublished record
  leaks.
- Rate limiting, bot protection and Turnstile on public-record forms run at the
  Cloudflare edge, verified by the Worker before it calls Odoo.

## Client-side state

First-party, `httpOnly` cookies carry just enough to reconstruct context on the
Worker; the Worker adds `X-Odusite-Token` and, when present, `Authorization`
before proxying to Odoo.

| Cookie | Contents | Lifetime |
|---|---|---|
| `od_access` | JWT access token | 15 min |
| `od_refresh` | refresh token | 30 days |
| `od_cart` | `cart_id:cart_token` | 90 days |
| `od_lang` | language code | 1 year |

The **cart** is stateless with respect to Odoo sessions: it is a draft
`sale.order` addressed by `id` + `access_token`, stored in the `od_cart` cookie.

## Payments

Payments are fully headless. Odoo creates the `payment.transaction`; the
frontend runs the provider's own JS SDK (Stripe Payment Element first); the
provider's webhooks go directly to Odoo's standard webhook routes, which remain
the source of truth. Stripe publishable keys are the only payment secret that
reaches the browser.

## Images & files

The Worker route `/img/**` proxies to Odoo `/web/image/**` with resizing and
long-lived (`immutable`) edge caching keyed by the `unique` checksum. Portal
files and PDFs are streamed through dedicated `/odusite/v1/...` endpoints. Large
attachment filestores can be offloaded to S3/R2 via the `odusite_s3` addon.

## Runtime

- **Odoo** 19.0, Python ≥ 3.10. The addons require no external pip dependencies
  (JWT is implemented with the standard library: `hmac` + `json` + `base64`).
- **Site** Node ≥ 20, pnpm, TypeScript strict, Astro 5, Wrangler.

---

The specifications in the repository's `specs/` directory are the source of
truth and describe every route, model, field and flow in full. This page is a
map; the specs are the territory.
