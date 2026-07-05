# Payments (fully headless)

Implemented in `odusite_payment` on top of the `payment` core (+ `account_payment`).
First provider — **Stripe** (`payment_stripe`); others are added with the same
scheme as needed.

## Flow (order, invoice, any payable document)

1. The site requests `GET /odusite/v1/payment/methods?document=<type>:<id>` →
   compatible providers/methods/saved tokens
   (wraps `payment.provider._get_compatible_providers` and
   `payment.method._get_compatible_payment_methods`);
   for Stripe the response includes `publishable_key`.
2. The site creates a transaction: `POST /odusite/v1/payment/transactions`
   `{document: "order:<id>" | "invoice:<id>", access_token, provider_id,
   payment_method_id, flow: "direct"|"redirect"|"token", token_id?, tokenize?}`.
   Odoo validates the amount/document readiness (like `/shop/payment/transaction`)
   and returns `{transaction_id, reference, processing_values}`.
   For Stripe direct, `processing_values` contains the PaymentIntent `client_secret`.
3. The frontend runs the provider JS (Stripe Payment Element →
   `stripe.confirmPayment`, `return_url` = site page
   `/shop/payment/return?tx=<id>`).
4. Provider webhooks go **directly to Odoo** on the stock routes
   (`/payment/stripe/webhook`) — they are public and don't require X-Odusite-Token.
5. The site polls `GET /odusite/v1/payment/transactions/<id>?access_token=...` →
   `{state: draft|pending|authorized|done|cancel|error, state_message,
   document_state}`. `done`/`authorized` → Odoo has already confirmed the order
   (stock `_post_process`); the site shows the confirmation page.

## Requirements

- Redirect providers: `processing_values.redirect_form_html` is not used;
  instead the endpoint returns `redirect_url` + POST params and the site
  auto-submits them itself (data from `_get_specific_rendering_values`).
- Saved methods (`payment.token`): list/delete —
  `GET/DELETE /odusite/v1/payment/tokens` (JWT only).
- Zero-amount orders are confirmed without a transaction
  (like `/shop/payment/validate`).
- Amount validation: compared with the document's `amount_total` at tx creation;
  creating a tx on top of a live one is forbidden (website_sale pattern).
- No donation flow in v1.

## Configuration

- Providers are configured in Odoo as usual (state=enabled/test,
  publishable/secret keys for Stripe). `odusite_payment` stores nothing itself.
- In Astro, `STRIPE_PUBLISHABLE_KEY` is optional — the key arrives via the API.
