"""Tests for the email double opt-in signup flow (odusite_portal auth).

Covers POST /auth/signup (b2c), /auth/confirm, /auth/confirm/resend, the
login gate for unconfirmed accounts, the invited-token shortcut and the
res.config.settings toggle. See specs/03-auth.md.
"""

import time

from odoo.tests.common import tagged

from odoo.addons.odusite_base.lib import jwt as jwt_lib
from odoo.addons.odusite_base.tests.common import OdusiteHttpCase

PASSWORD = 'Signup123!secure'


@tagged('post_install', '-at_install')
class TestSignupConfirm(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env['ir.config_parameter'].sudo()

    def _enable_b2c(self):
        self.ICP.set_param('auth_signup.invitation_scope', 'b2c')

    def _find_user(self, login):
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        return Users.search(Users._get_login_domain(login), limit=1)

    # -- b2c signup: double opt-in ---------------------------------------

    def test_signup_b2c_sends_confirmation(self):
        self._enable_b2c()
        email = 'newbie@example.com'
        response, body = self.api('POST', '/auth/signup',
                                  {'name': 'New Bie', 'email': email,
                                   'password': PASSWORD})
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data'],
                         {'status': 'confirmation_sent', 'email': email})
        # No tokens are issued before confirmation.
        self.assertNotIn('access_token', body['data'])
        self.assertNotIn('refresh_token', body['data'])

        user = self._find_user(email)
        self.assertTrue(user, 'user should be created')
        self.assertFalse(user.active, 'b2c signup must start inactive')
        self.assertFalse(user.odusite_email_confirmed)
        # No refresh token has been issued yet.
        self.assertFalse(self.env['odusite.refresh.token'].sudo().search_count(
            [('user_id', '=', user.id)]))

    def test_login_before_confirm_is_blocked(self):
        self._enable_b2c()
        email = 'pending@example.com'
        self.api('POST', '/auth/signup',
                 {'name': 'Pending', 'email': email, 'password': PASSWORD})

        response, body = self.api('POST', '/auth/login',
                                  {'login': email, 'password': PASSWORD})
        self.assert_api_error(response, body, 403, 'email_not_confirmed')

    def test_login_before_confirm_wrong_password_no_oracle(self):
        # A wrong password must not reveal that a pending account exists.
        self._enable_b2c()
        email = 'pending2@example.com'
        self.api('POST', '/auth/signup',
                 {'name': 'Pending Two', 'email': email, 'password': PASSWORD})

        response, body = self.api('POST', '/auth/login',
                                  {'login': email, 'password': 'wrong-password'})
        self.assert_api_error(response, body, 401, 'unauthorized')

    # -- confirm ---------------------------------------------------------

    def test_confirm_activates_and_logs_in(self):
        self._enable_b2c()
        email = 'confirmme@example.com'
        self.api('POST', '/auth/signup',
                 {'name': 'Confirm Me', 'email': email, 'password': PASSWORD})
        user = self._find_user(email)
        token = user._odusite_email_confirm_token()

        response, body = self.api('POST', '/auth/confirm', {'token': token})
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertTrue(data['access_token'])
        self.assertTrue(data['refresh_token'])
        self.assertEqual(data['expires_in'], 900)
        self.assertEqual(data['user']['id'], user.id)
        payload = jwt_lib.verify(data['access_token'], self.jwt_secret)
        self.assertEqual(payload['typ'], 'access')
        self.assertEqual(payload['sub'], user.id)

        user.invalidate_recordset()
        self.assertTrue(user.active)
        self.assertTrue(user.odusite_email_confirmed)

        # Login now works.
        response, body = self.api('POST', '/auth/login',
                                  {'login': email, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, body)

    def test_confirm_rejects_bad_tokens(self):
        self._enable_b2c()
        email = 'badtoken@example.com'
        self.api('POST', '/auth/signup',
                 {'name': 'Bad Token', 'email': email, 'password': PASSWORD})
        user = self._find_user(email)
        now = int(time.time())

        # Forged signature -> 400 invalid_token.
        forged = jwt_lib.sign(
            {'sub': user.id, 'typ': 'email_confirm', 'iat': now,
             'exp': now + 3600, 'jti': 'x'}, 'not-the-real-secret')
        response, body = self.api('POST', '/auth/confirm', {'token': forged})
        self.assert_api_error(response, body, 400, 'invalid_token')

        # Wrong token type -> 400 invalid_token.
        wrong_typ = jwt_lib.sign(
            {'sub': user.id, 'typ': 'access', 'iat': now,
             'exp': now + 3600, 'jti': 'x'}, self.jwt_secret)
        response, body = self.api('POST', '/auth/confirm', {'token': wrong_typ})
        self.assert_api_error(response, body, 400, 'invalid_token')

        # Expired -> 401 token_expired.
        expired = jwt_lib.sign(
            {'sub': user.id, 'typ': 'email_confirm', 'iat': now - 100,
             'exp': now - 10, 'jti': 'x'}, self.jwt_secret)
        response, body = self.api('POST', '/auth/confirm', {'token': expired})
        self.assert_api_error(response, body, 401, 'token_expired')

        # Missing token -> 400 bad_request.
        response, body = self.api('POST', '/auth/confirm', {})
        self.assert_api_error(response, body, 400, 'bad_request')

        # The account remains unusable after all failed attempts.
        user.invalidate_recordset()
        self.assertFalse(user.active)
        self.assertFalse(user.odusite_email_confirmed)

    # -- resend ----------------------------------------------------------

    def test_resend_never_enumerates(self):
        self._enable_b2c()
        email = 'resend@example.com'
        self.api('POST', '/auth/signup',
                 {'name': 'Re Send', 'email': email, 'password': PASSWORD})

        # Unconfirmed account, unknown account and empty body all answer ok.
        for payload in ({'email': email},
                        {'email': 'ghost@example.com'},
                        {}):
            response, body = self.api('POST', '/auth/confirm/resend', payload)
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body['data'], {'ok': True})

    # -- invited signup (token) -----------------------------------------

    def test_invited_signup_autologs_in(self):
        # An invited partner (with a valid signup token) skips the email step.
        partner = self.env['res.partner'].sudo().create({
            'name': 'Invited Guest', 'email': 'invited@example.com'})
        partner.signup_prepare()
        token = partner._generate_signup_token()

        response, body = self.api('POST', '/auth/signup', {
            'name': 'Invited Guest', 'email': 'invited@example.com',
            'password': PASSWORD, 'token': token})
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertTrue(data['access_token'])
        self.assertTrue(data['refresh_token'])

        user = self._find_user('invited@example.com')
        self.assertTrue(user)
        self.assertTrue(user.active)
        self.assertTrue(user.odusite_email_confirmed)

    # -- settings toggle -------------------------------------------------

    def test_settings_toggle_flips_invitation_scope(self):
        Settings = self.env['res.config.settings']

        Settings.create({'odusite_allow_signup': True}).set_values()
        self.assertEqual(
            self.ICP.get_param('auth_signup.invitation_scope'), 'b2c')
        self.assertTrue(Settings.get_values()['odusite_allow_signup'])

        Settings.create({'odusite_allow_signup': False}).set_values()
        self.assertEqual(
            self.ICP.get_param('auth_signup.invitation_scope'), 'b2b')
        self.assertFalse(Settings.get_values()['odusite_allow_signup'])
