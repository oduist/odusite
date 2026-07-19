from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase

VALID_PAYLOAD = {
    'name': 'Jane Visitor',
    'email': 'jane.visitor@example.com',
    'message': 'Hello from the odusite tests',
}


@tagged('post_install', '-at_install')
class TestContactForm(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env['crm.team'].create({'name': 'Odusite Web Team'})
        cls.website.crm_default_team_id = cls.team

    def test_contact_valid(self):
        payload = dict(VALID_PAYLOAD, phone='+1 555 0100', company='ACME Test Corp')
        response, body = self.api('POST', '/forms/contact', payload)
        self.assertEqual(response.status_code, 200, body)
        lead_id = body['data']['id']
        self.assertTrue(lead_id)
        lead = self.env['crm.lead'].browse(lead_id)
        self.assertTrue(lead.exists())
        self.assertEqual(lead.type, 'lead')
        self.assertEqual(lead.contact_name, 'Jane Visitor')
        self.assertEqual(lead.email_from, 'jane.visitor@example.com')
        self.assertEqual(lead.phone, '+1 555 0100')
        self.assertEqual(lead.partner_name, 'ACME Test Corp')
        self.assertIn('Hello from the odusite tests', lead.description)
        # No subject -> generated lead name.
        self.assertEqual(lead.name, 'Website contact: Jane Visitor')
        # Website defaults: medium = Website, team from website settings.
        self.assertEqual(lead.medium_id.name.lower(), 'website')
        self.assertEqual(lead.team_id, self.team)
        self.assertEqual(lead.company_id, self.website.company_id)

    def test_contact_missing_required(self):
        response, body = self.api('POST', '/forms/contact', {})
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(set(body['error']['details']['fields']),
                         {'name', 'email', 'message'})

        response, body = self.api('POST', '/forms/contact',
                                  {'name': 'X', 'email': 'x@example.com'})
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(body['error']['details']['fields'], {'message': 'required'})

    def test_contact_invalid_email(self):
        payload = dict(VALID_PAYLOAD, email='not-an-email')
        response, body = self.api('POST', '/forms/contact', payload)
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(body['error']['details']['fields'], {'email': 'invalid'})

    def test_contact_honeypot(self):
        payload = dict(VALID_PAYLOAD, email='spambot@example.com', website_hp='gotcha')
        response, body = self.api('POST', '/forms/contact', payload)
        # Silently accepted, nothing created.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['data'], {'id': 0})
        self.assertFalse(self.env['crm.lead'].search_count(
            [('email_from', '=', 'spambot@example.com')]))

    def test_contact_utm(self):
        payload = dict(
            VALID_PAYLOAD,
            subject='UTM test subject',
            meta={'utm_source': 'newsletter', 'utm_campaign': 'x',
                  'page': '/landing/odusite'},
        )
        response, body = self.api('POST', '/forms/contact', payload)
        self.assertEqual(response.status_code, 200, body)
        lead = self.env['crm.lead'].browse(body['data']['id'])
        self.assertEqual(lead.name, 'UTM test subject')
        # Source/campaign linked (or created) by name, case-insensitively.
        self.assertEqual(lead.source_id.name.lower(), 'newsletter')
        self.assertEqual(lead.campaign_id.name, 'x')
        self.assertIn('/landing/odusite', lead.description)

    def test_contact_rate_limit(self):
        icp = self.env['ir.config_parameter'].sudo()
        client_ip = '198.51.100.20'
        limiter_key = f'contact:{client_ip}'
        headers = {'X-Odusite-Client-IP': client_ip}
        # Enforcement is skipped under the test runner by default (counters
        # accumulate across unrelated cases); this test opts in explicitly.
        icp.set_param('odusite.rate_limit_force_in_tests', '1')
        icp.set_param('odusite.form_rate_limit', '1')
        self.clear_rate_limit(limiter_key)
        try:
            response, body = self.api(
                'POST', '/forms/contact', VALID_PAYLOAD, headers=headers)
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(self.rate_limit_hits(limiter_key), 1)
            response, body = self.api(
                'POST', '/forms/contact', VALID_PAYLOAD, headers=headers)
            self.assert_api_error(response, body, 429, 'too_many_requests')
        finally:
            icp.set_param('odusite.rate_limit_force_in_tests', False)
            icp.set_param('odusite.form_rate_limit', False)
            self.clear_rate_limit(limiter_key)

    def test_generic_form_unknown_model(self):
        # res.users is never in the odusite.api form whitelist. (The full
        # whitelist flow is covered by odusite_project's tests.)
        response, body = self.api('POST', '/forms/generic/res.users',
                                  {'name': 'X', 'login': 'x@example.com'})
        self.assert_api_error(response, body, 404, 'not_found')
