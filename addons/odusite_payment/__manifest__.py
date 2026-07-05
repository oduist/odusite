{
    'name': 'Odusite Payment',
    'summary': 'Headless payment API (providers, transactions, tokens) for the Odusite frontend',
    'description': """
Headless payment flow for the Odusite Astro frontend (see specs/04-payments.md):
- payable-document registry (odusite.payable): invoice + order resolvers
- GET /odusite/v1/payment/methods: compatible providers/methods/saved tokens
- POST /odusite/v1/payment/transactions: create payment.transaction and return
  processing values (Stripe direct: PaymentIntent client_secret)
- GET /odusite/v1/payment/transactions/<id>: transaction state polling
- GET/DELETE /odusite/v1/payment/tokens: saved payment methods (JWT)

Provider webhooks stay on the stock routes (e.g. /payment/stripe/webhook).
No hard dependency on payment_stripe: Stripe specifics are guarded by
provider.code == 'stripe' checks.
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Odusite',
    'license': 'LGPL-3',
    'depends': ['odusite_base', 'payment', 'account_payment'],
    'installable': True,
}
