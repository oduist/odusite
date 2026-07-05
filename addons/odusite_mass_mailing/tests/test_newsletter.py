from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase


@tagged('post_install', '-at_install')
class TestNewsletterApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Stock mass_mailing data ships a public "Newsletter" list; hide any
        # pre-existing public lists so default-list resolution is deterministic.
        cls.env['mailing.list'].search([]).write({'is_public': False})
        cls.list_news = cls.env['mailing.list'].create(
            {'name': 'Odusite News', 'is_public': True})
        cls.list_product = cls.env['mailing.list'].create(
            {'name': 'Product Updates', 'is_public': True})
        cls.list_private = cls.env['mailing.list'].create(
            {'name': 'Internal', 'is_public': False})

    def _find_contact(self, email):
        return self.env['mailing.contact'].search([('email', '=', email)])

    def test_subscribe_default_list(self):
        response, body = self.api('POST', '/newsletter/subscribe',
                                  {'email': 'alice@example.com'})
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], {'subscribed': True, 'list': 'Odusite News'})
        contact = self._find_contact('alice@example.com')
        self.assertEqual(len(contact), 1)
        self.assertEqual(contact.subscription_ids.list_id, self.list_news)
        self.assertFalse(contact.subscription_ids.opt_out)

    def test_subscribe_explicit_list(self):
        response, body = self.api('POST', '/newsletter/subscribe',
                                  {'email': 'bob@example.com',
                                   'list_id': self.list_product.id})
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'],
                         {'subscribed': True, 'list': 'Product Updates'})
        contact = self._find_contact('bob@example.com')
        self.assertEqual(contact.subscription_ids.list_id, self.list_product)

    def test_subscribe_idempotent(self):
        for email in ('carol@example.com', 'Carol@Example.COM'):
            response, body = self.api('POST', '/newsletter/subscribe',
                                      {'email': email})
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body['data'],
                             {'subscribed': True, 'list': 'Odusite News'})
        contact = self._find_contact('carol@example.com')
        self.assertEqual(len(contact), 1)
        self.assertEqual(len(contact.subscription_ids), 1)

    def test_subscribe_reactivates_opt_out(self):
        contact = self.env['mailing.contact'].create(
            {'name': 'Dave', 'email': 'dave@example.com'})
        subscription = self.env['mailing.subscription'].create(
            {'contact_id': contact.id, 'list_id': self.list_news.id,
             'opt_out': True})
        response, body = self.api('POST', '/newsletter/subscribe',
                                  {'email': 'dave@example.com'})
        self.assertEqual(response.status_code, 200, body)
        self.env.invalidate_all()
        self.assertEqual(len(self._find_contact('dave@example.com')), 1)
        self.assertFalse(subscription.opt_out)

    def test_subscribe_invalid_email(self):
        for email in ('', 'not-an-email'):
            response, body = self.api('POST', '/newsletter/subscribe',
                                      {'email': email})
            self.assert_api_error(response, body, 422, 'validation_error')
            self.assertEqual(body['error']['details']['fields'],
                             {'email': 'invalid'})
        self.assertFalse(self._find_contact('not-an-email'))

    def test_subscribe_honeypot(self):
        response, body = self.api('POST', '/newsletter/subscribe',
                                  {'email': 'spambot@example.com',
                                   'website_hp': 'gotcha'})
        # Silently accepted, nothing created, no list name leaked.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['data'], {'subscribed': True})
        self.assertFalse(self._find_contact('spambot@example.com'))

    def test_subscribe_private_list(self):
        response, body = self.api('POST', '/newsletter/subscribe',
                                  {'email': 'eve@example.com',
                                   'list_id': self.list_private.id})
        self.assert_api_error(response, body, 404, 'no_list')
        self.assertFalse(self._find_contact('eve@example.com'))

    def test_subscribe_no_public_list(self):
        (self.list_news | self.list_product).write({'is_public': False})
        response, body = self.api('POST', '/newsletter/subscribe',
                                  {'email': 'frank@example.com'})
        self.assert_api_error(response, body, 404, 'no_list')

    def test_lists_public_only(self):
        response, body = self.api('GET', '/newsletter/lists')
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], [
            {'id': self.list_news.id, 'name': 'Odusite News'},
            {'id': self.list_product.id, 'name': 'Product Updates'},
        ])
