# Architecture Decision Records

Format: context → decision → consequences. Add new entries at the bottom.

## ADR-001 — Odoo as headless backend, Astro frontend
Context: Odoo's website rendering (QWeb + snippets) is tightly coupled to its
session/asset pipeline and cannot be reused in a modern edge-deployed frontend.
Decision: all public UX is rebuilt in Astro; Odoo exposes REST controllers only
(`odusite_*` addons inheriting stock modules).
Consequences: full control of frontend; every needed Odoo feature must get an
explicit API; Odoo upgrades only affect the API layer.

## ADR-002 — Shared-secret header `X-Odusite-Token`
Context: site↔Odoo traffic is strictly server-to-server (Worker → Odoo).
Decision: one shared secret in the `X-Odusite-Token` header (env
`ODUSITE_TOKEN`, system param `odusite.token`), constant-time compared;
all `/odusite/...` routes require it.
Consequences: Odoo API is unreachable without the secret; browser never calls
Odoo; secret rotation = update both sides.

## ADR-003 — Portal auth via Odoo-issued JWT (no sessions)
Context: Odoo's portal is session-cookie based; sessions don't fit an edge SSR
frontend and MFA-less JSON login exists but binds to server-side session store.
Decision: `odusite_portal` issues HS256 access JWT (15 min) + rotating hashed
refresh tokens (30 days) stored in Odoo; Worker keeps them in httpOnly cookies.
Consequences: stateless request auth (`request.update_env(user=uid)`); explicit
revocation list; MFA/passkeys deferred to phase 2 (login returns `mfa_required`).

## ADR-004 — Fully headless payments, Stripe first
Context: user chose seamless on-site payments over redirecting to Odoo's
payment page. Odoo's payment engine already models providers/transactions.
Decision: odusite_payment wraps transaction creation and status; frontend runs
provider JS (Stripe Payment Element); PSP webhooks keep hitting stock Odoo
routes; site polls tx state.
Consequences: each provider is integrated one-by-one on the site; PCI stays
with the PSP; Odoo remains the source of truth for tx state and order
confirmation.

## ADR-005 — Hybrid SSR on Cloudflare Workers
Context: e-commerce + portal need fresh data and privacy; marketing pages need
speed; SSG rebuilds on every content change don't scale.
Decision: Astro SSR on Workers; marketing pages prerendered; public dynamic
pages edge-cached with tag-based invalidation via Odoo webhooks; cart/portal
never cached.
Consequences: one deployment; webhook + tag discipline required
(`06-cache-invalidation.md`).

## ADR-006 — Marketing pages authored in Astro, not in Odoo
Context: Odoo's page builder outputs QWeb/HTML tied to its assets; replicating
the builder headlessly is a large separate product.
Decision: marketing/landing pages are Astro content (git-versioned);
Odoo supplies entity data only. `website.page` is not exposed.
Consequences: content editors work via git/PR (or later a headless CMS block);
existing Odoo page content must be migrated manually once.

## ADR-007 — Stateless cart bound by id + access_token
Context: stock website_sale binds the cart to the Odoo session
(`session['sale_order_id']`); we have no Odoo sessions.
Decision: cart = draft sale.order; `POST /shop/cart` returns
`{id, token}` (token = `sale.order.access_token`); all cart ops require the
`X-Odusite-Cart` header; on login the cart is claimed for the user's partner.
Consequences: carts survive across devices via cookie only; abandoned-cart
logic keys on orders, not sessions; token check on every mutation.

## ADR-008 — No external Python deps in addons
Context: deployment simplicity; Odoo hosts often restrict pip installs.
Decision: JWT/HMAC implemented with the Python stdlib.
Consequences: no RS256/JWKS; HS256 only (acceptable: single issuer=verifier).

## ADR-009 — Images proxied through the site's `/img/**`
Context: Odoo's `/web/image` already does resize + immutable caching via
`unique` checksums, but exposing the Odoo host leaks infrastructure.
Decision: API returns `/web/image/...` relative URLs; the Worker serves them
under `/img/**`, proxying to Odoo with edge caching.
Consequences: single image pipeline, no re-implementation of resize; Odoo
stays hidden behind the site domain.

## ADR-010 — English for code, specs and docs
Context: initially specs were started in Russian; the owner requires English
artifacts (conversation stays in Russian).
Decision: all repo artifacts (code, comments, specs, docs, commits) in English.
Consequences: earlier Russian drafts rewritten.
