"""Tests for /odusite/v1/me/* (odusite_portal/controllers/me.py)."""

from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase

PASSWORD = 'Portal123!secure'


@tagged('post_install', '-at_install')
class TestMeApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_us = cls.env.ref('base.us')
        cls.state_ca = cls.env.ref('base.state_us_5')  # California
        cls.user = cls.create_portal_user(
            login='me.portal@example.com', password=PASSWORD, name='Me Portal')
        cls.partner = cls.user.partner_id
        # A complete main address, so partial PUT /me updates pass the portal
        # address validation (street/city/country are mandatory once set).
        cls.partner.write({
            'phone': '+1 555 0100',
            'street': '215 Vine Street',
            'city': 'Scranton',
            'zip': '18503',
            'country_id': cls.country_us.id,
            'state_id': cls.state_ca.id,
        })
        cls.other_user = cls.create_portal_user(
            login='me.other@example.com', password=PASSWORD, name='Me Other')

    def _address_payload(self, **overrides):
        payload = {
            'address_type': 'delivery',
            'name': 'Warehouse Dock',
            'email': 'dock@example.com',
            'phone': '+1 555 0111',
            'street': '1 Dock Avenue',
            'city': 'Scranton',
            'zip': '18504',
            'country_id': self.country_us.id,
            'state_id': self.state_ca.id,
        }
        payload.update(overrides)
        return payload

    def _create_address(self, access, **overrides):
        response, body = self.api('POST', '/me/addresses',
                                  self._address_payload(**overrides), bearer=access)
        self.assertEqual(response.status_code, 200, body)
        return body['data']

    # -- profile -----------------------------------------------------------

    def test_me_requires_bearer(self):
        response, body = self.api('GET', '/me')
        self.assert_api_error(response, body, 401, 'unauthorized')

    def test_me_profile_shape(self):
        access = self.make_access_token(self.user)
        response, body = self.api('GET', '/me', bearer=access)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['id'], self.user.id)
        self.assertEqual(data['name'], 'Me Portal')
        self.assertEqual(data['email'], self.user.login)
        self.assertEqual(data['phone'], '+1 555 0100')
        partner = data['partner']
        self.assertEqual(partner['id'], self.partner.id)
        self.assertEqual(partner['name'], 'Me Portal')
        self.assertEqual(partner['street'], '215 Vine Street')
        self.assertEqual(partner['city'], 'Scranton')
        self.assertEqual(partner['zip'], '18503')
        self.assertEqual(partner['country']['code'], 'US')
        self.assertEqual(partner['state']['code'], 'CA')
        for key in ('email', 'phone', 'street2', 'vat', 'company_name', 'type'):
            self.assertIn(key, partner)

    def test_me_update_profile(self):
        access = self.make_access_token(self.user)
        response, body = self.api('PUT', '/me', {
            'name': 'Renamed Portal',
            'phone': '+1 555 0199',
        }, bearer=access)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data']['name'], 'Renamed Portal')
        self.assertEqual(body['data']['phone'], '+1 555 0199')
        # Untouched fields survive the partial update.
        self.assertEqual(body['data']['partner']['street'], '215 Vine Street')

        self.env.invalidate_all()
        self.assertEqual(self.partner.name, 'Renamed Portal')
        self.assertEqual(self.partner.phone, '+1 555 0199')

    def test_me_update_invalid_email(self):
        access = self.make_access_token(self.user)
        response, body = self.api('PUT', '/me', {'email': 'not-an-email'},
                                  bearer=access)
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertIn('email', body['error']['details']['fields'])

        self.env.invalidate_all()
        self.assertEqual(self.partner.email, self.user.login)

    # -- password ----------------------------------------------------------

    def test_password_change_wrong_old(self):
        access = self.make_access_token(self.user)
        response, body = self.api('PUT', '/me/password', {
            'old_password': 'definitely-wrong',
            'new_password': 'Another456!secure',
        }, bearer=access)
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertIn('old_password', body['error']['details']['fields'])

    def test_password_change_missing_fields(self):
        access = self.make_access_token(self.user)
        response, body = self.api('PUT', '/me/password',
                                  {'new_password': 'Another456!secure'}, bearer=access)
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertIn('old_password', body['error']['details']['fields'])

        response, body = self.api('PUT', '/me/password',
                                  {'old_password': PASSWORD}, bearer=access)
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertIn('new_password', body['error']['details']['fields'])

    def test_password_change_revokes_other_sessions(self):
        access1, refresh1 = self.login_portal(self.user)
        _access2, refresh2 = self.login_portal(self.user)
        new_password = 'Another456!secure'

        response, body = self.api('PUT', '/me/password', {
            'old_password': PASSWORD,
            'new_password': new_password,
            'refresh_token': refresh1,
        }, bearer=access1)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], {'ok': True})

        # Other sessions are revoked; the provided refresh token survives.
        response, body = self.api('POST', '/auth/refresh',
                                  {'refresh_token': refresh2})
        self.assert_api_error(response, body, 401, 'unauthorized')
        response, body = self.api('POST', '/auth/refresh',
                                  {'refresh_token': refresh1})
        self.assertEqual(response.status_code, 200, body)

        # Only the new password logs in.
        response, body = self.api('POST', '/auth/login',
                                  {'login': self.user.login, 'password': PASSWORD})
        self.assert_api_error(response, body, 401, 'unauthorized')
        self.login_portal(self.user, password=new_password)

    # -- address book --------------------------------------------------------

    def test_address_create_and_list(self):
        access = self.make_access_token(self.user)
        data = self._create_address(access)
        self.assertEqual(data['type'], 'delivery')
        self.assertEqual(data['name'], 'Warehouse Dock')
        self.assertEqual(data['street'], '1 Dock Avenue')
        self.assertEqual(data['country']['code'], 'US')

        self.env.invalidate_all()
        address = self.env['res.partner'].browse(data['id'])
        self.assertEqual(address.parent_id, self.partner)
        self.assertEqual(address.type, 'delivery')

        response, body = self.api('GET', '/me/addresses', bearer=access)
        self.assertEqual(response.status_code, 200, body)
        delivery_ids = [item['id'] for item in body['data']['delivery']]
        billing_ids = [item['id'] for item in body['data']['billing']]
        self.assertIn(data['id'], delivery_ids)
        self.assertNotIn(data['id'], billing_ids)

    def test_address_create_validation(self):
        access = self.make_access_token(self.user)

        response, body = self.api('POST', '/me/addresses',
                                  {'address_type': 'bogus'}, bearer=access)
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertIn('address_type', body['error']['details']['fields'])

        response, body = self.api('POST', '/me/addresses', {
            'address_type': 'delivery',
            'name': 'Incomplete Address',
        }, bearer=access)
        self.assert_api_error(response, body, 422, 'validation_error')
        fields = body['error']['details']['fields']
        self.assertIn('city', fields)
        self.assertIn('country_id', fields)

    def test_address_update(self):
        access = self.make_access_token(self.user)
        data = self._create_address(access)

        response, body = self.api('PUT', f"/me/addresses/{data['id']}",
                                  {'street': '2 Dock Avenue'}, bearer=access)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data']['street'], '2 Dock Avenue')
        # Prefilled fields are untouched by the partial update.
        self.assertEqual(body['data']['city'], 'Scranton')

        self.env.invalidate_all()
        self.assertEqual(
            self.env['res.partner'].browse(data['id']).street, '2 Dock Avenue')

    def test_address_delete_archives(self):
        access = self.make_access_token(self.user)
        data = self._create_address(access)

        response, _body = self.api('DELETE', f"/me/addresses/{data['id']}",
                                   bearer=access)
        self.assertEqual(response.status_code, 204)

        response, body = self.api('GET', '/me/addresses', bearer=access)
        listed_ids = [item['id']
                      for item in body['data']['delivery'] + body['data']['billing']]
        self.assertNotIn(data['id'], listed_ids)

        # Archived, never unlinked.
        self.env.invalidate_all()
        address = self.env['res.partner'].with_context(
            active_test=False).browse(data['id'])
        self.assertTrue(address.exists())
        self.assertFalse(address.active)

    def test_address_of_other_partner_not_reachable(self):
        other_address = self.env['res.partner'].create({
            'name': 'Other Dock',
            'type': 'delivery',
            'parent_id': self.other_user.partner_id.id,
            'email': 'other.dock@example.com',
            'phone': '+1 555 0122',
            'street': '9 Other Street',
            'city': 'Utica',
            'zip': '13501',
            'country_id': self.country_us.id,
            'state_id': self.state_ca.id,
        })
        access = self.make_access_token(self.user)

        response, body = self.api('PUT', f'/me/addresses/{other_address.id}',
                                  {'street': 'Hijacked'}, bearer=access)
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api('DELETE', f'/me/addresses/{other_address.id}',
                                  bearer=access)
        self.assert_api_error(response, body, 404, 'not_found')

        self.env.invalidate_all()
        self.assertEqual(other_address.street, '9 Other Street')
        self.assertTrue(other_address.active)

    def test_main_address_not_editable_via_address_book(self):
        access = self.make_access_token(self.user)
        response, body = self.api('PUT', f'/me/addresses/{self.partner.id}',
                                  {'street': 'Nope'}, bearer=access)
        self.assert_api_error(response, body, 403, 'forbidden')

        response, body = self.api('DELETE', f'/me/addresses/{self.partner.id}',
                                  bearer=access)
        self.assert_api_error(response, body, 403, 'forbidden')

    # -- counters ------------------------------------------------------------

    def test_counters(self):
        access = self.make_access_token(self.user)
        response, body = self.api('GET', '/me/counters', bearer=access)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], {})

        # Unknown keys are simply ignored by the registry.
        response, body = self.api(
            'GET', '/me/counters?counters=definitely_unknown_counter', bearer=access)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], {})

    # -- sessions --------------------------------------------------------------

    def test_sessions_list_and_revoke(self):
        access, refresh = self.login_portal(self.user)
        Token = self.env['odusite.refresh.token'].sudo()
        row = Token.search([('token_hash', '=', Token._hash_token(refresh))])
        self.assertEqual(len(row), 1)

        response, body = self.api('GET', '/me/sessions', bearer=access)
        self.assertEqual(response.status_code, 200, body)
        sessions = {session['id']: session for session in body['data']}
        self.assertIn(row.id, sessions)
        session = sessions[row.id]
        self.assertFalse(session['is_current'])
        self.assertTrue(session['created_at'])
        self.assertTrue(session['expires_at'])
        for key in ('user_agent', 'ip', 'last_used_at'):
            self.assertIn(key, session)

        response, _body = self.api('DELETE', f'/me/sessions/{row.id}',
                                   bearer=access)
        self.assertEqual(response.status_code, 204)

        response, body = self.api('GET', '/me/sessions', bearer=access)
        self.assertNotIn(row.id, [session['id'] for session in body['data']])

        # The matching refresh token no longer works.
        response, body = self.api('POST', '/auth/refresh',
                                  {'refresh_token': refresh})
        self.assert_api_error(response, body, 401, 'unauthorized')

    def test_session_of_other_user_not_revocable(self):
        access, _refresh = self.login_portal(self.user)
        _other_access, other_refresh = self.login_portal(self.other_user)
        Token = self.env['odusite.refresh.token'].sudo()
        other_row = Token.search(
            [('token_hash', '=', Token._hash_token(other_refresh))])

        response, body = self.api('DELETE', f'/me/sessions/{other_row.id}',
                                  bearer=access)
        self.assert_api_error(response, body, 404, 'not_found')

        # And it still works for its owner.
        response, body = self.api('POST', '/auth/refresh',
                                  {'refresh_token': other_refresh})
        self.assertEqual(response.status_code, 200, body)
