"""JWT authentication endpoints /odusite/v1/auth/* (specs/03-auth.md).

Credentials are verified through the stock ``res.users._login`` machinery —
no Odoo session is ever created; the client only gets a short-lived access
JWT plus a rotating refresh token (``odusite.refresh.token``).
"""

import logging
import secrets
import time

from odoo import http
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.tools import single_email_re

from odoo.addons.auth_signup.models.res_partner import SignupError
from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    get_param,
    odusite_route,
)
from odoo.addons.odusite_base.lib import jwt as jwt_lib

_logger = logging.getLogger(__name__)

ACCESS_TOKEN_TTL = 900  # seconds — 15 minutes (specs/03-auth.md)


class OdusiteAuthController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _serialize_user(self, user):
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email or user.login,
            'partner_id': user.partner_id.id,
            'lang': user.lang or None,
            'is_portal': user._is_portal(),
        }

    def _issue_access_token(self, user):
        secret = get_param('odusite.jwt_secret')
        if not secret:
            raise ApiError(500, 'internal', 'JWT secret is not configured.')
        now = int(time.time())
        return jwt_lib.sign({
            'sub': user.id,
            'pid': user.partner_id.id,
            'typ': 'access',
            'iat': now,
            'exp': now + ACCESS_TOKEN_TTL,
            'jti': secrets.token_hex(16),
        }, secret)

    def _auth_response(self, user):
        refresh_token = request.env['odusite.refresh.token']._issue(
            user,
            user_agent=request.httprequest.user_agent.string,
            ip=request.httprequest.remote_addr,
        )
        return {
            'access_token': self._issue_access_token(user),
            'refresh_token': refresh_token,
            'expires_in': ACCESS_TOKEN_TTL,
            'user': self._serialize_user(user),
        }

    def _login_user(self, login, password):
        """Verify credentials without creating a session.

        Mirrors ``odoo.http.Session.authenticate`` ->
        ``res.users._login(credential, user_agent_env)``
        (odoo/addons/base/models/res_users.py), including the login cooldown
        and MFA detection, but skips the session/web.base.url side effects.
        """
        credential = {'login': login, 'password': password, 'type': 'password'}
        try:
            auth_info = request.env['res.users']._login(
                credential, {'interactive': True})
        except AccessDenied:
            # Same message whether the login exists or not.
            raise ApiError(401, 'unauthorized', 'Invalid credentials')
        user = request.env['res.users'].sudo().browse(auth_info['uid'])
        if not user.exists() or user._is_public():
            raise ApiError(401, 'unauthorized', 'Invalid credentials')
        if auth_info.get('mfa') != 'skip' and user._mfa_type():
            # MFA-enabled accounts cannot log in through the site (phase 2).
            raise ApiError(
                409, 'mfa_required',
                'Multi-factor authentication is enabled on this account and '
                'is not supported by the site login yet.')
        return user

    def _signup_token_info(self, token):
        """Resolve an auth_signup token to its partner info, or 400."""
        try:
            info = request.env['res.partner'].sudo()._signup_retrieve_info(token)
        except Exception:
            # verify_hash_signed raises on malformed base64/version bytes.
            info = None
        if not info:
            raise ApiError(400, 'bad_request', 'Invalid or expired token.')
        return info

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    @odusite_route(f'{API_PREFIX}/auth/login', methods=['POST'])
    def auth_login(self, login=None, password=None, **params):
        if not isinstance(login, str) or not isinstance(password, str) \
                or not login.strip() or not password:
            raise ApiError(400, 'bad_request', 'login and password are required.')
        user = self._login_user(login.strip(), password)
        return self._auth_response(user)

    @odusite_route(f'{API_PREFIX}/auth/refresh', methods=['POST'])
    def auth_refresh(self, refresh_token=None, **params):
        user = request.env['odusite.refresh.token']._consume(refresh_token)
        if not user:
            raise ApiError(401, 'unauthorized', 'Invalid or expired refresh token.')
        return self._auth_response(user)

    @odusite_route(f'{API_PREFIX}/auth/logout', methods=['POST'])
    def auth_logout(self, refresh_token=None, **params):
        if params.get('all'):
            if request.env.user._is_public():
                raise ApiError(401, 'unauthorized',
                               'Revoking all sessions requires a Bearer access token.')
            request.env['odusite.refresh.token']._revoke_all(request.env.user)
            return {'ok': True}
        if not isinstance(refresh_token, str) or not refresh_token:
            raise ApiError(400, 'bad_request', 'refresh_token is required.')
        request.env['odusite.refresh.token']._revoke(refresh_token)
        return {'ok': True}

    @odusite_route(f'{API_PREFIX}/auth/signup', methods=['POST'])
    def auth_signup(self, name=None, email=None, password=None, token=None, **params):
        """B2C signup or signup by invitation token.

        Mirrors AuthSignupHome.do_signup/_prepare_signup_values
        (auth_signup/controllers/main.py) on top of ``res.users.signup``.
        """
        if not isinstance(password, str) or not password.strip():
            raise ApiError(422, 'validation_error', 'Password is required.',
                           {'fields': {'password': 'This field is required.'}})
        token_info = {}
        if token:
            token_info = self._signup_token_info(token)
        else:
            if request.env['res.users']._get_signup_invitation_scope() != 'b2c':
                raise ApiError(403, 'forbidden',
                               'Sign up is only allowed for invited users.')
            if not isinstance(email, str) or not single_email_re.match(email.strip()):
                raise ApiError(422, 'validation_error', 'A valid email is required.',
                               {'fields': {'email': 'A valid email address is required.'}})
            if not isinstance(name, str) or not name.strip():
                raise ApiError(422, 'validation_error', 'Name is required.',
                               {'fields': {'name': 'This field is required.'}})

        values = {
            'login': ((email if isinstance(email, str) else '')
                      or token_info.get('login') or '').strip(),
            'name': ((name if isinstance(name, str) else '')
                     or token_info.get('name') or '').strip(),
            'password': password,
        }
        # Mirror _prepare_signup_values: keep the request language when installed.
        supported_langs = [code for code, _label in request.env['res.lang'].get_installed()]
        lang = request.env.context.get('lang', '')
        if lang in supported_langs:
            values['lang'] = lang

        try:
            login, _password = request.env['res.users'].sudo().signup(values, token)
        except (SignupError, ValueError, AssertionError) as exc:
            Users = request.env['res.users'].sudo().with_context(active_test=False)
            if values['login'] and Users.search_count(
                    Users._get_login_domain(values['login']), limit=1):
                raise ApiError(
                    422, 'validation_error',
                    'Another user is already registered using this email address.',
                    {'fields': {'email': 'Already registered.'}})
            _logger.warning('Odusite signup failed: %s', exc)
            raise ApiError(400, 'bad_request', 'Could not create a new account.')
        # Note: the stock b2c controller also sends
        # auth_signup.mail_template_user_signup_account_created here; skipped
        # in v1 because its links point to the Odoo backend (/web/login).
        user = self._login_user(login, password)
        return self._auth_response(user)

    @odusite_route(f'{API_PREFIX}/auth/password/forgot', methods=['POST'])
    def auth_password_forgot(self, login=None, **params):
        if not isinstance(login, str) or not login.strip():
            raise ApiError(400, 'bad_request', 'login is required.')
        if get_param('auth_signup.reset_password') != 'True':
            _logger.info('Odusite password reset requested but the feature is '
                         'disabled (auth_signup.reset_password).')
            return {'ok': True}
        try:
            request.env['res.users'].sudo().reset_password(login.strip())
        except Exception:
            # reset_password raises for unknown/duplicate logins and mail
            # issues; always answer OK to prevent user enumeration.
            _logger.info('Odusite password reset failed', exc_info=True)
        return {'ok': True}

    @odusite_route(f'{API_PREFIX}/auth/password/reset', methods=['POST'])
    def auth_password_reset(self, token=None, password=None, **params):
        """Set a new password from an auth_signup reset token.

        Uses ``res.users.signup(values, token)``: with a token and an existing
        user it writes the new password on that user
        (auth_signup/models/res_users.py). All refresh tokens of the user are
        revoked afterwards.
        """
        if not isinstance(token, str) or not token:
            raise ApiError(400, 'bad_request', 'token is required.')
        if not isinstance(password, str) or not password.strip():
            raise ApiError(422, 'validation_error', 'Password is required.',
                           {'fields': {'password': 'This field is required.'}})
        info = self._signup_token_info(token)
        values = {
            'login': info.get('login'),
            'name': info.get('name'),
            'password': password,
        }
        try:
            login, _password = request.env['res.users'].sudo().signup(values, token)
        except (SignupError, ValueError, AssertionError) as exc:
            _logger.warning('Odusite password reset failed: %s', exc)
            raise ApiError(400, 'bad_request', 'Could not reset the password.')
        Users = request.env['res.users'].sudo()
        user = Users.search(Users._get_login_domain(login), limit=1)
        if user:
            request.env['odusite.refresh.token']._revoke_all(user)
        return {'ok': True}
