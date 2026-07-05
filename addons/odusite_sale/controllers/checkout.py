"""Checkout endpoints: state, addresses, delivery method, confirmation.

The controller subclasses website_sale's WebsiteSale to reuse the stock
address helpers (``_prepare_address_update``, ``_create_or_update_address``,
``_check_billing_address`` / ``_check_delivery_address``); the guard logic
mirrors ``/shop/checkout`` -> ``/shop/payment``
(``_check_cart`` / ``_check_addresses`` / ``_check_cart_is_ready_to_be_paid``).
"""

from werkzeug.exceptions import Forbidden

from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import consteq

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    get_cart_binding,
    odusite_route,
)
from odoo.addons.odusite_base.lib import serializers
from odoo.addons.website_sale.controllers.delivery import Delivery
from odoo.addons.website_sale.controllers.main import WebsiteSale

from .common import amount, bind_pricing, get_cart, serialize_amounts, serialize_cart


class OdusiteCheckoutController(WebsiteSale):

    # === CHECKOUT STATE === #

    @odusite_route(f'{API_PREFIX}/shop/checkout', methods=['GET'])
    def checkout_state(self, **kwargs):
        order_sudo = get_cart()
        return self._serialize_checkout_state(order_sudo)

    def _serialize_checkout_state(self, order_sudo):
        website = request.website
        errors = []

        # Cart guards (mirrors WebsiteSale._check_cart, without redirections).
        cart_ok = bool(order_sudo.order_line)
        if not cart_ok:
            errors.append('cart_empty')
        if request.env.user._is_public() and website.account_on_checkout == 'mandatory':
            errors.append('login_required')

        # Address guards (mirrors WebsiteSale._check_addresses).
        is_anonymous = order_sudo._is_anonymous_cart()
        needs_delivery = order_sudo._has_deliverable_products()
        if is_anonymous:
            addresses = {'billing': None, 'delivery': None}
            errors.append('address_required')
        else:
            billing_complete = self._check_billing_address(order_sudo.partner_invoice_id)
            delivery_complete = self._check_delivery_address(order_sudo.partner_shipping_id)
            addresses = {
                'billing': self._serialize_checkout_address(
                    order_sudo.partner_invoice_id, billing_complete),
                'delivery': self._serialize_checkout_address(
                    order_sudo.partner_shipping_id, delivery_complete),
            }
            if not billing_complete:
                errors.append('billing_address_incomplete')
            if needs_delivery and not delivery_complete:
                errors.append('delivery_address_incomplete')

        delivery_methods = []
        if needs_delivery and not is_anonymous:
            delivery_methods = [
                self._serialize_delivery_method(delivery_method, order_sudo)
                for delivery_method in order_sudo._get_delivery_methods()
            ]
            if not order_sudo.carrier_id:
                errors.append('delivery_method_required')

        payment_ready = False
        if not errors:
            try:
                order_sudo._check_cart_is_ready_to_be_paid()
                payment_ready = True
            except ValidationError:
                errors.append('cart_not_ready')

        return {
            'cart_ok': cart_ok,
            'addresses': addresses,
            'needs_delivery': needs_delivery,
            'delivery_methods': delivery_methods,
            'selected_delivery_id': order_sudo.carrier_id.id or None,
            'payment_ready': payment_ready,
            'errors': errors,
            'amounts': serialize_amounts(order_sudo),
        }

    def _serialize_checkout_address(self, partner, complete):
        partner_sudo = partner.sudo()
        return {
            'id': partner_sudo.id,
            'name': partner_sudo.name or '',
            'email': partner_sudo.email or '',
            'phone': partner_sudo.phone or '',
            'street': partner_sudo.street or '',
            'street2': partner_sudo.street2 or '',
            'city': partner_sudo.city or '',
            'zip': partner_sudo.zip or '',
            'state': {
                'id': partner_sudo.state_id.id,
                'code': partner_sudo.state_id.code,
                'name': partner_sudo.state_id.name,
            } if partner_sudo.state_id else None,
            'country': {
                'id': partner_sudo.country_id.id,
                'code': partner_sudo.country_id.code,
                'name': partner_sudo.country_id.name,
            } if partner_sudo.country_id else None,
            'company_name': partner_sudo.company_name or '',
            'vat': partner_sudo.vat or '',
            'complete': bool(complete),
        }

    def _serialize_delivery_method(self, delivery_method, order_sudo):
        currency = order_sudo.currency_id
        rate = Delivery._get_rate(delivery_method, order_sudo)
        values = {
            'id': delivery_method.id,
            'name': delivery_method.name,
            'description': delivery_method.website_description or '',
            'price': amount(rate['price'], currency) if rate.get('success') else None,
            'currency': currency.name,
        }
        if delivery_method.free_over:
            values['free_over'] = amount(delivery_method.amount, currency)
        return values

    # === ADDRESS SUBMISSION === #

    @odusite_route(f'{API_PREFIX}/shop/checkout/address', methods=['POST'])
    def checkout_address(self, address_type='billing', use_delivery_as_billing=None,
                         partner_id=None, **form_data):
        """Create or update a checkout address; mirrors the flow of
        ``/shop/address/submit`` (WebsiteSale.shop_address_submit).

        Guests get a brand new partner not linked to the public partner
        (``_complete_address_values`` skips ``parent_id`` for anonymous carts
        and forces ``type='contact'``), set as the order's partner ids.
        """
        order_sudo = get_cart()

        if address_type not in ('billing', 'delivery'):
            raise ApiError(400, 'bad_request', "address_type must be 'billing' or 'delivery'.")
        use_delivery_as_billing = self._parse_bool(use_delivery_as_billing)

        try:
            partner_sudo, address_type = self._prepare_address_update(
                order_sudo,
                partner_id=int(partner_id) if partner_id else None,
                address_type=address_type,
            )
        except Forbidden:
            raise ApiError(403, 'forbidden', 'You are not allowed to edit this address.')

        is_new_address = not partner_sudo
        partner_sudo, feedback = self._create_or_update_address(
            partner_sudo,
            address_type=address_type,
            use_delivery_as_billing=use_delivery_as_billing,
            callback='',
            order_sudo=order_sudo,
            **form_data,
        )
        if feedback.get('invalid_fields'):
            raise ApiError(
                422, 'validation_error',
                ' '.join(feedback.get('messages') or []) or 'Invalid address values.',
                {'fields': list(feedback['invalid_fields'])},
            )

        # Link the partner to the order (copied from shop_address_submit).
        is_anonymous_cart = order_sudo._is_anonymous_cart()
        is_main_address = is_anonymous_cart or order_sudo.partner_id.id == partner_sudo.id
        partner_fnames = set()
        if is_main_address:  # Main customer address updated.
            partner_fnames.add('partner_id')  # Force the re-computation of partner-based fields.
        if address_type == 'billing':
            partner_fnames.add('partner_invoice_id')
            if is_new_address and order_sudo.only_services:
                # The delivery address is required to make the order.
                partner_fnames.add('partner_shipping_id')
        elif address_type == 'delivery':
            partner_fnames.add('partner_shipping_id')
            if use_delivery_as_billing:
                partner_fnames.add('partner_invoice_id')

        order_sudo._update_address(partner_sudo.id, partner_fnames)

        if order_sudo._is_anonymous_cart():
            # Unsubscribe the public partner if the cart was previously anonymous.
            order_sudo.message_unsubscribe(order_sudo.website_id.partner_id.ids)

        return self._serialize_checkout_state(order_sudo)

    @staticmethod
    def _parse_bool(value):
        return value in (True, 1, '1', 'true', 'True', 'on')

    # === DELIVERY METHOD === #

    @odusite_route(f'{API_PREFIX}/shop/checkout/delivery', methods=['PUT'])
    def checkout_delivery(self, delivery_method_id=None, **kwargs):
        """Set the delivery method; mirrors Delivery.shop_set_delivery_method."""
        order_sudo = get_cart()

        try:
            dm_id = int(delivery_method_id)
        except (TypeError, ValueError):
            raise ApiError(400, 'bad_request', 'delivery_method_id is required.')

        if dm_id not in order_sudo._get_delivery_methods().ids:
            raise ApiError(400, 'bad_request',
                           'This delivery method is not available for your order.')

        if dm_id != order_sudo.carrier_id.id:
            for tx_sudo in order_sudo.transaction_ids:
                if tx_sudo.state not in ('draft', 'cancel', 'error'):
                    raise ApiError(
                        409, 'conflict',
                        'A transaction is already registered on this order; the delivery'
                        ' method can no longer be changed.',
                    )
            delivery_method_sudo = request.env['delivery.carrier'].sudo().browse(
                dm_id).exists()
            order_sudo._set_delivery_method(delivery_method_sudo)
            if order_sudo.carrier_id.id != dm_id:
                # _set_delivery_method() only sets the carrier when a rate
                # could be computed.
                raise ApiError(400, 'bad_request',
                               'No delivery rate could be computed for this method.')

        return {
            'selected_delivery_id': order_sudo.carrier_id.id or None,
            'amounts': serialize_amounts(order_sudo),
        }

    # === CONFIRMATION === #

    @odusite_route(f'{API_PREFIX}/shop/orders/<int:order_id>/confirmation', methods=['GET'])
    def order_confirmation(self, order_id, access_token=None, **kwargs):
        """Post-payment confirmation data for the thank-you page (token-gated)."""
        token = access_token
        if not token:
            binding = get_cart_binding()
            if binding and binding[0] == order_id:
                token = binding[1]

        order_sudo = request.env['sale.order'].sudo().browse(order_id).exists()
        if (
            not order_sudo
            or not token
            or not order_sudo.access_token
            or not consteq(order_sudo.access_token, token)
            or (order_sudo.website_id and order_sudo.website_id.id != request.website.id)
        ):
            raise ApiError(404, 'not_found', 'Order not found.')

        bind_pricing()
        tx_sudo = order_sudo.get_portal_last_transaction()
        return {
            **serialize_cart(order_sudo),
            'name': order_sudo.name,
            'state': order_sudo.state,
            'date_order': serializers.datetime_utc(order_sudo.date_order),
            'partner': {
                'name': order_sudo.partner_id.name or '',
                'email': order_sudo.partner_id.email or '',
            },
            'transaction_state': tx_sudo.state or None,
        }
