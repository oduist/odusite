"""Portal order endpoints: list (JWT), detail / accept / decline / PDF
(JWT record rules or ``?access_token=``, via the ``_document_check_access``
pattern). The accept/decline flows are copied from
sale/controllers/portal.py (portal_quote_accept / portal_quote_decline)."""

import binascii

from odoo import _, fields
from odoo.http import content_disposition, request

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    list_meta,
    odusite_route,
    parse_pagination,
)
from odoo.addons.odusite_base.lib import serializers
from odoo.addons.sale.controllers.portal import CustomerPortal

from .common import amount, serialize_amounts

ORDER_SORTINGS = {
    'date': 'date_order desc',
}


class OdusiteSaleOrdersController(CustomerPortal):

    @odusite_route(f'{API_PREFIX}/my/orders', methods=['GET'], auth_user=True)
    def my_orders(self, state='orders', **kwargs):
        partner = request.env.user.partner_id
        if state == 'quotes':
            domain = self._prepare_quotations_domain(partner)
        elif state == 'orders':
            domain = self._prepare_orders_domain(partner)
        else:
            raise ApiError(400, 'bad_request', "state must be 'quotes' or 'orders'.")

        page, limit, offset, order = parse_pagination(kwargs, ORDER_SORTINGS,
                                                      default_order='date')
        SaleOrder = request.env['sale.order']
        if not SaleOrder.has_access('read'):
            return [], list_meta(0, page, limit)

        total = SaleOrder.search_count(domain)
        orders = SaleOrder.search(domain, order=order, limit=limit, offset=offset)
        return (
            [self._serialize_order_item(order_sudo) for order_sudo in orders.sudo()],
            list_meta(total, page, limit),
        )

    @odusite_route(f'{API_PREFIX}/my/orders/<int:order_id>', methods=['GET'])
    def my_order_detail(self, order_id, access_token=None, **kwargs):
        order_sudo = self._document_check_access('sale.order', order_id,
                                                 access_token=access_token)
        return self._serialize_order_detail(order_sudo, access_token=access_token)

    @odusite_route(f'{API_PREFIX}/my/orders/<int:order_id>/accept', methods=['POST'])
    def my_order_accept(self, order_id, name=None, signature=None, access_token=None,
                        **kwargs):
        """Sign the quotation; copied from portal_quote_accept."""
        order_sudo = self._document_check_access('sale.order', order_id,
                                                 access_token=access_token)

        if not order_sudo._has_to_be_signed():
            raise ApiError(409, 'conflict',
                           'The order is not in a state requiring customer signature.')
        if not signature:
            raise ApiError(400, 'bad_request', 'Signature is missing.')

        try:
            order_sudo.write({
                'signed_by': name,
                'signed_on': fields.Datetime.now(),
                'signature': signature,
            })
            # flush now to make signature data available to the PDF render
            request.env.cr.flush()
        except (TypeError, ValueError, binascii.Error):
            raise ApiError(400, 'bad_request', 'Invalid signature data.')

        if not order_sudo._has_to_be_paid():
            order_sudo._validate_order()

        pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'sale.action_report_saleorder', [order_sudo.id])[0]
        order_sudo.message_post(
            attachments=[(f'{order_sudo.name}.pdf', pdf)],
            author_id=(
                order_sudo.partner_id.id
                if request.env.user._is_public()
                else request.env.user.partner_id.id
            ),
            body=_('Order signed by %s', name),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        return {
            'signed': True,
            'state': order_sudo.state,
            'requires_payment': order_sudo._has_to_be_paid(),
        }

    @odusite_route(f'{API_PREFIX}/my/orders/<int:order_id>/decline', methods=['POST'])
    def my_order_decline(self, order_id, reason=None, access_token=None, **kwargs):
        """Decline the quotation; copied from portal_quote_decline."""
        order_sudo = self._document_check_access('sale.order', order_id,
                                                 access_token=access_token)

        if not reason:
            raise ApiError(400, 'bad_request', 'A decline reason is required.')
        if not order_sudo._has_to_be_signed():
            raise ApiError(409, 'conflict', 'This order can no longer be declined.')

        order_sudo._action_cancel()
        # The currency is manually cached while in a sudoed environment to
        # prevent an AccessError during the flush of the monetary fields
        # depending on the order state (see the stock portal controller).
        order_sudo.order_line.currency_id

        order_sudo.message_post(
            author_id=(
                order_sudo.partner_id.id
                if request.env.user._is_public()
                else request.env.user.partner_id.id
            ),
            body=reason,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        return {'state': order_sudo.state}

    @odusite_route(f'{API_PREFIX}/my/orders/<int:order_id>/pdf', methods=['GET'])
    def my_order_pdf(self, order_id, access_token=None, **kwargs):
        order_sudo = self._document_check_access('sale.order', order_id,
                                                 access_token=access_token)
        pdf, _report_type = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'sale.action_report_saleorder', [order_sudo.id])
        filename = f"{(order_sudo.name or 'order').replace('/', '_')}.pdf"
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', str(len(pdf))),
            ('Content-Disposition', content_disposition(filename)),
        ])

    # === SERIALIZERS === #

    def _serialize_order_item(self, order_sudo):
        currency = order_sudo.currency_id
        return {
            'id': order_sudo.id,
            'name': order_sudo.name,
            'date_order': serializers.datetime_utc(order_sudo.date_order),
            'state': order_sudo.state,
            'amount_total': amount(order_sudo.amount_total, currency),
            'currency': currency.name,
            'invoice_status': order_sudo.invoice_status,
        }

    def _serialize_order_detail(self, order_sudo, access_token=None):
        pdf_url = f'{API_PREFIX}/my/orders/{order_sudo.id}/pdf'
        if access_token:
            pdf_url += f'?access_token={access_token}'
        invoices = order_sudo.invoice_ids.filtered(lambda move: move.state == 'posted')
        return {
            **self._serialize_order_item(order_sudo),
            'validity_date': serializers.date_iso(order_sudo.validity_date),
            'expected_date': serializers.datetime_utc(order_sudo.expected_date),
            'amounts': serialize_amounts(order_sudo),
            'lines': [self._serialize_order_line(line) for line in order_sudo.order_line],
            'partner': {
                'name': order_sudo.partner_id.name or '',
                'email': order_sudo.partner_id.email or '',
            },
            'delivery_address': self._serialize_order_address(
                order_sudo.partner_shipping_id),
            'can_accept': order_sudo._has_to_be_signed(),
            'can_decline': order_sudo._has_to_be_signed(),
            'requires_payment': order_sudo._has_to_be_paid(),
            'signed_by': order_sudo.signed_by or None,
            'signed_on': serializers.datetime_utc(order_sudo.signed_on),
            'invoices': [
                {
                    'id': move.id,
                    'name': move.name,
                    'state': move.state,
                    'amount_total': amount(move.amount_total, move.currency_id),
                    'currency': move.currency_id.name,
                }
                for move in invoices
            ],
            'pdf_url': pdf_url,
        }

    def _serialize_order_line(self, line):
        currency = line.currency_id
        values = {
            'id': line.id,
            'name': line.name or '',
            'display_type': line.display_type or None,
            'product': {
                'id': line.product_id.id,
                'template_id': line.product_id.product_tmpl_id.id,
                'slug': serializers.slug(line.product_id.product_tmpl_id),
                'name': line.product_id.display_name,
                'image': serializers.image_url(line.product_id, 'image_128'),
            } if line.product_id else None,
            'quantity': line.product_uom_qty,
            'uom': line.product_uom_id.name or '',
            'price_unit': amount(line.price_unit, currency),
            'discount': line.discount,
            'price_subtotal': amount(line.price_subtotal, currency),
            'price_total': amount(line.price_total, currency),
            'is_delivery': bool(line.is_delivery),
        }
        if 'is_reward_line' in line._fields:  # website_sale_loyalty installed
            values['is_reward'] = bool(line.is_reward_line)
        return values

    def _serialize_order_address(self, partner):
        partner_sudo = partner.sudo()
        if not partner_sudo:
            return None
        return {
            'name': partner_sudo.name or '',
            'street': partner_sudo.street or '',
            'street2': partner_sudo.street2 or '',
            'city': partner_sudo.city or '',
            'zip': partner_sudo.zip or '',
            'state': partner_sudo.state_id.name or '',
            'country': partner_sudo.country_id.name or '',
            'phone': partner_sudo.phone or '',
        }
