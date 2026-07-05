"""Registry of documents that can be paid through the Odusite payment API.

Each payable document type is addressed by the frontend as ``"<prefix>:<id>"``
(e.g. ``"invoice:42"``, ``"order:7"``). A resolver descriptor bundles the
callables the payment controller needs to work with a document without knowing
its model (see specs/modules/odusite_payment.md).
"""

from odoo import _, models
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.fields import Command
from odoo.tools import consteq


class OdusitePayable(models.AbstractModel):
    """Extension registry for payable document types.

    Other odusite addons ``_inherit = 'odusite.payable'`` and extend
    :meth:`_odusite_payable_resolvers` (always call ``super()`` and merge
    results). A resolver descriptor is a dict with the following callables
    (all take the sudoed document record unless stated otherwise):

    - ``model``: the model name (str, not a callable);
    - ``browse``: ``(document_id, access_token) -> sudoed record`` — browse +
      access check (portal ``_document_check_access`` pattern: record rules of
      the current user, or ``consteq`` on the document ``access_token``);
    - ``amount_due``: remaining amount to pay (float);
    - ``partner``: the partner making the payment (record);
    - ``check_ready``: raise ``ValidationError`` when the document cannot be
      paid right now;
    - ``custom_create_values``: extra ``payment.transaction`` create values
      linking the transaction to the document;
    - ``confirm_zero_amount``: finalize a document whose amount due is zero
      (no transaction is created);
    - ``state_summary``: short JSON-serializable document summary.
    """
    _name = 'odusite.payable'
    _description = 'Odusite payable document registry'

    def _odusite_payable_resolvers(self):
        resolvers = {
            'invoice': {
                'model': 'account.move',
                'browse': self._invoice_browse,
                'amount_due': self._invoice_amount_due,
                'partner': self._invoice_partner,
                'check_ready': self._invoice_check_ready,
                'custom_create_values': self._invoice_custom_create_values,
                'confirm_zero_amount': self._invoice_confirm_zero_amount,
                'state_summary': self._invoice_state_summary,
            },
        }
        # Pragmatic choice: the 'order' resolver conceptually belongs to
        # odusite_sale, but it is shipped here (fully guarded by runtime
        # checks: `'sale.order' in self.env` and `hasattr` for website_sale
        # helpers) so that paying orders works even before odusite_sale
        # extends this registry. odusite_sale can override the 'order' key
        # after calling super() to take ownership of the resolver.
        if 'sale.order' in self.env:
            resolvers.setdefault('order', {
                'model': 'sale.order',
                'browse': self._order_browse,
                'amount_due': self._order_amount_due,
                'partner': self._order_partner,
                'check_ready': self._order_check_ready,
                'custom_create_values': self._order_custom_create_values,
                'confirm_zero_amount': self._order_confirm_zero_amount,
                'state_summary': self._order_state_summary,
            })
        return resolvers

    def _payable_browse(self, model_name, document_id, access_token):
        """Browse a payable document with an access check.

        Mirror of portal ``CustomerPortal._document_check_access``: the record
        must be readable by the current (JWT) user, or the provided
        ``access_token`` must match the document token.
        """
        document = self.env[model_name].browse(int(document_id))
        document_sudo = document.sudo().exists()
        if not document_sudo:
            raise MissingError(_("This document does not exist."))
        try:
            document.check_access('read')
        except AccessError:
            token = document_sudo.access_token
            if not access_token or not token or not consteq(token, access_token):
                raise
        return document_sudo

    # === Invoices (account.move) === #

    def _invoice_browse(self, document_id, access_token):
        return self._payable_browse('account.move', document_id, access_token)

    def _invoice_amount_due(self, invoice):
        return invoice.amount_residual

    def _invoice_partner(self, invoice):
        # Stock behavior of account_payment /invoice/transaction: the
        # logged-in user's partner, or the invoice partner for public access
        # (account_payment/controllers/payment.py `invoice_transaction`).
        user = self.env.user
        return invoice.partner_id if user._is_public() else user.partner_id

    def _invoice_check_ready(self, invoice):
        """Readiness check for invoices: posted customer invoice with a
        residual amount left to pay (subset of stock
        account_payment ``account.move._has_to_be_paid``)."""
        if invoice.state != 'posted':
            raise ValidationError(_("This invoice is not posted."))
        if invoice.move_type != 'out_invoice':
            raise ValidationError(_("This document is not a customer invoice."))
        if invoice.payment_state not in ('not_paid', 'in_payment', 'partial') \
                or invoice.currency_id.is_zero(invoice.amount_residual):
            raise ValidationError(_("This invoice has already been paid."))

    def _invoice_custom_create_values(self, invoice):
        return {'invoice_ids': [Command.set([invoice.id])]}

    def _invoice_confirm_zero_amount(self, invoice):
        # A posted invoice with nothing left to pay needs no further action.
        return

    def _invoice_state_summary(self, invoice):
        return {
            'type': 'invoice',
            'id': invoice.id,
            'state': invoice.state,
            'payment_state': invoice.payment_state,
        }

    # === Orders (sale.order) === #

    def _order_browse(self, document_id, access_token):
        return self._payable_browse('sale.order', document_id, access_token)

    def _order_amount_due(self, order):
        # website_sale does not support partial payments: the due amount is
        # the order total, or zero once transactions cover it
        # (website_sale/controllers/payment.py `shop_payment_transaction`).
        if order.amount_total \
                and order.currency_id.compare_amounts(order.amount_paid, order.amount_total) >= 0:
            return 0.0
        return order.amount_total

    def _order_partner(self, order):
        # Stock behavior of website_sale /shop/payment/transaction: always
        # the order's invoice partner (website_sale/controllers/payment.py).
        return order.partner_invoice_id

    def _order_check_ready(self, order):
        """Readiness check for orders: not cancelled, and — when website_sale
        is installed — the stock cart readiness check
        (``sale.order._check_cart_is_ready_to_be_paid``, guarded by
        ``hasattr`` since it only exists with website_sale)."""
        if order.state == 'cancel':
            raise ValidationError(_("The order has been cancelled."))
        if hasattr(order, '_check_cart_is_ready_to_be_paid'):
            order._check_cart_is_ready_to_be_paid()

    def _order_custom_create_values(self, order):
        return {'sale_order_ids': [Command.set([order.id])]}

    def _order_confirm_zero_amount(self, order):
        # Mirror of website_sale `/shop/payment/validate` for zero-amount
        # carts: run the readiness check, then confirm the order.
        if order.state in ('draft', 'sent'):
            if hasattr(order, '_check_cart_is_ready_to_be_paid'):
                order._check_cart_is_ready_to_be_paid()
            if hasattr(order, '_validate_order'):
                order._validate_order()
            else:
                order.action_confirm()

    def _order_state_summary(self, order):
        return {
            'type': 'order',
            'id': order.id,
            'state': order.state,
        }
