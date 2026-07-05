# odusite_partner

Depends: `odusite_base`, `website_partner`. Optional enrichment when
`website_customer` / `website_crm_partner_assign` are installed (references,
grades). Public partner directory ("Our customers" / "Resellers").

## Endpoints

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/partners` | GET | Paginated published partners. Filters: `?kind=customers\|resellers&country=&grade=&tag=&search=`. `customers`: published + `assigned_partner_id` set (website_customer semantics) or plain published companies when website_customer absent. `resellers`: published + grade set. Item: `{id, slug, name, logo, short_description, city, country, grade?, tags[{id, name, class}]}`. `meta.facets`: countries (+counts), grades. |
| `/odusite/v1/partners/<id_or_slug>` | GET | Detail: + `description_html` (website_description), website url, industry, implemented references `[{id, slug, name}]` (when assign module installed), `seo`. |

## Webhooks / sitemap

Watched: `res.partner` publish flag / website fields only (guarded — partner
writes are frequent; enqueue only when watched fields change).
Tags: `partners`, `partners:<id>`. Sitemap: `/partners/<slug>`.

## Site block `partners`

`/partners` (logo grid, country/grade filters, search), `/partners/[partner]`
(profile page). Optional world-map view deferred (no Google Maps in v1).
