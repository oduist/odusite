from odoo.tests.common import tagged

from .common import OdusiteSaleCase


@tagged('post_install', '-at_install')
class TestCartCheckout(OdusiteSaleCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carrier = cls._create_delivery_method(price=10.0)
        cls.portal_user = cls.create_portal_user(login='odusite.cart@example.com',
                                                 name='Odusite Cart Tester')

    def _billing_address_payload(self, **overrides):
        us = self.env.ref('base.us')
        state = self.env['res.country.state'].search([
            ('country_id', '=', us.id), ('code', '=', 'CA'),
        ], limit=1)
        payload = {
            'address_type': 'billing',
            'name': 'Guest Buyer',
            'email': 'guest.buyer@example.com',
            'phone': '+1 555 0100',
            'street': '1 Test Street',
            'city': 'San Francisco',
            'zip': '94105',
            'country_id': us.id,
            'state_id': state.id,
        }
        payload.update(overrides)
        return payload

    # -- Cart lifecycle ----------------------------------------------------

    def test_cart_create_and_get_empty(self):
        cart_id, token, header = self._open_cart()
        response, body = self.api('GET', '/shop/cart', cart=header)
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertEqual(data['id'], cart_id)
        self.assertEqual(data['lines'], [])
        self.assertEqual(data['cart_quantity'], 0)
        self.assertEqual(data['amounts']['total'], 0.0)
        self.assertEqual(data['amounts']['currency'], self.currency.name)
        self.assertIn(data['tax_mode'], ('included', 'excluded'))

        # Guest cart belongs to the website public partner.
        order = self.env['sale.order'].browse(cart_id)
        self.assertEqual(order.partner_id, self.website.user_id.sudo().partner_id)
        self.assertEqual(order.access_token, token)

    def test_cart_missing_or_malformed_header(self):
        response, body = self.api('GET', '/shop/cart')
        self.assert_api_error(response, body, 400, 'bad_request')

        response, body = self.api('GET', '/shop/cart', cart='not-a-binding')
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_cart_wrong_token(self):
        cart_id, _token, _header = self._open_cart()
        response, body = self.api('GET', '/shop/cart', cart=f'{cart_id}:wrong-token')
        self.assert_api_error(response, body, 404, 'not_found')

    def test_cart_lines_crud(self):
        _cart_id, _token, header = self._open_cart()

        # Add product, qty 2.
        response, body = self.api('POST', '/shop/cart/lines', {
            'product_id': self.product_chair.product_variant_id.id,
            'quantity': 2,
        }, cart=header)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        line_id = data['line_id']
        self.assertTrue(line_id)
        self.assertEqual(data['cart_quantity'], 2)
        self.assertEqual(len(data['lines']), 1)
        line = data['lines'][0]
        self.assertEqual(line['id'], line_id)
        self.assertEqual(line['quantity'], 2)
        self.assertEqual(line['price_unit'], 100.0)
        self.assertEqual(line['product']['id'], self.product_chair.product_variant_id.id)
        self.assertEqual(data['amounts']['untaxed'], 200.0)

        # Update quantity to 1.
        response, body = self.api('PUT', f'/shop/cart/lines/{line_id}',
                                  {'quantity': 1}, cart=header)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['cart_quantity'], 1)
        self.assertEqual(data['lines'][0]['quantity'], 1)
        self.assertEqual(data['amounts']['untaxed'], 100.0)

        # Delete the line.
        response, body = self.api('DELETE', f'/shop/cart/lines/{line_id}', cart=header)
        self.assertEqual(response.status_code, 200, body)
        self.assertEqual(body['data']['lines'], [])
        self.assertEqual(body['data']['amounts']['total'], 0.0)

        # The removed line is gone: further updates 404.
        response, body = self.api('PUT', f'/shop/cart/lines/{line_id}',
                                  {'quantity': 3}, cart=header)
        self.assert_api_error(response, body, 404, 'not_found')

    def test_cart_add_unpublished_product(self):
        _cart_id, _token, header = self._open_cart()
        response, body = self.api('POST', '/shop/cart/lines', {
            'product_id': self.product_hidden.product_variant_id.id,
            'quantity': 1,
        }, cart=header)
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_cart_add_invalid_quantity(self):
        _cart_id, _token, header = self._open_cart()
        response, body = self.api('POST', '/shop/cart/lines', {
            'product_id': self.product_chair.product_variant_id.id,
            'quantity': 0,
        }, cart=header)
        self.assert_api_error(response, body, 400, 'bad_request')

    # -- Checkout state machine ---------------------------------------------

    def test_checkout_empty_cart_state(self):
        _cart_id, _token, header = self._open_cart()
        response, body = self.api('GET', '/shop/checkout', cart=header)
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertFalse(data['cart_ok'])
        self.assertIn('cart_empty', data['errors'])
        self.assertIn('address_required', data['errors'])
        self.assertEqual(data['addresses'], {'billing': None, 'delivery': None})
        self.assertFalse(data['payment_ready'])

    def test_checkout_flow(self):
        _cart_id, _token, header = self._open_cart()
        response, body = self.api('POST', '/shop/cart/lines', {
            'product_id': self.product_chair.product_variant_id.id,
            'quantity': 1,
        }, cart=header)
        self.assertEqual(response.status_code, 200, body)

        # 1. Anonymous cart with items: only the address is missing; the
        #    delivery_method_required error only shows up once addresses exist.
        response, body = self.api('GET', '/shop/checkout', cart=header)
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertTrue(data['cart_ok'])
        self.assertTrue(data['needs_delivery'])
        self.assertEqual(data['errors'], ['address_required'])
        self.assertEqual(data['delivery_methods'], [])
        self.assertFalse(data['payment_ready'])

        # 2. Guest billing address (full US address).
        response, body = self.api('POST', '/shop/checkout/address',
                                  self._billing_address_payload(), cart=header)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        billing = data['addresses']['billing']
        self.assertTrue(billing['complete'])
        self.assertEqual(billing['email'], 'guest.buyer@example.com')
        self.assertEqual(billing['country']['code'], 'US')
        # Main-address submit propagates to the delivery address as well.
        self.assertTrue(data['addresses']['delivery']['complete'])
        self.assertEqual(data['errors'], ['delivery_method_required'])
        self.assertFalse(data['payment_ready'])

        methods = {method['id']: method for method in data['delivery_methods']}
        self.assertIn(self.carrier.id, methods)
        self.assertEqual(methods[self.carrier.id]['price'], 10.0)

        # 3. Select the delivery method: amounts include the delivery price.
        response, body = self.api('PUT', '/shop/checkout/delivery',
                                  {'delivery_method_id': self.carrier.id}, cart=header)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['selected_delivery_id'], self.carrier.id)
        self.assertEqual(data['amounts']['delivery'], 10.0)
        self.assertEqual(data['amounts']['total'], 110.0)

        # 4. All gates passed: the cart is payment-ready.
        response, body = self.api('GET', '/shop/checkout', cart=header)
        self.assertEqual(response.status_code, 200)
        data = body['data']
        self.assertEqual(data['errors'], [])
        self.assertTrue(data['payment_ready'])
        self.assertEqual(data['selected_delivery_id'], self.carrier.id)

    def test_checkout_address_validation_error(self):
        _cart_id, _token, header = self._open_cart()
        response, body = self.api('POST', '/shop/cart/lines', {
            'product_id': self.product_chair.product_variant_id.id,
            'quantity': 1,
        }, cart=header)
        self.assertEqual(response.status_code, 200, body)

        response, body = self.api(
            'POST', '/shop/checkout/address',
            self._billing_address_payload(email='not-an-email'), cart=header)
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertIn('email', body['error']['details']['fields'])

    def test_checkout_invalid_delivery_method(self):
        _cart_id, _token, header = self._open_cart()
        response, body = self.api('POST', '/shop/cart/lines', {
            'product_id': self.product_chair.product_variant_id.id,
            'quantity': 1,
        }, cart=header)
        self.assertEqual(response.status_code, 200, body)

        response, body = self.api('PUT', '/shop/checkout/delivery',
                                  {'delivery_method_id': 99999999}, cart=header)
        self.assert_api_error(response, body, 400, 'bad_request')

    # -- Cart claim ----------------------------------------------------------

    def test_cart_claim(self):
        bearer = self.make_access_token(self.portal_user)

        # The logged-in user already has a draft cart with a table.
        user_cart_id, _user_token, user_header = self._open_cart(bearer=bearer)
        response, body = self.api('POST', '/shop/cart/lines', {
            'product_id': self.product_table.product_variant_id.id,
            'quantity': 1,
        }, cart=user_header)
        self.assertEqual(response.status_code, 200, body)

        # A guest cart with a chair is claimed after login.
        guest_cart_id, _guest_token, guest_header = self._open_cart()
        response, body = self.api('POST', '/shop/cart/lines', {
            'product_id': self.product_chair.product_variant_id.id,
            'quantity': 1,
        }, cart=guest_header)
        self.assertEqual(response.status_code, 200, body)

        response, body = self.api('POST', '/shop/cart/claim',
                                  cart=guest_header, bearer=bearer)
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['id'], guest_cart_id)
        # The other draft cart of the partner was merged in.
        products = {line['product']['id'] for line in data['lines']}
        self.assertEqual(products, {
            self.product_chair.product_variant_id.id,
            self.product_table.product_variant_id.id,
        })

        self.env.invalidate_all()
        claimed = self.env['sale.order'].browse(guest_cart_id)
        self.assertEqual(claimed.partner_id, self.portal_user.partner_id)
        merged = self.env['sale.order'].browse(user_cart_id)
        self.assertEqual(merged.state, 'cancel')

    def test_cart_claim_requires_jwt(self):
        _guest_cart_id, _token, guest_header = self._open_cart()
        response, body = self.api('POST', '/shop/cart/claim', cart=guest_header)
        self.assert_api_error(response, body, 401, 'unauthorized')
