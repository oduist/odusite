from odoo.tests.common import tagged

from .common import OdusiteHttpCase


@tagged('post_install', '-at_install')
class TestApiCore(OdusiteHttpCase):

    def test_token_gate(self):
        response, body = self.api('GET', '/health', token=False)
        self.assert_api_error(response, body, 401, 'unauthorized')

        response, body = self.api('GET', '/health',
                                  headers={'X-Odusite-Token': 'wrong'}, token=False)
        self.assert_api_error(response, body, 401, 'unauthorized')

        response, body = self.api('GET', '/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['data']['status'], 'ok')

    def test_site(self):
        response, body = self.api('GET', '/site')
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertEqual(data['name'], self.website.name)
        self.assertIn('company', data)
        self.assertTrue(data['languages'])
        self.assertEqual(data['default_language'], self.website.default_lang_id.code)

    def test_menus(self):
        response, body = self.api('GET', '/menus')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(body['data'], list)
        for item in body['data']:
            self.assertIn('name', item)
            self.assertIn('url', item)
            self.assertIn('children', item)

    def test_countries(self):
        response, body = self.api('GET', '/countries')
        self.assertEqual(response.status_code, 200)
        codes = {country['code'] for country in body['data']}
        self.assertIn('US', codes)
        usa = next(c for c in body['data'] if c['code'] == 'US')
        self.assertTrue(usa['states'])
        self.assertIn('zip_required', usa)

    def test_sitemap_and_redirects(self):
        response, body = self.api('GET', '/sitemap')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(body['data'], list)

        self.env['website.rewrite'].sudo().create({
            'name': 'test redirect',
            'url_from': '/old-page',
            'url_to': '/new-page',
            'redirect_type': '301',
        })
        response, body = self.api('GET', '/redirects')
        self.assertEqual(response.status_code, 200)
        self.assertIn({'from': '/old-page', 'to': '/new-page', 'type': 301}, body['data'])

    def test_invalid_bearer_degrades_on_public_route(self):
        response, body = self.api('GET', '/health', bearer='not-a-jwt')
        self.assertEqual(response.status_code, 200, body)

    def test_unknown_route_is_404(self):
        response, _body = self.api('GET', '/definitely-not-a-route')
        self.assertEqual(response.status_code, 404)
