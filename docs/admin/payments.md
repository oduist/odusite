# Payments

Payments are fully headless (see `specs/04-payments.md`): the checkout and
portal render the provider UI on the site, Odoo owns transactions and order
confirmation. Requires the `odusite_payment` addon.

## Stripe (first supported provider)

1. In Odoo: **Invoicing/Website → Configuration → Payment Providers → Stripe**.
   Set the *Publishable Key* and *Secret Key* (test keys first), state
   **Test Mode** or **Enabled**, and publish the provider.
2. Create a Stripe webhook endpoint pointing at
   `https://<odoo>/payment/stripe/webhook` (this is a stock Odoo route and must
   be reachable from the internet). Put the *Webhook Signing Secret* into the
   provider form.
3. Nothing Stripe-specific is configured on the site: the publishable key and
   the PaymentIntent client secret are delivered through the API at checkout
   time. The browser loads `js.stripe.com` directly.

## Flow (what to expect operationally)

1. Site asks Odoo for compatible providers for the document (order/invoice).
2. Site creates a `payment.transaction` through the API; for Stripe the
   response carries the PaymentIntent client secret.
3. Customer pays in the embedded Stripe Payment Element.
4. Stripe notifies Odoo via the webhook; Odoo confirms the order / reconciles
   the invoice exactly as with the stock website.
5. The site polls the transaction state and shows the confirmation page.

Failed/stuck transactions are visible in Odoo under
**Payment Transactions** as usual.

## Other providers

Redirect-based providers (PayPal & co.) are supported by the generic redirect
flow (the site auto-submits the provider form returned by the API), but each
provider should be validated before production use — see the roadmap.
Zero-amount orders confirm without any provider.
