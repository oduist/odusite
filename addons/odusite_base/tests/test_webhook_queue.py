from unittest.mock import patch

import requests

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWebhookQueue(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.queue = cls.env['odusite.webhook.event']
        cls.icp = cls.env['ir.config_parameter'].sudo()

    def test_enqueue_dedupes_pending(self):
        self.queue._enqueue('blog.post', 1, 'updated', ['blog', 'blog:1'])
        self.queue._enqueue('blog.post', 1, 'updated', ['blog', 'blog:1'])
        pending = self.queue.search([
            ('model', '=', 'blog.post'), ('res_id', '=', 1),
            ('event', '=', 'updated'), ('state', '=', 'pending'),
        ])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending.tags, 'blog,blog:1')

    def test_different_events_not_deduped(self):
        self.queue._enqueue('blog.post', 2, 'updated', ['blog'])
        self.queue._enqueue('blog.post', 2, 'published', ['blog'])
        self.assertEqual(self.queue.search_count([
            ('model', '=', 'blog.post'), ('res_id', '=', 2),
            ('state', '=', 'pending'),
        ]), 2)

    def test_process_queue_skips_when_unconfigured(self):
        self.icp.set_param('odusite.site_url', '')
        self.queue._enqueue('blog.post', 3, 'updated', ['blog'])
        with patch.object(requests, 'post') as mocked:
            self.queue._process_queue()
            mocked.assert_not_called()
        self.assertTrue(self.queue.search([
            ('model', '=', 'blog.post'), ('res_id', '=', 3),
            ('state', '=', 'pending'),
        ]))

    def test_process_queue_delivers_and_signs(self):
        self.icp.set_param('odusite.site_url', 'https://site.example.com')
        self.icp.set_param('odusite.revalidate_secret', 'reval-secret')
        self.queue.search([]).unlink()
        self.queue._enqueue('blog.post', 4, 'published', ['blog', 'blog:4'])

        captured = {}

        def fake_post(url, data=None, headers=None, timeout=None):
            captured['url'] = url
            captured['data'] = data
            captured['headers'] = headers

            class FakeResponse:
                status_code = 200
            return FakeResponse()

        with patch('odoo.addons.odusite_base.models.odusite_webhook_event.requests.post',
                   side_effect=fake_post):
            self.queue._process_queue()

        self.assertEqual(captured['url'], 'https://site.example.com/api/revalidate')
        self.assertIn('X-Odusite-Signature', captured['headers'])
        self.assertIn('"blog:4"', captured['data'])
        self.assertFalse(self.queue.search([('state', '=', 'pending')]))

    def test_process_queue_failure_and_retry_cap(self):
        self.icp.set_param('odusite.site_url', 'https://site.example.com')
        self.icp.set_param('odusite.revalidate_secret', 'reval-secret')
        self.queue.search([]).unlink()
        self.queue._enqueue('blog.post', 5, 'deleted', ['blog'])
        event = self.queue.search([('res_id', '=', 5)])

        with patch('odoo.addons.odusite_base.models.odusite_webhook_event.requests.post',
                   side_effect=requests.ConnectionError()):
            for _ in range(5):
                self.queue._process_queue()

        self.assertEqual(event.state, 'failed')
        self.assertEqual(event.attempts, 5)

        event.action_retry()
        self.assertEqual(event.state, 'pending')
        self.assertEqual(event.attempts, 0)
