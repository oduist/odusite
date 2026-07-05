"""Unit tests for the odusite.refresh.token model
(odusite_portal/models/odusite_refresh_token.py)."""

import hashlib
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRefreshTokenModel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Token = cls.env['odusite.refresh.token']
        partner = cls.env['res.partner'].create({
            'name': 'Token Owner',
            'email': 'token.owner@example.com',
        })
        cls.user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'login': 'token.owner@example.com',
                'name': 'Token Owner',
                'partner_id': partner.id,
                'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
            })

    def _row(self, raw_token):
        return self.Token.sudo().search(
            [('token_hash', '=', self.Token._hash_token(raw_token))])

    # -- _issue ------------------------------------------------------------

    def test_issue_stores_hash_only(self):
        raw = self.Token._issue(self.user, user_agent='A' * 600, ip='203.0.113.7')
        self.assertIsInstance(raw, str)
        self.assertTrue(raw)

        row = self._row(raw)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.user_id, self.user)
        self.assertEqual(row.token_hash, hashlib.sha256(raw.encode()).hexdigest())
        self.assertNotEqual(row.token_hash, raw)
        self.assertFalse(row.revoked)
        self.assertFalse(row.last_used_at)
        self.assertEqual(row.user_agent, 'A' * 512)  # truncated for audit
        self.assertEqual(row.ip, '203.0.113.7')
        remaining = row.expires_at - fields.Datetime.now()
        self.assertTrue(timedelta(days=29) < remaining <= timedelta(days=30))

    # -- _consume ------------------------------------------------------------

    def test_consume_rotates(self):
        raw = self.Token._issue(self.user)
        consumed = self.Token._consume(raw)
        self.assertEqual(consumed, self.user)

        row = self._row(raw)
        self.assertTrue(row.revoked)
        self.assertTrue(row.last_used_at)

        # Single use: a second consume of the same token fails.
        self.assertFalse(self.Token._consume(raw))

    def test_consume_expired(self):
        raw = self.Token._issue(self.user)
        self._row(raw).write(
            {'expires_at': fields.Datetime.now() - timedelta(seconds=1)})
        self.assertFalse(self.Token._consume(raw))
        # Expired rows are rejected before rotation and stay untouched
        # (cleaned up later by _gc).
        self.assertFalse(self._row(raw).revoked)

    def test_consume_inactive_user(self):
        raw = self.Token._issue(self.user)
        self.user.active = False
        self.assertFalse(self.Token._consume(raw))
        # The row is burned even though no user is returned: _consume revokes
        # before checking the owner is still active.
        self.assertTrue(self._row(raw).revoked)

    def test_consume_garbage(self):
        for value in (None, '', 42, b'bytes', 'unknown-token'):
            self.assertFalse(self.Token._consume(value))

    # -- _revoke / _revoke_all -------------------------------------------------

    def test_revoke(self):
        raw = self.Token._issue(self.user)
        self.Token._revoke(raw)
        row = self._row(raw)
        self.assertTrue(row.revoked)
        self.assertTrue(row.last_used_at)
        self.assertFalse(self.Token._consume(raw))

        # Idempotent, and safe with garbage input.
        self.Token._revoke(raw)
        self.Token._revoke(None)
        self.Token._revoke(42)
        self.Token._revoke('unknown-token')

    def test_revoke_all_keeps_given_token(self):
        raw1 = self.Token._issue(self.user)
        raw2 = self.Token._issue(self.user)
        raw3 = self.Token._issue(self.user)

        self.Token._revoke_all(self.user, keep_raw_token=raw2)
        self.assertTrue(self._row(raw1).revoked)
        self.assertFalse(self._row(raw2).revoked)
        self.assertTrue(self._row(raw3).revoked)
        self.assertEqual(self.Token._consume(raw2), self.user)

        # Without keep_raw_token everything goes.
        raw4 = self.Token._issue(self.user)
        raw5 = self.Token._issue(self.user)
        self.Token._revoke_all(self.user)
        self.assertTrue(self._row(raw4).revoked)
        self.assertTrue(self._row(raw5).revoked)

    # -- _gc ---------------------------------------------------------------

    def test_gc_removes_stale_rows(self):
        now = fields.Datetime.now()
        raw_active = self.Token._issue(self.user)
        raw_expired = self.Token._issue(self.user)
        raw_revoked_old = self.Token._issue(self.user)
        raw_revoked_fresh = self.Token._issue(self.user)

        self._row(raw_expired).write({'expires_at': now - timedelta(days=10)})
        self._row(raw_revoked_old).write({'revoked': True})
        self._row(raw_revoked_fresh).write({'revoked': True})

        # Age the revoked row beyond the 7-day grace period (write_date is
        # ORM-managed, so it must be forced through SQL).
        row_revoked_old = self._row(raw_revoked_old)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE odusite_refresh_token SET write_date = %s WHERE id = %s",
            (now - timedelta(days=10), row_revoked_old.id))
        self.env.invalidate_all()

        self.Token._gc()

        self.assertTrue(self._row(raw_active), 'active token must survive _gc')
        self.assertFalse(self._row(raw_expired), 'long-expired token must be deleted')
        self.assertFalse(self._row(raw_revoked_old), 'old revoked token must be deleted')
        self.assertTrue(self._row(raw_revoked_fresh),
                        'recently revoked token must be kept for audit')
