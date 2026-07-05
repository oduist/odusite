"""Portal invoices endpoints (see specs/modules/odusite_account.md).

Domains and helpers mirror the stock account portal controller
(account/controllers/portal.py) and the account.move legal-documents helpers.
"""

from odoo import fields
from odoo.http import content_disposition, request

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    list_meta,
    odusite_route,
    parse_pagination,
)
from odoo.addons.odusite_base.lib import serializers
from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.odusite_api import (
    SETTLED_PAYMENT_STATES,
    invoices_base_domain,
    invoices_overdue_domain,
)

# Public order keys -> ORM order (account/controllers/portal.py
# `_get_account_searchbar_sortings`).
INVOICE_ORDER_WHITELIST = {
    'date': 'invoice_date desc',
    'duedate': 'invoice_date_due desc',
    'name': 'name desc',
}
INVOICE_STATE_FILTERS = {
    'open': [
        ('payment_state', 'not in', SETTLED_PAYMENT_STATES),
    ],
    'paid': [
        ('payment_state', 'in', ('paid', 'in_payment', 'reversed')),
    ],
    'overdue': None,  # computed: open + due date in the past
}


class OdusiteAccountPortal(CustomerPortal):

    # === Helpers === #

    def _invoice_is_overdue(self, invoice):
        return bool(
            invoice.payment_state not in SETTLED_PAYMENT_STATES
            and invoice.invoice_date_due
            and invoice.invoice_date_due < fields.Date.today()
        )

    def _serialize_invoice(self, invoice):
        return {
            'id': invoice.id,
            'name': invoice.name,
            'invoice_date': serializers.date_iso(invoice.invoice_date),
            'invoice_date_due': serializers.date_iso(invoice.invoice_date_due),
            'amount_total': invoice.amount_total,
            'amount_residual': invoice.amount_residual,
            'currency': invoice.currency_id.name,
            'payment_state': invoice.payment_state,
            'is_overdue': self._invoice_is_overdue(invoice),
        }

    def _serialize_invoice_line(self, line):
        return {
            'name': line.name or line.product_id.display_name or '',
            'quantity': line.quantity,
            'price_unit': line.price_unit,
            'price_subtotal': line.price_subtotal,
            'taxes': line.tax_ids.mapped('name'),
        }

    def _invoice_requires_payment(self, invoice_sudo):
        """Residual left to pay and at least one compatible provider."""
        if invoice_sudo.state != 'posted' or invoice_sudo.move_type != 'out_invoice':
            return False
        if invoice_sudo.payment_state in SETTLED_PAYMENT_STATES:
            return False
        if invoice_sudo.currency_id.is_zero(invoice_sudo.amount_residual):
            return False
        user = request.env.user
        partner = invoice_sudo.partner_id if user._is_public() else user.partner_id
        providers_sudo = request.env['payment.provider'].sudo()._get_compatible_providers(
            invoice_sudo.company_id.id,
            partner.id,
            invoice_sudo.amount_residual,
            currency_id=invoice_sudo.currency_id.id,
        )
        return bool(providers_sudo)

    def _get_portal_invoice(self, invoice_id, access_token):
        """Fetch a portal-visible invoice (JWT record rules or access token).
        Only posted customer invoices/refunds are exposed."""
        invoice_sudo = self._document_check_access('account.move', invoice_id, access_token)
        if invoice_sudo.move_type not in ('out_invoice', 'out_refund') \
                or invoice_sudo.state != 'posted':
            # Not a portal customer invoice: behave as if it did not exist.
            raise ApiError(404, 'not_found', 'The requested record does not exist.')
        return invoice_sudo

    # === Endpoints === #

    @odusite_route(f'{API_PREFIX}/my/invoices', methods=['GET'], auth_user=True)
    def odusite_my_invoices(self, **kwargs):
        page, limit, offset, order = parse_pagination(
            kwargs, order_whitelist=INVOICE_ORDER_WHITELIST, default_order='date',
        )
        domain = invoices_base_domain()
        state = kwargs.get('state')
        if state:
            if state not in INVOICE_STATE_FILTERS:
                raise ApiError(400, 'bad_request', f'Unsupported state filter: {state}',
                               {'allowed': sorted(INVOICE_STATE_FILTERS)})
            if state == 'overdue':
                domain += INVOICE_STATE_FILTERS['open'] + invoices_overdue_domain()
            else:
                domain += INVOICE_STATE_FILTERS[state]

        move_model = request.env['account.move']  # JWT user: portal record rules apply.
        total = move_model.search_count(domain)
        invoices = move_model.search(domain, order=order, limit=limit, offset=offset)
        return (
            [self._serialize_invoice(invoice) for invoice in invoices],
            list_meta(total, page, limit),
        )

    @odusite_route(f'{API_PREFIX}/my/invoices/<int:invoice_id>', methods=['GET'])
    def odusite_my_invoice_detail(self, invoice_id, access_token=None, **kwargs):
        invoice_sudo = self._get_portal_invoice(invoice_id, access_token)
        lines = invoice_sudo.invoice_line_ids.filtered(
            lambda line: line.display_type == 'product'
        )
        data = self._serialize_invoice(invoice_sudo)
        data.update({
            'lines': [self._serialize_invoice_line(line) for line in lines],
            'amount_untaxed': invoice_sudo.amount_untaxed,
            'amount_tax': invoice_sudo.amount_tax,
            'requires_payment': self._invoice_requires_payment(invoice_sudo),
            'pdf_url': f'{API_PREFIX}/my/invoices/{invoice_sudo.id}/pdf',
        })
        return data

    @odusite_route(f'{API_PREFIX}/my/invoices/<int:invoice_id>/pdf', methods=['GET'])
    def odusite_my_invoice_pdf(self, invoice_id, access_token=None, **kwargs):
        """Stream the legal invoice PDF.

        Primary source: account.move._get_invoice_legal_documents('pdf',
        allow_fallback=True) — the generated legal PDF, or a Pro Forma when it
        does not exist yet (as the stock portal download does). Last-resort
        fallback: render the account.account_invoices report.
        """
        invoice_sudo = self._get_portal_invoice(invoice_id, access_token)
        doc_data = invoice_sudo._get_invoice_legal_documents('pdf', allow_fallback=True)
        if doc_data:
            filename = doc_data['filename']
            content = doc_data['content']
        else:
            content, dummy = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'account.account_invoices', [invoice_sudo.id],
            )
            filename = invoice_sudo._get_invoice_report_filename()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', str(len(content))),
            ('Content-Disposition', content_disposition(filename)),
        ])
