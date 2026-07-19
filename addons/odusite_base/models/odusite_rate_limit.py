"""Race-safe per-key (per-IP) submission throttle.

Backs the anti-abuse limits on public write endpoints (contact / newsletter /
event registration / auth). One row per key with an atomic
``INSERT ... ON CONFLICT`` counter: concurrent requests cannot lose updates
(unlike a single JSON ``ir.config_parameter``) and each key is an isolated row,
so there is no global write hotspot. The site forwards Cloudflare's client IP
in ``X-Odusite-Client-IP`` because Cloudflare replaces ``CF-Connecting-IP`` on
cross-zone Worker subrequests.
"""

import ipaddress
import time

from odoo import api, fields, models
from odoo.http import request
from odoo.tools import config

DEFAULT_LIMIT = 20
DEFAULT_WINDOW = 3600  # seconds

# Opt-in flag so the dedicated rate-limit test can exercise enforcement while
# the runner is in test mode (see the guard in ``_enforce``).
FORCE_IN_TESTS_PARAM = 'odusite.rate_limit_force_in_tests'


class OdusiteRateLimit(models.Model):
    _name = 'odusite.rate.limit'
    _description = 'Odusite per-key submission throttle'

    key = fields.Char(required=True)
    window_start = fields.Integer(required=True)
    expires_at = fields.Integer(required=True, default=0)
    hits = fields.Integer(default=0)

    _key_unique = models.Constraint('UNIQUE(key)', 'One throttle row per key.')

    @api.model
    def _client_ip(self):
        headers = request.httprequest.headers
        candidates = (
            headers.get('X-Odusite-Client-IP'),
            headers.get('CF-Connecting-IP'),
            headers.get('X-Forwarded-For', '').split(',')[0].strip(),
            request.httprequest.remote_addr,
        )
        for candidate in candidates:
            try:
                return str(ipaddress.ip_address(candidate))
            except (TypeError, ValueError):
                continue
        return 'unknown'

    @api.model
    def _enforce(self, scope='form', limit=None, window=None, key=None):
        """Count one hit for ``scope:key`` and raise 429 above ``limit``.

        The upsert is atomic at the PostgreSQL level, so two concurrent
        requests both increment the counter (no lost update). A window that has
        elapsed resets the counter in the same statement.
        """
        # Local import: keeps model load independent of the controllers package.
        from ..controllers.api import ApiError

        limit = DEFAULT_LIMIT if limit is None else limit
        window = DEFAULT_WINDOW if window is None else window
        if limit <= 0:
            return
        # Under the test runner every request originates from 127.0.0.1 and
        # counters accumulate across unrelated HttpCase methods; skip unless a
        # test opts in. No overhead in production (test_enable is False there).
        if config['test_enable'] and not self.env['ir.config_parameter'].sudo().get_param(
                FORCE_IN_TESTS_PARAM):
            return
        full_key = '%s:%s' % (scope, key or self._client_ip())
        now = int(time.time())
        # API errors roll back the request cursor. Commit the throttle update on
        # an isolated cursor so rejected attempts still count toward the limit.
        with self.env.registry.cursor() as cr:
            cr.execute(
                """
                INSERT INTO odusite_rate_limit
                    (key, window_start, expires_at, hits)
                VALUES (%(k)s, %(now)s, %(expires)s, 1)
                ON CONFLICT (key) DO UPDATE SET
                    hits = CASE
                        WHEN odusite_rate_limit.expires_at > %(now)s
                        THEN LEAST(odusite_rate_limit.hits + 1, %(cap)s)
                        ELSE 1 END,
                    window_start = CASE
                        WHEN odusite_rate_limit.expires_at > %(now)s
                        THEN odusite_rate_limit.window_start ELSE %(now)s END,
                    expires_at = CASE
                        WHEN odusite_rate_limit.expires_at > %(now)s
                        THEN odusite_rate_limit.expires_at ELSE %(expires)s END
                RETURNING hits
                """,
                {
                    'k': full_key,
                    'now': now,
                    'expires': now + max(1, window),
                    'cap': limit + 1,
                },
            )
            hits = cr.fetchone()[0]
        if hits > limit:
            raise ApiError(429, 'too_many_requests',
                           'Too many submissions, please try again later.')

    @api.autovacuum
    def _gc_rate_limit(self):
        # Drop rows whose window ended over a day ago to keep the table small.
        self.env.cr.execute(
            "DELETE FROM odusite_rate_limit WHERE expires_at < %s",
            (int(time.time()) - 86400,),
        )
