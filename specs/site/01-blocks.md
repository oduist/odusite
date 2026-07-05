# Astro Site — Blocks

A **block** is a self-contained functional area activated at build time.
Disabled block ⇒ zero routes, zero JS, zero nav items.

## Configuration

`odusite.config.mjs`:
```
export default {
  theme: 'default',
  blocks: { blog: true, shop: true, portal: true, events: true,
            jobs: true, partners: true, forum: false, courses: false,
            forms: true, newsletter: true },
  nav: [...],            // ordered nav definition referencing block routes
}
```
Env overrides at build: `ODUSITE_BLOCK_<NAME>=1|0`, `ODUSITE_THEME=<name>`.

## Mechanics

Custom Astro integration `odusiteBlocks()` (in `site/integrations/blocks.mjs`):
- reads the config, for each enabled block calls `injectRoute()` for the
  block's pages and endpoints (each block ships a route manifest in
  `src/blocks/<name>/manifest.mjs`, plain JS loadable at config time:
  `{routes: [{pattern, entrypoint, prerender?}]}`);
- exposes `virtual:odusite/config` (enabled blocks, theme, nav) to components
  (header/nav/footer render only enabled entries);
- fails the build if a block is enabled but its addon healthcheck is not
  desired — no runtime coupling: the site trusts config, API 404s surface
  as build/SSR errors on those pages only.

## Block contract

`src/blocks/<name>/`
- `manifest.mjs` — route manifest (nav contributions live in odusite.config.mjs).
- `pages/` — `.astro` entrypoints (may mix prerender/SSR per page).
- `components/` — block-local components; must use theme tokens only.
- `api/` — same-origin endpoints for browser islands (proxy to Odoo client),
  injected under `/api/<block>/...`.

## Blocks ↔ addons

| Block | Addon required | Routes (site) |
|---|---|---|
| forms | odusite_crm | `/contact` (+ embeddable form component) |
| newsletter | odusite_mass_mailing | no pages — footer subscribe form + `/api/newsletter/subscribe` endpoint |
| blog | odusite_blog | `/blog`, `/blog/[post]`, `/blog/feed.xml` |
| shop | odusite_sale (+ odusite_payment) | `/shop`, `/shop/[...slug]`, `/cart`, `/checkout/*` |
| portal | odusite_portal (+ account/project/sale for sections) | `/portal/*`, `/login`, `/signup`, `/reset/*` |
| events | odusite_event | `/events`, `/events/[event]` |
| jobs | odusite_hr_recruitment | `/jobs`, `/jobs/[job]` |
| partners | odusite_partner | `/partners`, `/partners/[partner]` |
| forum | odusite_forum | `/forum/*` |
| courses | odusite_slides | `/courses/*` |

Portal sections register themselves similarly *within* the portal block:
orders/invoices/tasks sections appear only when their block flag
(`shop`, `portal.invoices`, `portal.projects`) is on.
