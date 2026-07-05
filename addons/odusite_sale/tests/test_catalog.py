from odoo.tests.common import tagged

from .common import OdusiteSaleCase


@tagged('post_install', '-at_install')
class TestShopCatalog(OdusiteSaleCase):

    # -- /shop/categories -------------------------------------------------

    def test_categories_tree(self):
        response, body = self.api('GET', '/shop/categories')
        self.assertEqual(response.status_code, 200)
        roots = {category['id']: category for category in body['data']}
        # The child category is nested under its parent, not a root.
        self.assertIn(self.categ_parent.id, roots)
        self.assertNotIn(self.categ_child.id, roots)

        parent = roots[self.categ_parent.id]
        self.assertEqual(parent['name'], 'Odusite Furniture')
        self.assertEqual(parent['slug'], self._slug(self.categ_parent))
        self.assertIsNone(parent['parent_id'])
        # product_count only counts direct membership (table).
        self.assertEqual(parent['product_count'], 1)

        children = {category['id']: category for category in parent['children']}
        self.assertIn(self.categ_child.id, children)
        child = children[self.categ_child.id]
        self.assertEqual(child['parent_id'], self.categ_parent.id)
        self.assertEqual(child['product_count'], 1)  # chair
        self.assertEqual(child['children'], [])

    # -- /shop/products listing --------------------------------------------

    def test_products_published_only(self):
        response, body = self.api('GET', '/shop/products?limit=100')
        self.assertEqual(response.status_code, 200)
        ids = self._ids(body)
        self.assertIn(self.product_chair.id, ids)
        self.assertIn(self.product_table.id, ids)
        self.assertIn(self.product_shirt.id, ids)
        self.assertNotIn(self.product_hidden.id, ids)

        chair = next(item for item in body['data'] if item['id'] == self.product_chair.id)
        for key in ('id', 'slug', 'name', 'list_price', 'price', 'has_discounted_price',
                    'currency', 'image', 'second_image', 'tags', 'category_ids'):
            self.assertIn(key, chair)
        self.assertEqual(chair['slug'], self._slug(self.product_chair))
        self.assertEqual(chair['price'], 100.0)
        self.assertFalse(chair['has_discounted_price'])
        self.assertEqual(chair['currency'], self.currency.name)
        self.assertIn(self.categ_child.id, chair['category_ids'])

        for key in ('total', 'page', 'limit', 'pages', 'facets'):
            self.assertIn(key, body['meta'])

    def test_products_category_filter(self):
        response, body = self.api('GET', f'/shop/products?category={self.categ_child.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), [self.product_chair.id])

        # child_of semantics: the parent category also matches child products.
        response, body = self.api('GET', f'/shop/products?category={self.categ_parent.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(self._ids(body)),
                         {self.product_chair.id, self.product_table.id})

        # Category is accepted as a slug too.
        response, body = self.api(
            'GET', f'/shop/products?category={self._slug(self.categ_child)}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(body), [self.product_chair.id])

        response, body = self.api('GET', '/shop/products?category=99999999')
        self.assert_api_error(response, body, 404, 'not_found')

    def test_products_search(self):
        response, body = self.api('GET', '/shop/products?search=Odusite+Chair&limit=100')
        self.assertEqual(response.status_code, 200)
        ids = self._ids(body)
        self.assertIn(self.product_chair.id, ids)
        self.assertNotIn(self.product_table.id, ids)
        self.assertNotIn(self.product_shirt.id, ids)
        self.assertNotIn(self.product_hidden.id, ids)

    def test_products_price_filter(self):
        response, body = self.api(
            'GET', '/shop/products?min_price=60&max_price=200&limit=100')
        self.assertEqual(response.status_code, 200)
        ids = self._ids(body)
        self.assertIn(self.product_chair.id, ids)     # 100.0
        self.assertNotIn(self.product_shirt.id, ids)  # 50.0
        self.assertNotIn(self.product_table.id, ids)  # 250.0

        response, body = self.api('GET', '/shop/products?max_price=60&limit=100')
        self.assertEqual(response.status_code, 200)
        ids = self._ids(body)
        self.assertIn(self.product_shirt.id, ids)
        self.assertNotIn(self.product_chair.id, ids)
        self.assertNotIn(self.product_table.id, ids)

    def test_products_order_price_asc(self):
        response, body = self.api('GET', '/shop/products?order=price_asc&limit=100')
        self.assertEqual(response.status_code, 200)
        ids = self._ids(body)
        # shirt (50) < chair (100) < table (250)
        self.assertLess(ids.index(self.product_shirt.id), ids.index(self.product_chair.id))
        self.assertLess(ids.index(self.product_chair.id), ids.index(self.product_table.id))
        prices = [item['price'] for item in body['data']]
        self.assertEqual(prices, sorted(prices))

    def test_products_bad_order(self):
        response, body = self.api('GET', '/shop/products?order=hack')
        self.assert_api_error(response, body, 400, 'bad_request')
        self.assertEqual(body['error']['details']['allowed'],
                         ['name', 'newest', 'price_asc', 'price_desc', 'relevance'])

    def test_products_facets(self):
        response, body = self.api('GET', '/shop/products?limit=100')
        self.assertEqual(response.status_code, 200)
        attributes = {
            attribute['id']: attribute
            for attribute in body['meta']['facets']['attributes']
        }
        self.assertIn(self.color_attribute.id, attributes)
        color = attributes[self.color_attribute.id]
        self.assertEqual(color['name'], 'Odusite Color')
        self.assertEqual(color['display_type'], 'color')
        values = {value['name']: value for value in color['values']}
        self.assertEqual(set(values), {'Red', 'Blue'})
        # Only the shirt carries the attribute: 1 template per value.
        self.assertEqual(values['Red']['count'], 1)
        self.assertEqual(values['Blue']['count'], 1)
        self.assertEqual(values['Red']['html_color'], '#FF0000')

    # -- /shop/products/<id_or_slug> detail ---------------------------------

    def test_product_detail_by_slug(self):
        response, body = self.api(
            'GET', f'/shop/products/{self._slug(self.product_shirt)}')
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertEqual(data['id'], self.product_shirt.id)
        self.assertEqual(data['name'], 'Odusite Shirt')
        self.assertIn('images', data)
        self.assertIn('json_ld', data)

        # Attribute lines with values.
        lines = {line['attribute']['id']: line for line in data['attribute_lines']}
        self.assertIn(self.color_attribute.id, lines)
        color_line = lines[self.color_attribute.id]
        self.assertEqual(color_line['display_type'], 'color')
        self.assertEqual(color_line['create_variant'], 'always')
        values = {value['name']: value for value in color_line['values']}
        self.assertEqual(set(values), {'Red', 'Blue'})
        self.assertEqual(values['Red']['id'], self.ptav_red.id)
        self.assertEqual(values['Red']['price_extra'], 0.0)

        # Combination info of the default variant.
        combination = data['combination']
        self.assertEqual(combination['product_template_id'], self.product_shirt.id)
        self.assertIn(combination['product_id'],
                      self.product_shirt.product_variant_ids.ids)
        self.assertEqual(combination['price'], 50.0)
        self.assertTrue(combination['is_combination_possible'])
        self.assertEqual(combination['currency'], self.currency.name)

        # SEO block.
        self.assertEqual(set(data['seo']),
                         {'title', 'description', 'keywords', 'og_image'})
        self.assertEqual(data['seo']['title'], self.product_shirt.display_name)

    def test_product_detail_by_id(self):
        response, body = self.api('GET', f'/shop/products/{self.product_chair.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['data']['id'], self.product_chair.id)

    def test_product_detail_unpublished_404(self):
        response, body = self.api('GET', f'/shop/products/{self.product_hidden.id}')
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api(
            'GET', f'/shop/products/{self._slug(self.product_hidden)}')
        self.assert_api_error(response, body, 404, 'not_found')

        response, body = self.api('GET', '/shop/products/99999999')
        self.assert_api_error(response, body, 404, 'not_found')

    # -- /shop/products/<id>/combination -------------------------------------

    def test_combination_info(self):
        response, body = self.api(
            'POST', f'/shop/products/{self.product_shirt.id}/combination',
            {'combination': [self.ptav_red.id], 'quantity': 1})
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertEqual(data['product_id'], self.variant_red.id)
        self.assertEqual(data['price'], 50.0)
        self.assertTrue(data['is_combination_possible'])

        response, body = self.api(
            'POST', f'/shop/products/{self.product_shirt.id}/combination',
            {'combination': [self.ptav_blue.id]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['data']['product_id'], self.variant_blue.id)

    def test_combination_wrong_template(self):
        # ptavs of another template are rejected.
        response, body = self.api(
            'POST', f'/shop/products/{self.product_chair.id}/combination',
            {'combination': [self.ptav_red.id]})
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_combination_unpublished_404(self):
        response, body = self.api(
            'POST', f'/shop/products/{self.product_hidden.id}/combination',
            {'combination': []})
        self.assert_api_error(response, body, 404, 'not_found')
