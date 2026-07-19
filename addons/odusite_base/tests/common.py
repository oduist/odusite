"""Shared test helpers for odusite_* API tests.

Usage in other modules::

    from odoo.addons.odusite_base.tests.common import OdusiteHttpCase

    @tagged('post_install', '-at_install')
    class TestBlogApi(OdusiteHttpCase):
        def test_posts(self):
            response, body = self.api('GET', '/blog/posts')
            self.assertEqual(response.status_code, 200)
"""

import json
import time

from odoo.tests.common import HttpCase

from ..lib import jwt as jwt_lib


class OdusiteHttpCase(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        cls.odusite_token = icp.get_param('odusite.token')
        if not cls.odusite_token:
            cls.odusite_token = 'test-odusite-token'
            icp.set_param('odusite.token', cls.odusite_token)
        cls.jwt_secret = icp.get_param('odusite.jwt_secret')
        if not cls.jwt_secret:
            cls.jwt_secret = 'test-odusite-jwt-secret'
            icp.set_param('odusite.jwt_secret', cls.jwt_secret)
        cls.website = cls.env['website'].search([], order='sequence, id', limit=1)

    # -- HTTP ------------------------------------------------------------

    def api(self, method, path, payload=None, token=True, bearer=None,
            cart=None, headers=None, files=None):
        """Call an /odusite/v1 endpoint. Returns (requests.Response, body).

        ``body`` is the decoded JSON (dict) or None for non-JSON responses.
        """
        request_headers = {}
        if token:
            request_headers['X-Odusite-Token'] = self.odusite_token
        if bearer:
            request_headers['Authorization'] = f'Bearer {bearer}'
        if cart:
            request_headers['X-Odusite-Cart'] = cart
        if headers:
            request_headers.update(headers)

        kwargs = {'headers': request_headers, 'timeout': 60}
        if files is not None:
            kwargs['files'] = files
            if payload:
                kwargs['data'] = payload
        elif payload is not None:
            request_headers.setdefault('Content-Type', 'application/json')
            kwargs['data'] = json.dumps(payload)

        response = self.opener.request(
            method, self.base_url() + '/odusite/v1' + path, **kwargs)
        body = None
        if 'application/json' in response.headers.get('Content-Type', ''):
            body = response.json()
        return response, body

    def assert_api_error(self, response, body, status, code):
        self.assertEqual(response.status_code, status)
        self.assertTrue(body and 'error' in body, f'expected error body, got: {body}')
        self.assertEqual(body['error']['code'], code)

    def clear_rate_limit(self, key):
        self.env['odusite.rate.limit'].sudo().search([('key', '=', key)]).unlink()

    def rate_limit_hits(self, key):
        row = self.env['odusite.rate.limit'].sudo().search(
            [('key', '=', key)], limit=1)
        return row.hits if row else None

    # -- Auth helpers ----------------------------------------------------

    @classmethod
    def create_portal_user(cls, login='portal.tester@example.com',
                           password='Portal123!secure', name='Portal Tester'):
        partner = cls.env['res.partner'].create({'name': name, 'email': login})
        user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'login': login,
            'name': name,
            'partner_id': partner.id,
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        # Set the password through the classic path so _check_credentials works.
        user.password = password
        return user

    def login_portal(self, user=None, login=None, password='Portal123!secure'):
        """Log in through the real /auth/login endpoint. Returns (access, refresh)."""
        login = login or (user and user.login)
        response, body = self.api('POST', '/auth/login',
                                  {'login': login, 'password': password})
        assert response.status_code == 200, f'login failed: {body}'
        return body['data']['access_token'], body['data']['refresh_token']

    def make_access_token(self, user, ttl=900, typ='access'):
        """Forge a JWT directly (unit-level shortcut, bypasses /auth/login)."""
        now = int(time.time())
        return jwt_lib.sign({
            'sub': user.id,
            'pid': user.partner_id.id,
            'typ': typ,
            'iat': now,
            'exp': now + ttl,
            'jti': f'test-{user.id}-{now}',
        }, self.jwt_secret)
