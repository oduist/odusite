# odusite_base

Depends: `website`, `portal`. The foundation every other odusite addon builds on.

## Responsibilities

1. **Token gate + route helper.** `odusite_route(path, methods, auth_user=False,
   paginated=False)` decorator/helper wrapping Odoo `http.route`:
   - verifies `X-Odusite-Token` against system param `odusite.token`
     (constant-time; missing/param unset → 401);
   - parses JSON body into kwargs, serializes returned dicts to JSON envelope
     (`{"data":...}` / `{"error":...}`), maps exceptions
     (ValidationError→422, AccessError→403, MissingError→404, others→500 logged);
   - resolves `Authorization: Bearer` JWT (verify signature/exp; on success
     `request.update_env(user=uid)`; `auth_user=True` → 401 without valid JWT);
   - activates language from `?lang`/`Accept-Language` (must be enabled on the
     website), binds the configured website
     (`odusite.website_id` param or default) into the context;
   - standard pagination parsing (`page`, `limit`, `search`, `order` whitelist).
2. **JWT utils** (stdlib): sign/verify HS256; secret system param
   `odusite.jwt_secret` auto-generated on install (`post_init_hook`), same for
   `odusite.token` (so an admin can copy it, not invent it).
3. **Serialization helpers**: `image_url(record, field, size)` (with `unique`
   checksum from write_date), `seo(record)` dict, `money(amount, currency)`,
   `html_field(record, field)` (returns sanitized HTML with `/web/image` URLs
   left relative), slug helpers (Odoo-compatible slug/unslug).
4. **Webhooks/cache invalidation**: mixin `odusite.watched.mixin` + queue model
   `odusite.webhook.event` + cron sender (see `../06-cache-invalidation.md`).
5. **Site-wide endpoints.**

## Models

- `odusite.webhook.event` — see `06-cache-invalidation.md`.
- `res.config.settings` extension (Website settings block "Odusite"):
  `odusite_token`, `odusite_site_url`, `odusite_revalidate_secret`,
  `odusite_website_id` — stored as system parameters
  (`odusite.token`, `odusite.site_url`, `odusite.revalidate_secret`,
  `odusite.website_id`).

## Endpoints

| Route | Method | Auth | Description |
|---|---|---|---|
| `/odusite/v1/site` | GET | token | Site config bundle: name, company (name, address, VAT, email, phone), logo/favicon image URLs, social links, default + available languages `[{code, url_code, name}]`, currency, menus (see below). Cached tag `site`. |
| `/odusite/v1/menus` | GET | token | Website menu tree (`website.menu`): `{id, name, url, new_window, sequence, children[]}`; mega-menu entries flattened to plain links; group-restricted menus excluded unless JWT user has access. |
| `/odusite/v1/sitemap` | GET | token | Aggregated `[{url, lastmod}]` of all published entities; each odusite module contributes via a `_odusite_sitemap()` hook registry. |
| `/odusite/v1/redirects` | GET | token | `website.rewrite` records: `[{from, to, type: 301|302}]`. |
| `/odusite/v1/countries` | GET | token | `[{id, code, name, states[{id, code, name}], zip_required, state_required}]` for address forms (mirrors `/my/address/country_info`). |
| `/odusite/v1/health` | GET | token | `{status: "ok", version}` — deploy smoke check. |
| `/odusite/v1/search` | GET | token | Unified site search (`?q=&types=<csv of model names>&limit=`), wraps `website._search_with_fuzzy(search_type='all')`. Returns `{results: [{type, id, name, url, description?, image?}], fuzzy_term}` + `meta.count`; `url` is the Odoo-style URL (`/shop/…`, `/blog/…`). Empty/missing `q` → 400; unknown `types` are ignored (graceful `[]`). |

## Notes

- No public model is exposed here; content modules register themselves into the
  sitemap and webhook registries.
- Every controller in other odusite modules imports `odusite_route` from this
  addon; direct `@http.route` JSON handling is forbidden by convention.
- `/search` federates whatever `website.searchable.mixin` models are installed
  (products, blog posts, events, jobs, forum, courses, …). Publication and
  website filtering come from the upstream search domains and public record
  rules — the search always runs in the request user's env, never sudo.
  `website.page` results are excluded (marketing pages live in Astro).
