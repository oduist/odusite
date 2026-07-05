"""Portal user extensions for the email double opt-in signup flow.

Fresh self-service (b2c) signups are created inactive and unconfirmed
(:meth:`~odoo.addons.odusite_portal.controllers.auth.OdusiteAuthController.auth_signup`);
the account only becomes usable once the visitor clicks the tokenized
confirmation link emailed to them (``POST /odusite/v1/auth/confirm``).
See ``specs/03-auth.md``.
"""

import logging
import secrets
import time

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.odusite_base.lib import jwt as jwt_lib

_logger = logging.getLogger(__name__)

# Email-confirmation JWT lifetime — 48 hours (specs/03-auth.md).
EMAIL_CONFIRM_TTL = 48 * 3600
# Dedicated token type: never reusable as an access token (odusite_base's
# api._resolve_jwt_strict only accepts typ == 'access').
EMAIL_CONFIRM_TYP = 'email_confirm'


class ResUsers(models.Model):
    _inherit = 'res.users'

    odusite_email_confirmed = fields.Boolean(
        string='Odusite email confirmed',
        default=False,
        copy=False,
        help='Set once the user has confirmed their email address through the '
             'Odusite double opt-in flow. Self-service (b2c) sign-ups start '
             'unconfirmed and inactive until the confirmation link is used; '
             'invited users are confirmed on creation.',
    )

    def _odusite_email_confirm_token(self):
        """Signed, stateless email-confirmation JWT for this user.

        Payload ``{sub, typ: 'email_confirm', iat, exp, jti}`` signed with
        ``odusite.jwt_secret``. The ``email_confirm`` type keeps it from ever
        being accepted as an access token.
        """
        self.ensure_one()
        secret = self.env['ir.config_parameter'].sudo().get_param('odusite.jwt_secret')
        if not secret:
            raise UserError(_('JWT secret is not configured.'))
        now = int(time.time())
        return jwt_lib.sign({
            'sub': self.id,
            'typ': EMAIL_CONFIRM_TYP,
            'iat': now,
            'exp': now + EMAIL_CONFIRM_TTL,
            'jti': secrets.token_hex(16),
        }, secret)

    def _odusite_confirm_url(self):
        """Confirmation link on the Astro site: ``<odusite.site_url>/confirm/<token>``.

        Mirrors :meth:`res.partner._odusite_signup_url`: falls back to the Odoo
        base URL when ``odusite.site_url`` is not configured.
        """
        self.ensure_one()
        site_url = (self.env['ir.config_parameter'].sudo()
                    .get_param('odusite.site_url') or '').rstrip('/')
        if not site_url:
            site_url = (self.get_base_url() or '').rstrip('/')
        return f'{site_url}/confirm/{self._odusite_email_confirm_token()}'

    def _odusite_send_confirmation_email(self):
        """Send (queue) the double opt-in confirmation email. Best effort."""
        self.ensure_one()
        template = self.env.ref(
            'odusite_portal.mail_template_odusite_email_confirm',
            raise_if_not_found=False)
        if not template:
            _logger.warning('Odusite confirmation mail template is missing.')
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': self.email or self.login})
        return True
