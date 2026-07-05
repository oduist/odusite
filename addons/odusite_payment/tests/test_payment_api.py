from odoo import Command
from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase

from .common import PaymentFixturesMixin


@tagged('post_install', '-at_install')
class TestPaymentApi(PaymentFixturesMixin, OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls._ensure_chart_of_accounts(cls.company)
        cls.portal_user = cls.create_portal_user(
            login='odusite.payment@example.com', name='Odusite Payment Tester')
        cls.partner = cls.portal_user.partner_id
        cls.provider, cls.method = cls._enable_test_provider(cls.company)
        cls.invoice = cls._make_invoice(cls.partner, 100.0)
        cls.invoice_token = cls.invoice._portal_ensure_token()

    def _bearer(self):
        return self.make_access_token(self.portal_user)

    def _tx_payload(self, invoice=None, token=None, **overrides):
        invoice = invoice or self.invoice
        payload = {
            'document': f'invoice:{invoice.id}',
            'access_token': token or (
                self.invoice_token if invoice == self.invoice
                else invoice._portal_ensure_token()
            ),
            'provider_id': self.provider.id,
            'payment_method_id': self.method.id,
            'flow': 'redirect',
        }
        payload.update(overrides)
        return payload

    # -- GET /payment/methods -------------------------------------------------

    def test_methods_for_invoice(self):
        response, body = self.api(
            'GET',
            f'/payment/methods?document=invoice:{self.invoice.id}'
            f'&access_token={self.invoice_token}')
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        providers = {provider['id']: provider for provider in data['providers']}
        self.assertIn(self.provider.id, providers)
        entry = providers[self.provider.id]
        self.assertEqual(entry['code'], self.provider.code)
        self.assertEqual(entry['state'], 'test')
        self.assertEqual(entry['inline'], {})  # Stripe-only key.
        method_ids = [method['id'] for method in entry['payment_methods']]
        self.assertIn(self.method.id, method_ids)

        self.assertEqual(data['amount'],
                         {'amount': 100.0, 'currency': self.invoice.currency_id.name})
        self.assertEqual(data['document'], {
            'type': 'invoice',
            'id': self.invoice.id,
            'state': 'posted',
            'payment_state': 'not_paid',
        })
        # Saved tokens are JWT-only.
        self.assertEqual(data['tokens'], [])

    def test_methods_document_errors(self):
        response, body = self.api('GET', '/payment/methods')
        self.assert_api_error(response, body, 400, 'bad_request')

        response, body = self.api('GET', '/payment/methods?document=invoice:abc')
        self.assert_api_error(response, body, 400, 'bad_request')

        response, body = self.api('GET', '/payment/methods?document=starship:1')
        self.assert_api_error(response, body, 400, 'bad_request')
        self.assertIn('invoice', body['error']['details']['allowed'])

        # Guest with a wrong document token: access denied.
        response, body = self.api(
            'GET',
            f'/payment/methods?document=invoice:{self.invoice.id}&access_token=wrong')
        self.assert_api_error(response, body, 403, 'forbidden')

        response, body = self.api(
            'GET', '/payment/methods?document=invoice:99999999&access_token=x')
        self.assert_api_error(response, body, 404, 'not_found')

    # -- POST /payment/transactions ---------------------------------------------

    def test_transaction_create_redirect_flow(self):
        response, body = self.api('POST', '/payment/transactions', self._tx_payload())
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertTrue(data['transaction_id'])
        self.assertTrue(data['reference'])
        self.assertEqual(data['provider_code'], self.provider.code)
        self.assertEqual(data['flow'], 'redirect')
        self.assertEqual(data['state'], 'draft')
        # Provider code 'none' has no rendering values: empty redirect data.
        self.assertEqual(data['processing_values'],
                         {'redirect_url': None, 'form_data': {}})

        tx = self.env['payment.transaction'].browse(data['transaction_id'])
        self.assertTrue(tx.exists())
        self.assertEqual(tx.invoice_ids, self.invoice)
        self.assertEqual(tx.amount, 100.0)
        self.assertEqual(tx.partner_id, self.invoice.partner_id)
        self.assertEqual(tx.operation, 'online_redirect')

    def test_transaction_amount_validation(self):
        # A matching client-side amount is accepted...
        response, body = self.api('POST', '/payment/transactions',
                                  self._tx_payload(amount=100.0))
        self.assertEqual(response.status_code, 200, body)

        # ...a tampered one is rejected (on a fresh invoice: the first
        # transaction of this test stays draft, i.e. not live, so only the
        # amount check can fail here).
        response, body = self.api('POST', '/payment/transactions',
                                  self._tx_payload(amount=55.0))
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(body['error']['details']['fields']['amount'],
                         'amount_mismatch')

    def test_transaction_blocked_by_live_sibling(self):
        response, body = self.api('POST', '/payment/transactions', self._tx_payload())
        self.assertEqual(response.status_code, 200, body)
        tx = self.env['payment.transaction'].browse(body['data']['transaction_id'])

        # A pending transaction blocks a second one.
        tx._set_pending()
        response, body = self.api('POST', '/payment/transactions', self._tx_payload())
        self.assert_api_error(response, body, 409, 'conflict')

        # A done transaction blocks as well (even before reconciliation
        # actually marks the invoice paid).
        tx._set_done()
        response, body = self.api('POST', '/payment/transactions', self._tx_payload())
        self.assert_api_error(response, body, 409, 'conflict')

    def test_transaction_zero_amount_paid_invoice(self):
        invoice = self._make_invoice(self.partner, 60.0)
        token = invoice._portal_ensure_token()
        self._register_full_payment(invoice)
        self.assertEqual(invoice.amount_residual, 0.0)

        response, body = self.api('POST', '/payment/transactions',
                                  self._tx_payload(invoice=invoice, token=token))
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['state'], 'done')
        self.assertTrue(data['zero_amount'])
        self.assertEqual(data['document']['type'], 'invoice')
        self.assertIn(data['document']['payment_state'], ('in_payment', 'paid'))
        # No transaction was created for the zero-amount document.
        self.assertFalse(self.env['payment.transaction'].search(
            [('invoice_ids', 'in', invoice.ids)]))

    def test_transaction_invalid_inputs(self):
        response, body = self.api('POST', '/payment/transactions',
                                  self._tx_payload(flow='magic'))
        self.assert_api_error(response, body, 400, 'bad_request')

        response, body = self.api('POST', '/payment/transactions',
                                  self._tx_payload(provider_id=99999999))
        self.assert_api_error(response, body, 400, 'bad_request')

        response, body = self.api('POST', '/payment/transactions',
                                  self._tx_payload(payment_method_id=99999999))
        self.assert_api_error(response, body, 400, 'bad_request')

        # Token flow requires token_id.
        response, body = self.api('POST', '/payment/transactions',
                                  self._tx_payload(flow='token'))
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_transaction_for_sent_order(self):
        # The 'order' resolver ships with odusite_payment but only activates
        # when sale is installed.
        if 'sale.order' not in self.env:
            self.skipTest('sale is not installed')
        product = self.env['product.product'].create({
            'name': 'Odusite Payable Service',
            'type': 'service',  # only_services: no delivery gate in readiness.
            'list_price': 40.0,
            'taxes_id': [Command.clear()],
        })
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'require_payment': True,
            'order_line': [Command.create({
                'product_id': product.id,
                'product_uom_qty': 1,
            })],
        })
        order.write({'state': 'sent'})
        token = order._portal_ensure_token()

        response, body = self.api('POST', '/payment/transactions', {
            'document': f'order:{order.id}',
            'access_token': token,
            'provider_id': self.provider.id,
            'payment_method_id': self.method.id,
            'flow': 'redirect',
        })
        self.assertEqual(response.status_code, 200, body)
        tx = self.env['payment.transaction'].browse(body['data']['transaction_id'])
        self.assertEqual(tx.sale_order_ids, order)
        self.assertEqual(tx.amount, 40.0)

    # -- GET /payment/transactions/<id> ---------------------------------------

    def test_transaction_status_poll(self):
        response, body = self.api('POST', '/payment/transactions', self._tx_payload())
        self.assertEqual(response.status_code, 200, body)
        tx_id = body['data']['transaction_id']

        # Guest with the document access token.
        response, body = self.api(
            'GET', f'/payment/transactions/{tx_id}?access_token={self.invoice_token}')
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['state'], 'draft')
        self.assertFalse(data['is_post_processed'])
        self.assertEqual(data['document']['type'], 'invoice')
        self.assertEqual(data['document']['id'], self.invoice.id)

        # JWT user owning the transaction partner: no token needed.
        response, body = self.api('GET', f'/payment/transactions/{tx_id}',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)

        # Wrong/missing token as guest: existence is not leaked (404).
        response, body = self.api(
            'GET', f'/payment/transactions/{tx_id}?access_token=wrong')
        self.assert_api_error(response, body, 404, 'not_found')
        response, body = self.api('GET', f'/payment/transactions/{tx_id}')
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api(
            'GET', f'/payment/transactions/99999999?access_token={self.invoice_token}')
        self.assert_api_error(response, body, 404, 'not_found')

    # -- /payment/tokens ---------------------------------------------------------

    def test_tokens_list_and_archive(self):
        token = self.env['payment.token'].create({
            'provider_id': self.provider.id,
            'payment_method_id': self.method.id,
            'partner_id': self.partner.id,
            'provider_ref': 'odusite-test-ref',
            'payment_details': '4242',
        })

        response, body = self.api('GET', '/payment/tokens')
        self.assert_api_error(response, body, 401, 'unauthorized')

        response, body = self.api('GET', '/payment/tokens', bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        entries = {entry['id']: entry for entry in body['data']}
        self.assertIn(token.id, entries)
        entry = entries[token.id]
        self.assertEqual(entry['provider_id'], self.provider.id)
        self.assertEqual(entry['payment_details'], '4242')
        self.assertEqual(entry['payment_method']['id'], self.method.id)

        # The methods endpoint lists the saved token for the JWT user too.
        response, body = self.api(
            'GET',
            f'/payment/methods?document=invoice:{self.invoice.id}'
            f'&access_token={self.invoice_token}',
            bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        self.assertIn(token.id, [entry['id'] for entry in body['data']['tokens']])

        # DELETE archives the token.
        response, _body = self.api('DELETE', f'/payment/tokens/{token.id}',
                                   bearer=self._bearer())
        self.assertEqual(response.status_code, 204)
        self.env.invalidate_all()
        self.assertFalse(token.active)

        # An archived token behaves as missing.
        response, body = self.api('DELETE', f'/payment/tokens/{token.id}',
                                  bearer=self._bearer())
        self.assert_api_error(response, body, 404, 'not_found')

    def test_token_delete_other_partner(self):
        other_partner = self.env['res.partner'].create(
            {'name': 'Odusite Other Token Owner'})
        foreign_token = self.env['payment.token'].create({
            'provider_id': self.provider.id,
            'payment_method_id': self.method.id,
            'partner_id': other_partner.id,
            'provider_ref': 'odusite-foreign-ref',
        })
        response, body = self.api('DELETE', f'/payment/tokens/{foreign_token.id}',
                                  bearer=self._bearer())
        self.assert_api_error(response, body, 404, 'not_found')
        self.env.invalidate_all()
        self.assertTrue(foreign_token.active)
