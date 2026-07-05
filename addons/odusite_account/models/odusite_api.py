from odoo import fields, models

# Payment states excluded from "still to pay", as in the stock
# overdue-invoices domain (account/controllers/portal.py
# `_get_overdue_invoices_domain`).
SETTLED_PAYMENT_STATES = ('in_payment', 'paid', 'reversed', 'blocked', 'invoicing_legacy')


def invoices_base_domain():
    """Portal customer invoices: posted out_invoice/out_refund only
    (see specs/modules/odusite_account.md; drafts are excluded)."""
    return [
        ('move_type', 'in', ('out_invoice', 'out_refund')),
        ('state', '=', 'posted'),
    ]


def invoices_overdue_domain():
    return [
        ('payment_state', 'not in', SETTLED_PAYMENT_STATES),
        ('invoice_date_due', '<', fields.Date.today()),
    ]


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _portal_counters(self, counters):
        values = super()._portal_counters(counters)
        if 'invoices' in counters:
            move_model = self.env['account.move']
            if move_model.has_access('read'):
                domain = invoices_base_domain()
                values['invoices'] = move_model.search_count(domain)
                values['invoices_overdue'] = move_model.search_count(
                    domain + invoices_overdue_domain()
                )
            else:
                values['invoices'] = 0
                values['invoices_overdue'] = 0
        return values

    def _chatter_models(self):
        return super()._chatter_models() | {'account.move'}
