"""Shared fixtures for the odusite_sale API tests.

All fixture products get their taxes cleared so the monetary assertions do not
depend on whether a chart of accounts / default sale tax exists in the test
database.
"""

from odoo import Command

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase


class OdusiteSaleCase(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.website.company_id
        cls.currency = cls.website.currency_id

        # -- Categories: parent + child ---------------------------------
        cls.categ_parent = cls.env['product.public.category'].create({
            'name': 'Odusite Furniture',
        })
        cls.categ_child = cls.env['product.public.category'].create({
            'name': 'Odusite Chairs',
            'parent_id': cls.categ_parent.id,
        })

        # -- Attribute Color (Red/Blue), create_variant=always ----------
        cls.color_attribute = cls.env['product.attribute'].create({
            'name': 'Odusite Color',
            'display_type': 'color',
            'create_variant': 'always',
            'value_ids': [
                Command.create({'name': 'Red', 'html_color': '#FF0000'}),
                Command.create({'name': 'Blue', 'html_color': '#0000FF'}),
            ],
        })
        cls.value_red = cls.color_attribute.value_ids[0]
        cls.value_blue = cls.color_attribute.value_ids[1]

        # -- Products: 3 published + 1 unpublished ----------------------
        cls.product_chair = cls._create_product(
            'Odusite Chair', 100.0, categories=cls.categ_child)
        cls.product_table = cls._create_product(
            'Odusite Table', 250.0, categories=cls.categ_parent)
        cls.product_shirt = cls._create_product('Odusite Shirt', 50.0, extra={
            'attribute_line_ids': [Command.create({
                'attribute_id': cls.color_attribute.id,
                'value_ids': [Command.set([cls.value_red.id, cls.value_blue.id])],
            })],
        })
        cls.product_hidden = cls._create_product(
            'Odusite Hidden', 75.0, published=False)

        shirt_ptavs = (
            cls.product_shirt.attribute_line_ids.product_template_value_ids
        )
        cls.ptav_red = shirt_ptavs.filtered(
            lambda ptav: ptav.product_attribute_value_id == cls.value_red)
        cls.ptav_blue = shirt_ptavs.filtered(
            lambda ptav: ptav.product_attribute_value_id == cls.value_blue)
        cls.variant_red = cls.product_shirt.product_variant_ids.filtered(
            lambda product: cls.ptav_red in product.product_template_attribute_value_ids)
        cls.variant_blue = cls.product_shirt.product_variant_ids.filtered(
            lambda product: cls.ptav_blue in product.product_template_attribute_value_ids)

    # -- Fixture helpers -------------------------------------------------

    @classmethod
    def _create_product(cls, name, price, categories=None, published=True, extra=None):
        values = {
            'name': name,
            'list_price': price,
            'sale_ok': True,
            'is_published': published,
            'taxes_id': [Command.clear()],
        }
        if categories:
            values['public_categ_ids'] = [Command.set(categories.ids)]
        if extra:
            values.update(extra)
        return cls.env['product.template'].create(values)

    @classmethod
    def _create_delivery_method(cls, name='Odusite Standard Delivery', price=10.0):
        """Published fixed-price delivery.carrier (with its service product)."""
        delivery_product = cls.env['product.product'].create({
            'name': f'{name} (delivery product)',
            'type': 'service',
            'sale_ok': False,
            'list_price': price,
            'taxes_id': [Command.clear()],
        })
        return cls.env['delivery.carrier'].create({
            'name': name,
            'delivery_type': 'fixed',
            'fixed_price': price,
            'product_id': delivery_product.id,
            'is_published': True,
        })

    # -- Request helpers -------------------------------------------------

    def _slug(self, record):
        return self.env['ir.http']._slug(record)

    def _ids(self, body):
        return [item['id'] for item in body['data']]

    def _open_cart(self, bearer=None):
        """POST /shop/cart; returns (cart_id, token, X-Odusite-Cart value)."""
        response, body = self.api('POST', '/shop/cart', bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertTrue(data['id'])
        self.assertTrue(data['token'])
        return data['id'], data['token'], f"{data['id']}:{data['token']}"
