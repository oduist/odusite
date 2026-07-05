"""Tests for GET /odusite/v1/search (unified website search).

The endpoint federates whatever website.searchable.mixin models are installed
in the database. The tests use product.template (website_sale, pulled in by
other odusite modules in the test environment) as the reference searchable
model and skip when it is not available.
"""

import unittest
from urllib.parse import urlencode

from odoo.tests.common import tagged

from .common import OdusiteHttpCase


@tagged('post_install', '-at_install')
class TestSearchApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if ('product.template' not in cls.env
                or not hasattr(cls.env['product.template'], '_search_get_detail')):
            raise unittest.SkipTest(
                'website_sale is not installed — no searchable reference model')
        cls.published_product = cls.env['product.template'].create({
            'name': 'Zephyrion Search Widget',
            'sale_ok': True,
            'is_published': True,
            'list_price': 10.0,
        })
        cls.unpublished_product = cls.env['product.template'].create({
            'name': 'Zephyrion Search Hidden Gadget',
            'sale_ok': True,
            'is_published': False,
            'list_price': 10.0,
        })

    def search(self, **params):
        return self.api('GET', '/search?' + urlencode(params))

    def product_results(self, body):
        return [item for item in body['data']['results']
                if item['type'] == 'product.template']

    def test_search_finds_published_product(self):
        response, body = self.search(q='zephyrion')
        self.assertEqual(response.status_code, 200)
        products = self.product_results(body)
        found = [item for item in products if item['id'] == self.published_product.id]
        self.assertTrue(found, f'published product not in results: {body}')
        item = found[0]
        self.assertEqual(item['name'], 'Zephyrion Search Widget')
        self.assertTrue(item['url'].startswith('/shop/'), item['url'])
        self.assertGreaterEqual(body['meta']['count'], 1)

    def test_search_never_leaks_unpublished(self):
        # Multi-word search targeting the unpublished record specifically
        # (multi-word also disables fuzzy rewriting upstream).
        response, body = self.search(q='zephyrion hidden gadget')
        self.assertEqual(response.status_code, 200)
        ids = [item['id'] for item in self.product_results(body)]
        self.assertNotIn(self.unpublished_product.id, ids)

        # And it must not show up in a broad search either.
        response, body = self.search(q='zephyrion')
        self.assertEqual(response.status_code, 200)
        ids = [item['id'] for item in self.product_results(body)]
        self.assertNotIn(self.unpublished_product.id, ids)

    def test_search_empty_q_is_400(self):
        response, body = self.api('GET', '/search')
        self.assert_api_error(response, body, 400, 'bad_request')

        response, body = self.search(q='   ')
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_search_types_filter(self):
        response, body = self.search(q='zephyrion', types='product.template')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.product_results(body))
        self.assertTrue(all(item['type'] == 'product.template'
                            for item in body['data']['results']))

        # A types filter excluding products must not return any product.
        response, body = self.search(q='zephyrion', types='blog.post')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.product_results(body))

    def test_search_unknown_type_graceful_empty(self):
        # Types not backed by any installed searchable model → empty result,
        # not an error (the site may request types whose addon is missing).
        response, body = self.search(q='zephyrion', types='no.such.model')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['data']['results'], [])
        self.assertEqual(body['meta']['count'], 0)

    def test_search_website_pages_not_exposed(self):
        # website.page is intentionally excluded (marketing pages live in
        # Astro), even when explicitly requested.
        response, body = self.search(q='home', types='website.page')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['data']['results'], [])

    def test_search_invalid_limit_is_400(self):
        response, body = self.search(q='zephyrion', limit='abc')
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_search_blog_post_when_installed(self):
        env = self.env
        if 'blog.post' not in env or not hasattr(env['blog.post'], '_search_get_detail'):
            self.skipTest('website_blog is not installed')
        blog = env['blog.blog'].create({'name': 'Zephyrion Chronicles'})
        post = env['blog.post'].create({
            'name': 'Zephyrion voyage report',
            'blog_id': blog.id,
            'is_published': True,
            'post_date': '2020-01-01',
        })
        response, body = self.search(q='voyage', types='blog.post')
        self.assertEqual(response.status_code, 200)
        found = [item for item in body['data']['results']
                 if item['type'] == 'blog.post' and item['id'] == post.id]
        self.assertTrue(found, f'blog post not in results: {body}')
        self.assertTrue(found[0]['url'].startswith('/blog/'), found[0]['url'])
