"""Rotating refresh tokens for the Odusite portal JWT auth (specs/03-auth.md).

Raw tokens are 48 random bytes, base64url-encoded, and are never stored:
only their sha256 hash is kept. Access is restricted to base.group_system;
all API access goes through the classmethod helpers below (internal sudo).
"""

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models

REFRESH_TOKEN_TTL_DAYS = 30
GC_KEEP_DAYS = 7


class OdusiteRefreshToken(models.Model):
    _name = 'odusite.refresh.token'
    _description = 'Odusite portal refresh token'
    _order = 'id desc'

    user_id = fields.Many2one(
        'res.users', required=True, ondelete='cascade', index=True)
    token_hash = fields.Char(required=True, index=True,
                             help='sha256 hex digest of the raw refresh token')
    expires_at = fields.Datetime(required=True)
    revoked = fields.Boolean(default=False)
    user_agent = fields.Char()
    ip = fields.Char()
    last_used_at = fields.Datetime()

    _token_hash_unique = models.Constraint(
        'UNIQUE (token_hash)',
        'Refresh token hash must be unique.',
    )

    @api.model
    def _hash_token(self, raw_token):
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @api.model
    def _issue(self, user, user_agent=None, ip=None):
        """Create a refresh token row for `user` and return the raw token
        (the only moment it exists in clear text)."""
        raw_token = secrets.token_urlsafe(48)
        self.sudo().create({
            'user_id': user.id,
            'token_hash': self._hash_token(raw_token),
            'expires_at': fields.Datetime.now() + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
            'user_agent': (user_agent or '')[:512] or False,
            'ip': (ip or '')[:64] or False,
        })
        return raw_token

    @api.model
    def _consume(self, raw_token):
        """Validate `raw_token` and revoke it (rotation).

        The claim is a single atomic UPDATE (``... WHERE revoked = false ...
        RETURNING``) so two concurrent refreshes with the same token cannot both
        succeed — exactly one wins the rotation (closing the previous
        check-then-write race). A miss (unknown / already rotated / expired)
        returns an empty recordset, as before.

        :return: the owning res.users record (sudo), or an empty recordset
                 when the token is unknown, revoked, expired or the user is
                 inactive.
        """
        empty_user = self.env['res.users'].sudo().browse()
        if not raw_token or not isinstance(raw_token, str):
            return empty_user
        token_hash = self._hash_token(raw_token)
        now = fields.Datetime.now()
        self.env.cr.execute(
            """
            UPDATE odusite_refresh_token
               SET revoked = true, last_used_at = %s
             WHERE token_hash = %s AND revoked = false AND expires_at >= %s
            RETURNING user_id
            """,
            (now, token_hash, now),
        )
        row = self.env.cr.fetchone()
        if not row:
            return empty_user
        # The raw UPDATE bypassed the ORM cache; drop it before reading back.
        self.invalidate_model(['revoked', 'last_used_at'])
        user = self.env['res.users'].sudo().browse(row[0])
        return user if user.active else empty_user

    @api.model
    def _revoke(self, raw_token):
        """Revoke a single token by raw value (idempotent, no oracle)."""
        if not raw_token or not isinstance(raw_token, str):
            return
        self.sudo().search([
            ('token_hash', '=', self._hash_token(raw_token)),
            ('revoked', '=', False),
        ]).write({'revoked': True, 'last_used_at': fields.Datetime.now()})

    @api.model
    def _revoke_all(self, user, keep_raw_token=None):
        """Revoke every active token of `user`.

        :param keep_raw_token: optional raw token to keep alive (used by the
            password change endpoint to preserve the current session).
        """
        domain = [('user_id', '=', user.id), ('revoked', '=', False)]
        if keep_raw_token and isinstance(keep_raw_token, str):
            domain.append(('token_hash', '!=', self._hash_token(keep_raw_token)))
        self.sudo().search(domain).write({'revoked': True})

    @api.model
    def _gc(self):
        """Daily cron: delete tokens expired/revoked more than 7 days ago."""
        cutoff = fields.Datetime.now() - timedelta(days=GC_KEEP_DAYS)
        self.sudo().search([
            '|',
            ('expires_at', '<', cutoff),
            '&', ('revoked', '=', True), ('write_date', '<', cutoff),
        ]).unlink()
