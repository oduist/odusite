from urllib.parse import urlencode

from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _odusite_signup_url(self):
        """Signup/reset-password URL pointing to the Astro site.

        Replaces ``_get_signup_url_for_action`` (auth_signup) in the mail
        templates overridden by this module (data/mail_template_data.xml), so
        emailed links land on ``<odusite.site_url>/portal/reset/<token>``
        instead of the Odoo ``/web`` routes (specs/03-auth.md, "Emails").
        Falls back to the stock URL when ``odusite.site_url`` is not set.

        The token is the standard auth_signup signed token
        (``res.partner._generate_signup_token``), consumed by
        POST /odusite/v1/auth/password/reset.
        """
        self.ensure_one()
        partner_sudo = self.sudo()
        site_url = (self.env['ir.config_parameter'].sudo()
                    .get_param('odusite.site_url') or '').rstrip('/')
        if not site_url:
            return partner_sudo._get_signup_url_for_action()[self.id]
        token = partner_sudo._generate_signup_token()
        login = (partner_sudo.user_ids[:1].login or partner_sudo.email or '')
        query = urlencode({
            'login': login,
            'type': partner_sudo.signup_type or 'reset',
        })
        # _generate_signup_token() output is base64url: safe in a path segment.
        return f'{site_url}/portal/reset/{token}?{query}'
