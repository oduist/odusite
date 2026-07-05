# odusite_sale

Depends: `odusite_base`, `odusite_portal`, `website_sale` (brings `sale`,
`delivery` engine via website_sale). The largest module: catalog, cart,
checkout, portal orders.

## Catalog

Data: `product.template` (+variants), `product.public.category`,
`product.pricelist`, combination info (`_get_combination_info`) as the single
pricing/availability source. Pricelist/fiscal position resolved per request:
website default pricelist (guest) or partner pricelist (JWT), fiscal position
from partner country (JWT) else website company country. No GeoIP in v1.

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/shop/categories` | GET | Category tree: `{id, slug, name, parent_id, children[], product_count, cover}`. |
| `/odusite/v1/shop/products` | GET | Paginated listing. Filters: `?category=&search=&min_price=&max_price=&tags=&attribs=<attr>-<val>,...`. Item: `{id, slug, name, list_price, price, has_discounted_price, currency, rating?, image, second_image?, tags[], category_ids[]}` (prices from `_get_sales_prices`). Order whitelist: `relevance`, `price_asc`, `price_desc`, `name`, `newest`. Response `meta.facets`: attributes + value counts for the current result set. |
| `/odusite/v1/shop/products/<id_or_slug>` | GET | Detail: name, description_html (`website_description`/`description_ecommerce`), images (main + `product_template_image_ids`), attribute lines (`{attribute, display_type, values[{id, name, html_color, price_extra}]}`), combination info of the default variant, alternatives, accessories, documents `[{id, name, url}]`, `seo`, JSON-LD payload. |
| `/odusite/v1/shop/products/<id>/combination` | POST | `{combination: [ptav_ids], quantity}` → combination info: `{product_id, price, list_price, has_discounted_price, currency, display_name, image, is_combination_possible, ...stock fields when website_sale_stock installed}`. |

## Cart (stateless — ADR-007)

Cart = draft `sale.order` addressed by `X-Odusite-Cart: <id>:<access_token>`.
Server verifies token (consteq) + state=draft + website match on every call.
Uses stock cart methods: `_cart_add`, `_cart_update_line_quantity`,
`_verify_cart_after_update`.

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/shop/cart` | POST | Create cart (guest: partner = website public partner; JWT: user partner + pricelist). → `{id, token}`. |
| `/odusite/v1/shop/cart` | GET | Cart contents: lines `[{id, product: {id, slug, name, image}, description, quantity, price_unit, price_subtotal, price_total}]`, amounts `{untaxed, tax, delivery, total, currency}`, `tax_mode: included\|excluded` (website `show_line_subtotals_tax_selection`), reward/delivery lines flagged. |
| `/odusite/v1/shop/cart/lines` | POST | Add: `{product_id?, product_template_id, combination?, quantity, no_variant_attribute_value_ids?, custom_values?}` → updated cart summary + `line_id`, warnings (stock clamp). |
| `/odusite/v1/shop/cart/lines/<line_id>` | PUT/DELETE | Change quantity / remove. |
| `/odusite/v1/shop/cart/claim` | POST | JWT required. Re-assigns a guest cart to the logged-in partner (`_update_address` partner swap; existing draft cart of the user is merged). |

## Checkout

State machine mirrors `/shop/checkout`→`/shop/payment` guards
(`_check_cart`, address completeness, delivery selected when deliverable).

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/shop/checkout` | GET | Current checkout state: `{cart_ok, addresses: {billing, delivery}, needs_delivery, delivery_methods: [{id, name, description, price, currency, free_over?}], selected_delivery_id, payment_ready, errors[]}`. |
| `/odusite/v1/shop/checkout/address` | POST | Guest checkout address (creates/updates partner like `/shop/address/submit`; guest → new partner with `parent_id=False`, linked to order only). Body: `{address_type, use_delivery_as_billing, fields...}`. |
| `/odusite/v1/shop/checkout/delivery` | PUT | `{delivery_method_id}` → `set_delivery_line` via `_set_delivery_method`, returns recomputed amounts. |
| `/odusite/v1/shop/orders/<id>/confirmation` | GET | Post-payment confirmation data (token-gated): order summary for the thank-you page. |

Payment step is handled by `odusite_payment`
(`document: "order:<id>"` + cart token as access_token).

## Portal orders (JWT)

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/my/orders` | GET | Paginated, `?state=quotes\|orders` (quotes: state=sent; orders: state=sale/done). Item: `{id, name, date_order, state, amount_total, currency, invoice_status}`. |
| `/odusite/v1/my/orders/<id>` | GET | Detail (JWT rules or `?access_token=`): header, lines, amounts, `can_accept`, `can_decline`, `requires_payment`, delivery address, expected_date, linked invoices refs, `pdf_url`. |
| `/odusite/v1/my/orders/<id>/accept` | POST | `{name, signature(base64 png), access_token?}` → stock sign flow (`signed_by/on/signature`, validates order when no payment required). |
| `/odusite/v1/my/orders/<id>/decline` | POST | `{reason}` → cancel + chatter message. |
| `/odusite/v1/my/orders/<id>/pdf` | GET | Streams the sale order PDF report (JWT or access_token). |

Chatter: `sale.order` registered in the chatter whitelist; the addon sets
`_mail_post_access = 'read'` on sale.order (like account.move/project.task)
so portal customers can comment on their own orders.
Counters: `orders`, `quotes`.

## Webhooks / sitemap

Watched: `product.template` (name, prices, publish, images, categories),
`product.public.category`. Tags `shop`, `shop:<tmpl_id>`, `shop-cat:<id>`.
Sitemap: `/shop/<product_slug>` + category pages.

## Site block `shop`

`/shop` (grid, facets, sort, pagination), `/shop/[category]`,
`/shop/[product]` (gallery, variant picker calling combination endpoint,
add to cart), `/cart`, `/checkout` (address → delivery → payment (Stripe
Element) → confirmation), portal section `/portal/orders[/id]` with sign/
decline/pay actions. Cart badge in header (server island).
