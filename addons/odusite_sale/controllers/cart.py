"""Stateless cart endpoints (ADR-007).

The cart is a draft ``sale.order`` addressed by the ``X-Odusite-Cart:
<id>:<access_token>`` header; every call re-verifies token, state and
website. Mutations go through the stock website_sale cart methods
(``_cart_add`` / ``_cart_update_line_quantity``)."""

from odoo import SUPERUSER_ID, http
from odoo.exceptions import AccessError
from odoo.http import request

from odoo.addons.odusite_base.controllers.api import API_PREFIX, ApiError, odusite_route

from .common import bind_pricing, get_cart, pricing_partner, serialize_cart


class OdusiteCartController(http.Controller):

    @odusite_route(f'{API_PREFIX}/shop/cart', methods=['POST'])
    def cart_create(self, **kwargs):
        """Create a cart, like website._create_cart() but without a session.

        Guests get the website public partner; JWT users their own partner
        (with their pricelist/fiscal position, resolved by bind_pricing).
        """
        bind_pricing()
        website = request.website
        partner_sudo = pricing_partner()

        so_data = website._prepare_sale_order_values(partner_sudo)
        order_sudo = request.env['sale.order'].with_user(SUPERUSER_ID).with_company(
            website.company_id
        ).create(so_data)
        # The order was created with SUPERUSER_ID, revert back to request user.
        order_sudo = order_sudo.with_user(request.env.user).sudo()

        return {'id': order_sudo.id, 'token': order_sudo._portal_ensure_token()}

    @odusite_route(f'{API_PREFIX}/shop/cart', methods=['GET'])
    def cart_get(self, **kwargs):
        order_sudo = get_cart()
        return serialize_cart(order_sudo)

    @odusite_route(f'{API_PREFIX}/shop/cart/lines', methods=['POST'])
    def cart_add_line(self, product_template_id=None, product_id=None, combination=None,
                      quantity=1, no_variant_attribute_value_ids=None, custom_values=None,
                      **kwargs):
        order_sudo = get_cart()

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise ApiError(400, 'bad_request', 'Invalid quantity.')
        if quantity <= 0:
            raise ApiError(400, 'bad_request', 'Quantity must be positive.')

        product, no_variant_ids = self._resolve_cart_product(
            product_template_id, product_id, combination, no_variant_attribute_value_ids)

        custom_values = custom_values or kwargs.get('product_custom_attribute_values') or []
        try:
            custom_attribute_values = [
                {
                    'custom_product_template_attribute_value_id': int(
                        custom['custom_product_template_attribute_value_id']),
                    'custom_value': custom.get('custom_value', ''),
                }
                for custom in custom_values
            ]
        except (TypeError, KeyError, ValueError, AttributeError):
            raise ApiError(400, 'bad_request', 'Invalid custom_values payload.')

        values = order_sudo._cart_add(
            product_id=product.id,
            quantity=quantity,
            no_variant_attribute_value_ids=no_variant_ids,
            product_custom_attribute_values=custom_attribute_values,
        )
        return self._cart_mutation_response(order_sudo, values)

    @odusite_route(f'{API_PREFIX}/shop/cart/lines/<int:line_id>', methods=['PUT', 'DELETE'])
    def cart_update_line(self, line_id, quantity=None, **kwargs):
        order_sudo = get_cart()
        if line_id not in order_sudo.order_line.ids:
            raise ApiError(404, 'not_found', 'Cart line not found.')

        if request.httprequest.method == 'DELETE':
            quantity = 0
        else:
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                raise ApiError(400, 'bad_request', 'Invalid quantity.')
            if quantity < 0:
                quantity = 0

        values = order_sudo._cart_update_line_quantity(line_id, quantity)
        return self._cart_mutation_response(order_sudo, values)

    @odusite_route(f'{API_PREFIX}/shop/cart/claim', methods=['POST'], auth_user=True)
    def cart_claim(self, **kwargs):
        """Re-assign a guest cart to the logged-in partner.

        Mirrors the login re-assignment in website._get_and_cache_current_cart()
        (``_update_address(partner_id, ['partner_id'])``); other draft carts of
        the partner on this website are merged into the claimed cart (their
        non-delivery lines are moved over, then the empty carts are cancelled,
        like the stock abandoned-cart 'merge' revival).
        """
        order_sudo = get_cart()
        partner = request.env.user.partner_id

        if order_sudo.partner_id.id != partner.id:
            if not order_sudo._is_anonymous_cart():
                raise ApiError(403, 'forbidden', 'This cart belongs to another customer.')
            order_sudo._update_address(partner.id, ['partner_id'])
            # The anonymous cart was subscribed to the website public partner.
            order_sudo.message_unsubscribe(order_sudo.website_id.partner_id.ids)

        other_carts_sudo = request.env['sale.order'].sudo().search([
            ('id', '!=', order_sudo.id),
            ('partner_id', '=', partner.id),
            ('website_id', '=', request.website.id),
            ('state', '=', 'draft'),
        ])
        for other_cart_sudo in other_carts_sudo:
            if other_cart_sudo.get_portal_last_transaction().state in (
                'pending', 'authorized', 'done'
            ):
                continue  # Never touch a cart with an ongoing payment.
            other_cart_sudo.order_line.filtered(
                lambda line: not line.is_delivery and not line.display_type
            ).write({'order_id': order_sudo.id})
            other_cart_sudo.action_cancel()

        order_sudo._verify_cart()
        order_sudo._verify_cart_after_update()
        return serialize_cart(order_sudo)

    # === HELPERS === #

    def _resolve_cart_product(self, product_template_id, product_id, combination,
                              no_variant_attribute_value_ids):
        """Resolve the `product.product` to add and its no_variant ptavs.

        Either an explicit ``product_id`` is given, or the variant is derived
        from ``product_template_id`` + ``combination`` (ptav ids), following
        the closest-possible-combination logic of ``_prepare_order_line_values``.
        """
        try:
            no_variant_ids = [int(value) for value in (no_variant_attribute_value_ids or [])]
            combination_ids = [int(value) for value in (combination or [])]
            product_id = int(product_id) if product_id else None
            product_template_id = int(product_template_id) if product_template_id else None
        except (TypeError, ValueError):
            raise ApiError(400, 'bad_request', 'Invalid cart line payload.')

        if not product_id:
            if not product_template_id:
                raise ApiError(400, 'bad_request',
                               'product_id or product_template_id is required.')
            template_sudo = request.env['product.template'].sudo().browse(
                product_template_id).exists()
            if not template_sudo:
                raise ApiError(404, 'not_found', 'Product not found.')
            ptavs_sudo = request.env['product.template.attribute.value'].sudo().browse(
                combination_ids
            ).exists().filtered(lambda ptav: ptav.product_tmpl_id.id == template_sudo.id)
            closest_combination = template_sudo._get_closest_possible_combination(ptavs_sudo)
            product_sudo = template_sudo._create_product_variant(closest_combination)
            if not product_sudo:
                raise ApiError(400, 'bad_request', 'The given combination is not possible.')
            product_id = product_sudo.id
            no_variant_ids = list(set(no_variant_ids) | set(
                closest_combination.filtered(
                    lambda ptav: ptav.attribute_id.create_variant == 'no_variant'
                ).ids
            ))

        product = request.env['product.product'].browse(product_id).exists()
        try:
            allowed = bool(product) and product._is_add_to_cart_allowed()
        except AccessError:
            allowed = False
        if not allowed:
            raise ApiError(400, 'bad_request',
                           'The given product cannot be added to the cart.')
        return product, no_variant_ids

    def _cart_mutation_response(self, order_sudo, values):
        data = serialize_cart(order_sudo)
        data['line_id'] = values.get('line_id') or None
        data['warning'] = values.get('warning') or None
        return data
