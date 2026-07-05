# odusite_payment

Depends: `odusite_base`, `payment`, `account_payment`. Optional bridge:
`payment_stripe` (first supported provider). See `../04-payments.md` for the
end-to-end flow and requirements.

## Document resolvers

Registry `odusite.payable.documents`: `"order" → sale.order`,
`"invoice" → account.move` (registered by odusite_sale / odusite_account).
Each resolver provides: browse+token check, `amount_due`, readiness check
(`_check_cart_is_ready_to_be_paid` for orders; posted & residual > 0 for
invoices), `custom_create_values` (`sale_order_ids` / `invoice_ids`),
post-payment state summary.

## Endpoints

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/payment/methods` | GET | `?document=order:<id>&access_token=` → `{providers: [{id, code, name, state(test?), payment_methods[{id, code, name, image}], support_tokenization, inline: {publishable_key?}}], tokens: [{id, provider_id, payment_details, payment_method}] (JWT only)}`. |
| `/odusite/v1/payment/transactions` | POST | Create tx (see 04-payments). Validates: document ready, amount == amount_due, no live sibling tx. Returns `{transaction_id, reference, provider_code, flow, processing_values}` — for stripe direct: `{client_secret, publishable_key}`; for redirect providers: `{redirect_url, form_data}`. |
| `/odusite/v1/payment/transactions/<id>` | GET | `?access_token=<document token>` → `{state, state_message, is_post_processed, document: {type, id, state}}`. |
| `/odusite/v1/payment/tokens` | GET/DELETE | JWT. Saved payment methods list / archive (`/payment/archive_token` equivalent). |

## Stripe integration notes

- Uses `payment_stripe` provider internals to create the PaymentIntent for a
  transaction in `direct` flow and expose its `client_secret`
  (equivalent of the stock inline flow, without Odoo JS).
- Webhook stays stock: `/payment/stripe/webhook` (configure endpoint secret in
  the provider form). `/payment/stripe/return` unused by the headless flow.
- `return_url` for `stripe.confirmPayment` is a **site** URL; final state is
  read via the tx polling endpoint (webhook-driven server truth).

## Webhooks / sitemap

None (transactional module).

## Site part

Shared payment UI in the `shop` and `portal` blocks:
`<PaymentSheet document="order:<id>">` — loads methods, creates tx, mounts
Stripe Payment Element (or auto-submit redirect form), then redirects to the
confirmation page which polls tx status.
