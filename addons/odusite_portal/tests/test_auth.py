"""Tests for /odusite/v1/auth/* (odusite_portal/controllers/auth.py)."""

import time

from odoo.tests.common import tagged

from odoo.addons.odusite_base.lib import jwt as jwt_lib
from odoo.addons.odusite_base.tests.common import OdusiteHttpCase

PASSWORD = 'Portal123!secure'


@tagged('post_install', '-at_install')
class TestAuthApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.create_portal_user(
            login='auth.portal@example.com', password=PASSWORD, name='Auth Portal')

    # -- login -----------------------------------------------------------

    def test_login_success(self):
        response, body = self.api('POST', '/auth/login',
                                  {'login': self.user.login, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertTrue(data['access_token'])
        self.assertTrue(data['refresh_token'])
        self.assertEqual(data['expires_in'], 900)
        self.assertEqual(data['user'], {
            'id': self.user.id,
            'name': 'Auth Portal',
            'email': self.user.login,
            'partner_id': self.user.partner_id.id,
            'lang': self.user.lang,
            'is_portal': True,
        })

        payload = jwt_lib.verify(data['access_token'], self.jwt_secret)
        self.assertEqual(payload['typ'], 'access')
        self.assertEqual(payload['sub'], self.user.id)
        self.assertEqual(payload['pid'], self.user.partner_id.id)
        self.assertTrue(payload['jti'])
        self.assertEqual(payload['exp'] - payload['iat'], 900)

        # The refresh token is stored hashed, never in clear text.
        Token = self.env['odusite.refresh.token'].sudo()
        row = Token.search(
            [('token_hash', '=', Token._hash_token(data['refresh_token']))])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.user_id, self.user)
        self.assertFalse(row.revoked)

    def test_login_wrong_credentials_no_enumeration(self):
        response_wrong, body_wrong = self.api(
            'POST', '/auth/login',
            {'login': self.user.login, 'password': 'definitely-wrong'})
        self.assert_api_error(response_wrong, body_wrong, 401, 'unauthorized')

        response_ghost, body_ghost = self.api(
            'POST', '/auth/login',
            {'login': 'ghost.user@example.com', 'password': 'definitely-wrong'})
        self.assert_api_error(response_ghost, body_ghost, 401, 'unauthorized')

        # Unknown login and wrong password must be indistinguishable.
        self.assertEqual(body_wrong['error'], body_ghost['error'])

    def test_login_missing_fields(self):
        for payload in (
            {},
            {'login': self.user.login},
            {'password': PASSWORD},
            {'login': '', 'password': PASSWORD},
            {'login': self.user.login, 'password': ''},
            {'login': 42, 'password': PASSWORD},
        ):
            response, body = self.api('POST', '/auth/login', payload)
            self.assert_api_error(response, body, 400, 'bad_request')

    # -- refresh ---------------------------------------------------------

    def test_refresh_rotation(self):
        _access1, refresh1 = self.login_portal(self.user)

        response, body = self.api('POST', '/auth/refresh',
                                  {'refresh_token': refresh1})
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertNotEqual(data['refresh_token'], refresh1)
        payload = jwt_lib.verify(data['access_token'], self.jwt_secret)
        self.assertEqual(payload['typ'], 'access')
        self.assertEqual(payload['sub'], self.user.id)

        # The consumed token is revoked: a second use must fail.
        response, body = self.api('POST', '/auth/refresh',
                                  {'refresh_token': refresh1})
        self.assert_api_error(response, body, 401, 'unauthorized')

        # The rotated token works.
        response, body = self.api('POST', '/auth/refresh',
                                  {'refresh_token': data['refresh_token']})
        self.assertEqual(response.status_code, 200, body)

    def test_refresh_invalid_token(self):
        for payload in ({}, {'refresh_token': None}, {'refresh_token': ''},
                        {'refresh_token': 'not-a-known-token'}):
            response, body = self.api('POST', '/auth/refresh', payload)
            self.assert_api_error(response, body, 401, 'unauthorized')

    # -- logout ----------------------------------------------------------

    def test_logout_revokes_refresh_token(self):
        _access, refresh = self.login_portal(self.user)

        response, body = self.api('POST', '/auth/logout',
                                  {'refresh_token': refresh})
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], {'ok': True})

        response, body = self.api('POST', '/auth/refresh',
                                  {'refresh_token': refresh})
        self.assert_api_error(response, body, 401, 'unauthorized')

        # Idempotent, no revocation oracle.
        response, body = self.api('POST', '/auth/logout',
                                  {'refresh_token': refresh})
        self.assertEqual(response.status_code, 200, body)

    def test_logout_requires_refresh_token_or_bearer(self):
        response, body = self.api('POST', '/auth/logout', {})
        self.assert_api_error(response, body, 400, 'bad_request')

        # all:true without a Bearer access token is refused.
        response, body = self.api('POST', '/auth/logout', {'all': True})
        self.assert_api_error(response, body, 401, 'unauthorized')

    def test_logout_all_revokes_every_session(self):
        access1, refresh1 = self.login_portal(self.user)
        _access2, refresh2 = self.login_portal(self.user)

        response, body = self.api('POST', '/auth/logout', {'all': True},
                                  bearer=access1)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'], {'ok': True})

        for refresh in (refresh1, refresh2):
            response, body = self.api('POST', '/auth/refresh',
                                      {'refresh_token': refresh})
            self.assert_api_error(response, body, 401, 'unauthorized')

    # -- password forgot ---------------------------------------------------

    def test_password_forgot_no_enumeration(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'auth_signup.reset_password', 'True')

        response_known, body_known = self.api(
            'POST', '/auth/password/forgot', {'login': self.user.login})
        self.assertEqual(response_known.status_code, 200, body_known)
        self.assertEqual(body_known['data'], {'ok': True})

        response_ghost, body_ghost = self.api(
            'POST', '/auth/password/forgot', {'login': 'ghost.user@example.com'})
        self.assertEqual(response_ghost.status_code, 200, body_ghost)
        self.assertEqual(body_known, body_ghost)

        response, body = self.api('POST', '/auth/password/forgot', {})
        self.assert_api_error(response, body, 400, 'bad_request')

    # -- bearer token enforcement on protected routes ----------------------

    def test_bearer_rejects_non_access_token_type(self):
        # A token with typ != 'access' (e.g. a would-be refresh JWT) must not
        # grant access even though its signature is valid.
        forged = self.make_access_token(self.user, typ='refresh')
        response, body = self.api('GET', '/me', bearer=forged)
        self.assert_api_error(response, body, 401, 'invalid_jwt')

    def test_bearer_rejects_forged_signature(self):
        now = int(time.time())
        forged = jwt_lib.sign({
            'sub': self.user.id,
            'pid': self.user.partner_id.id,
            'typ': 'access',
            'iat': now,
            'exp': now + 900,
            'jti': 'forged',
        }, 'not-the-real-secret')
        response, body = self.api('GET', '/me', bearer=forged)
        self.assert_api_error(response, body, 401, 'invalid_jwt')

    def test_bearer_rejects_expired_token(self):
        expired = self.make_access_token(self.user, ttl=-60)
        response, body = self.api('GET', '/me', bearer=expired)
        self.assert_api_error(response, body, 401, 'jwt_expired')

    def test_bearer_rejects_archived_user(self):
        user = self.create_portal_user(
            login='auth.archived@example.com', password=PASSWORD, name='Archived')
        token = self.make_access_token(user)
        user.active = False
        response, body = self.api('GET', '/me', bearer=token)
        self.assert_api_error(response, body, 401, 'invalid_jwt')
