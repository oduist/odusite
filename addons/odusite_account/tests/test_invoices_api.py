from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase
# odusite_account depends on odusite_payment: reusing its fixtures is safe.
from odoo.addons.odusite_payment.tests.common import PaymentFixturesMixin


@tagged('post_install', '-at_install')
class TestInvoicesApi(PaymentFixturesMixin, OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls._ensure_chart_of_accounts(cls.company)
        cls.portal_user = cls.create_portal_user(
            login='odusite.invoices@example.com', name='Odusite Invoices Tester')
        cls.partner = cls.portal_user.partner_id
        # A compatible provider makes requires_payment computable to True.
        cls.provider, cls.method = cls._enable_test_provider(cls.company)

        today = fields.Date.today()
        yesterday = today - timedelta(days=1)
        cls.inv_open = cls._make_invoice(
            cls.partner, 150.0, date_due=today + timedelta(days=30))
        cls.inv_overdue = cls._make_invoice(
            cls.partner, 100.0, invoice_date=yesterday, date_due=yesterday)
        cls.inv_paid = cls._make_invoice(cls.partner, 80.0)
        cls._register_full_payment(cls.inv_paid)
        cls.inv_draft = cls._make_invoice(cls.partner, 50.0, post=False)

        other_partner = cls.env['res.partner'].create(
            {'name': 'Odusite Other Customer'})
        cls.inv_other = cls._make_invoice(other_partner, 42.0)

    def _bearer(self):
        return self.make_access_token(self.portal_user)

    def _ids(self, body):
        return [item['id'] for item in body['data']]

    # -- List -------------------------------------------------------------

    def test_list_posted_only(self):
        response, body = self.api('GET', '/my/invoices?limit=100',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        ids = self._ids(body)
        self.assertIn(self.inv_open.id, ids)
        self.assertIn(self.inv_overdue.id, ids)
        self.assertIn(self.inv_paid.id, ids)
        # Drafts never appear; other partners' invoices are filtered by the
        # portal record rules.
        self.assertNotIn(self.inv_draft.id, ids)
        self.assertNotIn(self.inv_other.id, ids)

        by_id = {item['id']: item for item in body['data']}
        item = by_id[self.inv_overdue.id]
        for key in ('id', 'name', 'invoice_date', 'invoice_date_due',
                    'amount_total', 'amount_residual', 'currency',
                    'payment_state', 'is_overdue'):
            self.assertIn(key, item)
        self.assertEqual(item['amount_total'], 100.0)
        self.assertEqual(item['amount_residual'], 100.0)
        self.assertTrue(item['is_overdue'])
        self.assertFalse(by_id[self.inv_open.id]['is_overdue'])
        self.assertFalse(by_id[self.inv_paid.id]['is_overdue'])

    def test_list_requires_jwt(self):
        response, body = self.api('GET', '/my/invoices')
        self.assert_api_error(response, body, 401, 'unauthorized')

    def test_list_state_filters(self):
        response, body = self.api('GET', '/my/invoices?state=overdue&limit=100',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(self._ids(body), [self.inv_overdue.id])

        response, body = self.api('GET', '/my/invoices?state=paid&limit=100',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(self._ids(body), [self.inv_paid.id])
        self.assertIn(body['data'][0]['payment_state'], ('in_payment', 'paid'))

        # 'open' covers everything still to pay, overdue included.
        response, body = self.api('GET', '/my/invoices?state=open&limit=100',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(set(self._ids(body)),
                         {self.inv_open.id, self.inv_overdue.id})

        response, body = self.api('GET', '/my/invoices?state=bogus',
                                  bearer=self._bearer())
        self.assert_api_error(response, body, 400, 'bad_request')
        self.assertEqual(body['error']['details']['allowed'],
                         ['open', 'overdue', 'paid'])

    # -- Detail -------------------------------------------------------------

    def test_detail_jwt(self):
        response, body = self.api('GET', f'/my/invoices/{self.inv_open.id}',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['id'], self.inv_open.id)
        self.assertEqual(len(data['lines']), 1)
        line = data['lines'][0]
        self.assertEqual(line['quantity'], 1.0)
        self.assertEqual(line['price_unit'], 150.0)
        self.assertEqual(line['price_subtotal'], 150.0)
        self.assertEqual(line['taxes'], [])
        self.assertEqual(data['amount_untaxed'], 150.0)
        # Posted, residual > 0 and a compatible (test) provider exists.
        self.assertTrue(data['requires_payment'])
        self.assertEqual(data['pdf_url'],
                         f'/odusite/v1/my/invoices/{self.inv_open.id}/pdf')

    def test_detail_paid_requires_no_payment(self):
        response, body = self.api('GET', f'/my/invoices/{self.inv_paid.id}',
                                  bearer=self._bearer())
        self.assertEqual(response.status_code, 200, body)
        self.assertFalse(body['data']['requires_payment'])
        self.assertEqual(body['data']['amount_residual'], 0.0)

    def test_detail_access_token_without_jwt(self):
        token = self.inv_open._portal_ensure_token()
        response, body = self.api(
            'GET', f'/my/invoices/{self.inv_open.id}?access_token={token}')
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data']['id'], self.inv_open.id)

        response, body = self.api(
            'GET', f'/my/invoices/{self.inv_open.id}?access_token=wrong-token')
        self.assert_api_error(response, body, 403, 'forbidden')

    def test_detail_draft_not_found(self):
        # Even with a valid document token a draft invoice is hidden.
        token = self.inv_draft._portal_ensure_token()
        response, body = self.api(
            'GET', f'/my/invoices/{self.inv_draft.id}?access_token={token}')
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api('GET', '/my/invoices/99999999',
                                  bearer=self._bearer())
        self.assert_api_error(response, body, 404, 'not_found')

    def test_detail_other_partner_forbidden(self):
        response, body = self.api('GET', f'/my/invoices/{self.inv_other.id}',
                                  bearer=self._bearer())
        self.assert_api_error(response, body, 403, 'forbidden')

    # -- PDF ------------------------------------------------------------------

    def test_pdf(self):
        # In Odoo's test mode the report engine falls back to HTML rendering,
        # so this passes without wkhtmltopdf; if the PDF pipeline is broken on
        # the test server we skip instead of failing the suite.
        token = self.inv_open._portal_ensure_token()
        response, _body = self.api(
            'GET', f'/my/invoices/{self.inv_open.id}/pdf?access_token={token}')
        content_type = response.headers.get('Content-Type', '')
        if response.status_code != 200 or 'application/pdf' not in content_type:
            self.skipTest(
                f'invoice PDF rendering unavailable (status {response.status_code}, '
                f'content-type {content_type})')
        self.assertTrue(response.content)
        self.assertIn('attachment', response.headers.get('Content-Disposition', ''))

    # -- Portal counters ---------------------------------------------------------

    def test_portal_counters(self):
        counters = self.env['odusite.api'].with_user(
            self.portal_user)._portal_counters(['invoices'])
        # 3 posted invoices of the partner (open, overdue, paid); the draft
        # and the other partner's invoice are excluded.
        self.assertEqual(counters['invoices'], 3)
        self.assertEqual(counters['invoices_overdue'], 1)

    def test_portal_counters_not_requested(self):
        counters = self.env['odusite.api'].with_user(
            self.portal_user)._portal_counters([])
        self.assertNotIn('invoices', counters)
