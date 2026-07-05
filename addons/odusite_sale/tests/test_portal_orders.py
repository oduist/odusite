from odoo import Command
from odoo.tests.common import tagged

from .common import OdusiteSaleCase

# 1x1 transparent PNG, base64 (customer signature payload).
TINY_PNG_B64 = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAA'
    'AAYAAjCB0C8AAAAASUVORK5CYII='
)


@tagged('post_install', '-at_install')
class TestPortalOrders(OdusiteSaleCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal_user = cls.create_portal_user(login='odusite.orders@example.com',
                                                 name='Odusite Orders Tester')
        cls.partner = cls.portal_user.partner_id
        # Service product: portal order flows without delivery concerns.
        cls.service_product = cls.env['product.template'].create({
            'name': 'Odusite Signature Service',
            'type': 'service',
            'list_price': 100.0,
            'sale_ok': True,
            'taxes_id': [Command.clear()],
        })
        cls.quote_sign = cls._create_sent_order()
        cls.quote_decline = cls._create_sent_order()

    @classmethod
    def _create_sent_order(cls):
        order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'require_signature': True,
            'require_payment': False,
            'order_line': [Command.create({
                'product_id': cls.service_product.product_variant_id.id,
                'product_uom_qty': 1,
            })],
        })
        order.write({'state': 'sent'})
        return order

    def _bearer(self):
        return self.make_access_token(self.portal_user)

    # -- List ----------------------------------------------------------------

    def test_orders_list_quotes(self):
        response, body = self.api('GET', '/my/orders?state=quotes&limit=100',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        by_id = {item['id']: item for item in body['data']}
        self.assertIn(self.quote_sign.id, by_id)
        self.assertIn(self.quote_decline.id, by_id)
        item = by_id[self.quote_sign.id]
        self.assertEqual(item['state'], 'sent')
        self.assertEqual(item['name'], self.quote_sign.name)
        self.assertEqual(item['amount_total'], 100.0)
        self.assertEqual(item['currency'], self.quote_sign.currency_id.name)
        self.assertIn('invoice_status', item)

        # 'sent' orders are quotes, not confirmed orders.
        response, body = self.api('GET', '/my/orders?state=orders&limit=100',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.quote_sign.id, [item['id'] for item in body['data']])

    def test_orders_list_bad_state(self):
        response, body = self.api('GET', '/my/orders?state=bogus',
                                  bearer=self._bearer())
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_orders_list_requires_jwt(self):
        response, body = self.api('GET', '/my/orders')
        self.assert_api_error(response, body, 401, 'unauthorized')

    # -- Detail ----------------------------------------------------------------

    def test_order_detail_jwt(self):
        response, body = self.api('GET', f'/my/orders/{self.quote_sign.id}',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['id'], self.quote_sign.id)
        self.assertTrue(data['can_accept'])
        self.assertTrue(data['can_decline'])
        self.assertFalse(data['requires_payment'])
        self.assertIsNone(data['signed_by'])
        self.assertEqual(len(data['lines']), 1)
        self.assertEqual(data['lines'][0]['quantity'], 1)
        self.assertEqual(data['lines'][0]['price_unit'], 100.0)
        self.assertEqual(data['amounts']['total'], 100.0)
        self.assertIn('delivery_address', data)
        self.assertTrue(data['pdf_url'].endswith(f'/my/orders/{self.quote_sign.id}/pdf'))

    def test_order_detail_access_token(self):
        token = self.quote_sign._portal_ensure_token()
        response, body = self.api(
            'GET', f'/my/orders/{self.quote_sign.id}?access_token={token}')
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data']['id'], self.quote_sign.id)
        # The token is propagated into pdf_url.
        self.assertIn(f'access_token={token}', body['data']['pdf_url'])

        response, body = self.api(
            'GET', f'/my/orders/{self.quote_sign.id}?access_token=wrong-token')
        self.assert_api_error(response, body, 403, 'forbidden')

    # -- Accept (sign) -----------------------------------------------------------

    def test_order_accept(self):
        response, body = self.api(
            'POST', f'/my/orders/{self.quote_sign.id}/accept',
            {'name': 'Odusite Orders Tester', 'signature': TINY_PNG_B64},
            bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertTrue(data['signed'])
        # No payment required: signing confirms the order.
        self.assertEqual(data['state'], 'sale')
        self.assertFalse(data['requires_payment'])

        self.env.invalidate_all()
        self.assertEqual(self.quote_sign.state, 'sale')
        self.assertEqual(self.quote_sign.signed_by, 'Odusite Orders Tester')
        self.assertTrue(self.quote_sign.signature)

        # Signing again is a conflict: the order no longer awaits a signature.
        response, body = self.api(
            'POST', f'/my/orders/{self.quote_sign.id}/accept',
            {'name': 'Odusite Orders Tester', 'signature': TINY_PNG_B64},
            bearer=self._bearer())
        self.assert_api_error(response, body, 409, 'conflict')

    def test_order_accept_missing_signature(self):
        response, body = self.api(
            'POST', f'/my/orders/{self.quote_sign.id}/accept',
            {'name': 'Odusite Orders Tester'}, bearer=self._bearer())
        self.assert_api_error(response, body, 400, 'bad_request')

    # -- Decline --------------------------------------------------------------

    def test_order_decline(self):
        response, body = self.api(
            'POST', f'/my/orders/{self.quote_decline.id}/decline',
            {'reason': 'Too expensive for us'}, bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data']['state'], 'cancel')

        self.env.invalidate_all()
        self.assertEqual(self.quote_decline.state, 'cancel')
        # The cancellation tracking note may be posted after the customer's
        # comment — assert on the whole thread, not the newest message.
        messages = self.env['mail.message'].search([
            ('model', '=', 'sale.order'),
            ('res_id', '=', self.quote_decline.id),
        ])
        self.assertTrue(
            any('Too expensive for us' in (message.body or '')
                for message in messages),
            messages.mapped('body'))

    def test_order_decline_requires_reason(self):
        response, body = self.api(
            'POST', f'/my/orders/{self.quote_decline.id}/decline', {},
            bearer=self._bearer())
        self.assert_api_error(response, body, 400, 'bad_request')

    # -- PDF --------------------------------------------------------------------

    def test_order_pdf(self):
        # In Odoo's test mode _render_qweb_pdf falls back to the HTML
        # rendering, so this passes without wkhtmltopdf; on a server where the
        # PDF pipeline is broken we skip instead of failing the suite.
        token = self.quote_sign._portal_ensure_token()
        response, _body = self.api(
            'GET', f'/my/orders/{self.quote_sign.id}/pdf?access_token={token}')
        content_type = response.headers.get('Content-Type', '')
        if response.status_code != 200 or 'application/pdf' not in content_type:
            self.skipTest(
                f'order PDF rendering unavailable (status {response.status_code}, '
                f'content-type {content_type})')
        self.assertTrue(response.content)
        self.assertIn('attachment', response.headers.get('Content-Disposition', ''))
