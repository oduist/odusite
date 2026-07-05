import hashlib
import hmac
import json
import logging
from datetime import timedelta

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
SEND_BATCH = 200


class OdusiteWebhookEvent(models.Model):
    _name = 'odusite.webhook.event'
    _description = 'Odusite cache invalidation event'
    _order = 'id'

    model = fields.Char(required=True)
    res_id = fields.Integer()
    event = fields.Selection(
        [
            ('created', 'Created'),
            ('updated', 'Updated'),
            ('deleted', 'Deleted'),
            ('published', 'Published'),
            ('unpublished', 'Unpublished'),
        ],
        required=True,
    )
    tags = fields.Char(required=True, help='Comma-separated cache tags')
    state = fields.Selection(
        [('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')],
        default='pending', index=True, required=True,
    )
    attempts = fields.Integer(default=0)
    payload = fields.Text()

    @api.model
    def _enqueue(self, model_name, res_id, event, tags):
        domain = [
            ('state', '=', 'pending'),
            ('model', '=', model_name),
            ('res_id', '=', res_id),
            ('event', '=', event),
        ]
        if self.search_count(domain, limit=1):
            return
        self.create({
            'model': model_name,
            'res_id': res_id,
            'event': event,
            'tags': ','.join(tags),
        })

    @api.model
    def _purge_all(self):
        """Enqueue a full-purge event (tag 'all')."""
        self.create({'model': 'website', 'res_id': 0, 'event': 'updated', 'tags': 'all'})

    @api.model
    def _process_queue(self):
        icp = self.env['ir.config_parameter'].sudo()
        site_url = (icp.get_param('odusite.site_url') or '').rstrip('/')
        secret = icp.get_param('odusite.revalidate_secret')
        if not site_url or not secret:
            return
        events = self.search([('state', '=', 'pending')], limit=SEND_BATCH)
        if not events:
            return
        body = json.dumps({
            'events': [
                {
                    'model': event.model,
                    'id': event.res_id,
                    'event': event.event,
                    'tags': (event.tags or '').split(','),
                    'at': fields.Datetime.to_string(event.write_date),
                }
                for event in events
            ],
        })
        signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        try:
            response = requests.post(
                f'{site_url}/api/revalidate',
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'X-Odusite-Signature': signature,
                },
                timeout=10,
            )
            delivered = response.status_code < 300
        except requests.RequestException:
            delivered = False
        if delivered:
            events.write({'state': 'sent'})
        else:
            _logger.warning('Odusite revalidate webhook delivery failed (%s events)', len(events))
            for event in events:
                event.attempts += 1
            events.filtered(lambda e: e.attempts >= MAX_ATTEMPTS).write({'state': 'failed'})

    @api.model
    def _gc(self):
        cutoff_sent = fields.Datetime.now() - timedelta(days=7)
        cutoff_failed = fields.Datetime.now() - timedelta(days=30)
        self.search([
            '|',
            '&', ('state', '=', 'sent'), ('write_date', '<', cutoff_sent),
            '&', ('state', '=', 'failed'), ('write_date', '<', cutoff_failed),
        ]).unlink()

    def action_retry(self):
        self.write({'state': 'pending', 'attempts': 0})
