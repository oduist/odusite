"""Tests for /odusite/v1/chatter/* (odusite_portal/controllers/chatter.py).

The chatter whitelist is contributed by other odusite modules; these tests use
``sale.order`` (registered by ``odusite_sale``) and are skipped when it is not
available in the registry.
"""

import json
import unittest

from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase

PASSWORD = 'Portal123!secure'


@tagged('post_install', '-at_install')
class TestChatterApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if ('sale.order' not in cls.env['odusite.api']._chatter_models()
                or 'sale.order' not in cls.env):
            raise unittest.SkipTest(
                'sale.order is not registered in the odusite chatter whitelist '
                '(odusite_sale is not installed)')
        cls.user = cls.create_portal_user(
            login='chatter.portal@example.com', password=PASSWORD,
            name='Chatter Portal')
        cls.partner = cls.user.partner_id
        cls.order = cls.env['sale.order'].create({'partner_id': cls.partner.id})

        cls.other_user = cls.create_portal_user(
            login='chatter.other@example.com', password=PASSWORD,
            name='Chatter Other')
        cls.other_order = cls.env['sale.order'].create(
            {'partner_id': cls.other_user.partner_id.id})

        # An internal user with write access on sale.order: in Odoo 19
        # sale.order does not define _mail_post_access, so posting through the
        # chatter API requires 'write' on the document.
        cls.manager = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'login': 'chatter.manager@example.com',
                'name': 'Chatter Manager',
                'email': 'chatter.manager@example.com',
                'group_ids': [(6, 0, [
                    cls.env.ref('base.group_user').id,
                    cls.env.ref('sales_team.group_sale_manager').id,
                ])],
            })

    @property
    def order_path(self):
        return f'/chatter/sale.order/{self.order.id}/messages'

    # -- whitelist ---------------------------------------------------------

    def test_unregistered_model_is_404(self):
        access = self.make_access_token(self.user)

        # res.partner exists but is not whitelisted.
        response, body = self.api(
            'GET', f'/chatter/res.partner/{self.partner.id}/messages',
            bearer=access)
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api(
            'POST', f'/chatter/res.partner/{self.partner.id}/messages',
            {'body': 'Hello'}, bearer=access)
        self.assert_api_error(response, body, 404, 'not_found')

        # Unknown model names get the same answer (no model enumeration).
        response, body = self.api('GET', '/chatter/no.such.model/1/messages',
                                  bearer=access)
        self.assert_api_error(response, body, 404, 'not_found')

    def test_missing_record_is_404(self):
        access = self.make_access_token(self.user)
        response, body = self.api(
            'GET', '/chatter/sale.order/99999999/messages', bearer=access)
        self.assert_api_error(response, body, 404, 'not_found')

        manager_access = self.make_access_token(self.manager)
        response, body = self.api(
            'POST', '/chatter/sale.order/99999999/messages',
            {'body': 'Hello'}, bearer=manager_access)
        self.assert_api_error(response, body, 404, 'not_found')

    # -- reading -----------------------------------------------------------

    def test_messages_share_safe_domain(self):
        access = self.make_access_token(self.user)

        response, body = self.api('GET', self.order_path, bearer=access)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], [])
        self.assertEqual(body['meta']['total'], 0)

        # A customer-visible comment and an internal note.
        self.order.message_post(
            body='Public reply', message_type='comment',
            subtype_xmlid='mail.mt_comment')
        self.order.message_post(
            body='Internal note', message_type='comment',
            subtype_xmlid='mail.mt_note')

        response, body = self.api('GET', self.order_path, bearer=access)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['meta']['total'], 1)
        self.assertEqual(len(body['data']), 1)
        item = body['data'][0]
        self.assertIn('Public reply', item['body'])
        self.assertEqual(item['author']['name'], self.env.user.partner_id.name)
        self.assertTrue(item['date'])
        self.assertEqual(item['attachments'], [])
        # The internal note never leaks anywhere in the payload.
        self.assertNotIn('Internal note', json.dumps(body))

    def test_other_customers_document_forbidden(self):
        access = self.make_access_token(self.user)
        response, body = self.api(
            'GET', f'/chatter/sale.order/{self.other_order.id}/messages',
            bearer=access)
        self.assert_api_error(response, body, 403, 'forbidden')

    def test_access_token_grants_read(self):
        self.order.message_post(
            body='Token visible', message_type='comment',
            subtype_xmlid='mail.mt_comment')
        token = self.order._portal_ensure_token()

        # No Bearer at all: the record access_token is enough for reading.
        response, body = self.api(
            'GET', f'{self.order_path}?access_token={token}')
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['meta']['total'], 1)
        self.assertIn('Token visible', body['data'][0]['body'])

    def test_wrong_access_token_forbidden(self):
        self.order._portal_ensure_token()

        response, body = self.api(
            'GET', f'{self.order_path}?access_token=wrong-token')
        self.assert_api_error(response, body, 403, 'forbidden')

        # Anonymous without any token is refused as well.
        response, body = self.api('GET', self.order_path)
        self.assert_api_error(response, body, 403, 'forbidden')

    # -- posting -----------------------------------------------------------

    def test_post_requires_jwt(self):
        response, body = self.api('POST', self.order_path, {'body': 'Hello'})
        self.assert_api_error(response, body, 401, 'unauthorized')

    def test_portal_user_posts_on_own_sale_order(self):
        # odusite_sale sets `_mail_post_access = 'read'` on sale.order
        # (aligning with account.move/project.task) so portal customers can
        # comment on their own orders through the chatter API.
        access = self.make_access_token(self.user)
        response, body = self.api('POST', self.order_path,
                                  {'body': 'Hello from the customer'},
                                  bearer=access)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data']['author']['name'], self.user.partner_id.name)

    def test_post_message_full_flow(self):
        manager_access = self.make_access_token(self.manager)
        response, body = self.api('POST', self.order_path,
                                  {'body': 'Hello from the API'},
                                  bearer=manager_access)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertIn('Hello from the API', data['body'])
        self.assertEqual(data['author']['name'], self.manager.partner_id.name)

        # The message is visible to the customer through the same endpoint.
        portal_access = self.make_access_token(self.user)
        response, body = self.api('GET', self.order_path, bearer=portal_access)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['meta']['total'], 1)
        self.assertEqual(body['data'][0]['id'], data['id'])
        self.assertEqual(body['data'][0]['author']['name'],
                         self.manager.partner_id.name)

    def test_post_message_validation(self):
        manager_access = self.make_access_token(self.manager)

        response, body = self.api('POST', self.order_path, {'body': '   '},
                                  bearer=manager_access)
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertIn('body', body['error']['details']['fields'])

        response, body = self.api(
            'POST', self.order_path,
            {'body': 'Hello', 'attachment_ids': 'not-a-list'},
            bearer=manager_access)
        self.assert_api_error(response, body, 400, 'bad_request')
