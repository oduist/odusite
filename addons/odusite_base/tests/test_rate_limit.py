import time

from odoo.tests.common import TransactionCase, tagged

from ..controllers.api import ApiError


@tagged('post_install', '-at_install')
class TestRateLimit(TransactionCase):

    def _delete_committed_key(self, key):
        with self.env.registry.cursor() as cr:
            cr.execute("DELETE FROM odusite_rate_limit WHERE key = %s", (key,))

    def test_rejected_hit_commits_on_isolated_cursor(self):
        limiter_key = 'test:rollback-persistence'
        RateLimit = self.env['odusite.rate.limit'].sudo()
        self.env['ir.config_parameter'].sudo().set_param(
            'odusite.rate_limit_force_in_tests', '1')
        self._delete_committed_key(limiter_key)
        try:
            RateLimit._enforce(
                scope='test', key='rollback-persistence', limit=1, window=60)
            with self.assertRaises(ApiError):
                RateLimit._enforce(
                    scope='test', key='rollback-persistence', limit=1, window=60)

            with self.env.registry.cursor() as cr:
                cr.execute(
                    "SELECT hits FROM odusite_rate_limit WHERE key = %s",
                    (limiter_key,),
                )
                self.assertEqual(cr.fetchone(), (2,))
        finally:
            self._delete_committed_key(limiter_key)

    def test_gc_keeps_active_long_window(self):
        now = int(time.time())
        RateLimit = self.env['odusite.rate.limit'].sudo()
        active = RateLimit.create({
            'key': 'test:active-long-window',
            'window_start': now - 2 * 86400,
            'expires_at': now + 86400,
            'hits': 3,
        })
        expired = RateLimit.create({
            'key': 'test:expired-window',
            'window_start': now - 3 * 86400,
            'expires_at': now - 2 * 86400,
            'hits': 2,
        })

        RateLimit._gc_rate_limit()

        self.assertTrue(active.exists(), 'an active long window must survive GC')
        self.assertFalse(expired.exists(), 'an old expired window should be deleted')
