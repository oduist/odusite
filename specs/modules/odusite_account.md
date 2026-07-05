# odusite_account

Depends: `odusite_base`, `odusite_portal`, `odusite_payment`, `account`.
Portal invoices.

## Endpoints (JWT; detail also via `?access_token=`)

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/my/invoices` | GET | Paginated `account.move` (move_type in out_invoice/out_refund, state=posted; drafts excluded). Filters: `?state=open\|paid\|overdue`. Item: `{id, name, invoice_date, invoice_date_due, amount_total, amount_residual, currency, payment_state, is_overdue}`. |
| `/odusite/v1/my/invoices/<id>` | GET | Detail: header + lines `[{name, quantity, price_unit, price_subtotal, taxes}]`, totals, `requires_payment` (residual>0 & providers available), `pdf_url`. |
| `/odusite/v1/my/invoices/<id>/pdf` | GET | Streams the legal invoice PDF (`_get_invoice_legal_documents_all` fallback to rendered report). |

Payment: through `odusite_payment` with `document: "invoice:<id>"`.
Chatter: `account.move` in the whitelist. Counter: `invoices` (+ overdue count
in `/me/counters` details).

## Webhooks / sitemap

None (portal-only module).

## Site part

Portal block section `/portal/invoices[/id]`: list with status chips
(paid/open/overdue), detail with lines, Pay button (PaymentSheet), PDF
download.
