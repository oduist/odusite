# API Conventions

## Transport

- Base: `POST|GET|PUT|DELETE https://<odoo>/odusite/v1/...`
- Request/response bodies are JSON (`Content-Type: application/json`),
  except file uploads (`multipart/form-data`) and binary downloads.
- Routes are implemented via the `odusite_route` helper from `odusite_base`
  (`type='http'`, `auth='public'`, `csrf=False`, explicit `methods`).

## Headers

| Header | Required | Purpose |
|---|---|---|
| `X-Odusite-Token` | yes | shared secret (env `ODUSITE_TOKEN` ↔ system param `odusite.token`) |
| `Authorization: Bearer <jwt>` | no | portal user context |
| `X-Odusite-Cart` | no | `"<cart_id>:<cart_token>"` — guest cart binding |
| `Accept-Language` / `?lang=` | no | response language (`ru_RU`, `en_US`, …) |

## Response format

Success: `{"data": <object|array>, "meta": {...}}` — `meta` present on lists.
Error: HTTP status + `{"error": {"code": "<machine_code>", "message": "<text>", "details": {}}}`.

Statuses: 200/201, 400 `bad_request`, 401 `unauthorized` (token) /
`invalid_jwt` / `jwt_expired`, 403 `forbidden`, 404 `not_found`,
409 `conflict` (e.g. `mfa_required`), 422 `validation_error`
(`details.fields` — per-field errors), 429, 500 `internal` (no internals leaked).

## Lists: pagination, search, sorting

`?page=1&limit=20&search=<string>&order=<key>` —
`meta: {total, page, limit, pages}`. `limit` ≤ 100. `order` keys come from a
per-endpoint whitelist (like searchbar_sortings in the Odoo portal).

## Common field conventions

- Identifiers — `id` (int). Slugs — `slug` (generated like Odoo:
  `<name>-<id>`); detail endpoints accept both id and slug.
- Dates — ISO 8601 UTC (`"2026-07-05T12:00:00Z"`); date-only — `YYYY-MM-DD`.
- Money: `{"amount": 123.45, "currency": "EUR"}` or `amount_*` fields +
  `currency` on the object.
- Images: the `image` field is a relative path
  `/web/image/<model>/<id>/<field>/<WxH>?unique=<hash>` — the site rewrites it
  to its `/img/**` proxy. HTML fields (`content`) are returned as safe HTML;
  URLs inside are already rewritten for the proxy.
- SEO block on every detail entity:
  `seo: {title, description, keywords, og_image}` (from `website_meta_*`).
- Publishing: only `is_published=True` records are exposed (+ website_id
  filter, + publish date ≤ now). The `is_published` field itself is not exposed.

## Execution context in Odoo

- Without JWT: `env` of the website user (public user), with `sudo()` only where
  the stock controller does the same.
- With JWT: `request.update_env(user=uid)` — portal record rules apply.
- Invalid/expired Bearer tokens on public endpoints degrade to anonymous;
  only `auth_user` endpoints answer 401 (`invalid_jwt`/`jwt_expired`).
- Language: activated from `?lang`/`Accept-Language` if enabled on the website.

## Versioning

`/v1` prefix. Breaking changes → `/v2` (both supported during migration).
