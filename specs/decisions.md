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

## ADR-008 — Minimal external Python deps in addons
Context: deployment simplicity; Odoo hosts often restrict pip installs.
Decision: JWT/HMAC implemented with the Python stdlib. The one sanctioned
external dependency is **boto3** in `odusite_s3` (ADR-012): a hand-rolled S3
SigV4 client is too risky for production object storage, and boto3 is the
industry standard (works with AWS S3 and Cloudflare R2). It is declared in the
addon manifest `external_dependencies` so Odoo warns when it is missing; no
other addon may add pip dependencies.
Consequences: JWT stays stdlib-only (HS256, single issuer=verifier); object
storage relies on boto3 where installed.

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

## ADR-011 — Portal identity via signed JWT, not a trusted `X-User-ID` header
Context: an alternative "trusted subsystem" design was considered (the SSR
worker asserts the caller with a plain `X-User-ID` header and Odoo switches
context with `with_user()`, trusting it because the request carries the master
token). Both models end up filtering data with Odoo Record Rules; they differ
only in how the user identity is established.
Decision: keep the JWT model (ADR-003). The user id is carried inside an
HS256-signed access token that Odoo re-verifies on every request in
`odusite_route` before `update_env(user=uid)`; identity cannot be forged
without `odusite.jwt_secret`. `X-User-ID` would make identity *asserted* rather
than *proven*, collapsing security onto the single assumption that nothing with
the master token ever emits a wrong id.
Consequences: stronger identity (two independent secrets: master token +
jwt_secret; tamper-proof, short-lived, revocable). A trusted `X-User-ID` path
may be added later **only** for server-side agents that legitimately act for a
user without a browser session — behind the master token, explicitly logged,
never replacing JWT for browser users.

## ADR-012 — Object storage offload to S3/R2 (`odusite_s3`)
Context: the ТЗ mandates that media and documents served to the frontend live
on S3-compatible storage (Cloudflare R2, zero egress), not in Odoo's local
filestore. In Odoo every binary (product images, blog/event covers, generated
PDFs, uploaded CVs/attachments) is an `ir.attachment`, which exposes clean
`_storage/_file_read/_file_write/_file_delete` hooks.
Decision: a new addon `odusite_s3` offloads the `ir.attachment` filestore to
S3/R2 via those hooks (boto3). It **adopts the production techniques of an
internal reference module** (`s3_attachment`) rather than a naive first cut:
- **`s3://` storage marker** in `store_fname` (not an `_storage()` override):
  per-record, self-describing storage; local and S3 files coexist and reads
  route on the prefix. The offload decision is taken in
  `_get_datas_related_values` where mimetype **and** size are known.
- **Selective** offload: content goes to S3; backend web-asset bundles (JS/CSS)
  and small images stay local so the admin UI isn't slowed by per-request S3
  reads; extra keep-local mimetype prefixes are configurable.
- **Deferred, reference-counted GC**: `_file_delete` queues into an
  `odusite.s3.gc` table in a separate cursor (survives rollback — object stores
  aren't transactional); an autovacuum deletes an object only when no attachment
  still references its key (dedup-safe).
- **Throttled background migration** of the existing filestore: a threaded cron
  (network I/O off the DB), keyset-paginated, with a tz-aware time window,
  Start/Stop, concurrent-update retries, an unhealthy-source guard, and a direct
  SQL `store_fname` swap that bypasses sibling modules' ORM write hooks.
- **Presigned URLs** for private documents, plus an **`ir.http` 302 redirect**
  of `/web/content` and `/web/image` originals straight to a presigned URL after
  the standard access check (resize falls through to read-from-S3).
- Public images use **hybrid** delivery: the API exposes the direct R2/CDN URL
  of the original; the `/img` proxy stays for on-the-fly resized variants.
- **Secrets from `odoo.conf`/env first**, DB params as a fallback (UI stays
  usable for testing; production can keep credentials out of the DB).
Consequences: media/documents scale independently of Odoo; bandwidth leaves
Odoo/worker for public originals and private downloads; requires boto3
(ADR-008) and R2/S3 credentials configured in conf/env or Odoo settings.
Complements — does not replace — ADR-009 (`/img` proxy remains for resizing).
