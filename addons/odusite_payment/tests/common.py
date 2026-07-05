"""Payment/accounting fixture helpers.

Shared by the odusite_payment and odusite_account tests (odusite_account
depends on odusite_payment, so importing this module from there is safe).
"""

from odoo import Command, fields


class PaymentFixturesMixin:

    @classmethod
    def _ensure_chart_of_accounts(cls, company):
        """Posting invoices needs a chart of accounts; test databases are
        created without demo data, so load the generic one on demand."""
        if not company.chart_template:
            cls.env['account.chart.template'].try_loading(
                'generic_coa', company, install_demo=False)

    @classmethod
    def _enable_test_provider(cls, company):
        """Put a provider shipped by the `payment` module (code 'none', no
        provider API calls) in test state with an active payment method, so
        that _get_compatible_providers / _get_compatible_payment_methods
        match it for public (published) payments."""
        provider = cls.env.ref('payment.payment_provider_demo',
                               raise_if_not_found=False)
        if not provider:
            provider = cls.env['payment.provider'].search(
                [('code', '=', 'none')], limit=1)
        method = cls.env.ref('payment.payment_method_card',
                             raise_if_not_found=False)
        if not method:
            method = cls.env['payment.method'].search(
                [('is_primary', '=', True)], limit=1)
        # Enable the provider BEFORE activating the method: activating a
        # payment.method requires an enabled provider among its providers.
        provider.write({
            'state': 'test',
            'is_published': True,
            'company_id': company.id,
            'available_country_ids': [Command.clear()],
            'maximum_amount': 0,
        })
        # Link first, then activate: payment.method.write checks the provider
        # link on the OLD values before applying the vals.
        method.write({
            'provider_ids': [Command.link(provider.id)],
            'supported_country_ids': [Command.clear()],
            'supported_currency_ids': [Command.clear()],
        })
        method.write({'active': True})
        return provider, method

    @classmethod
    def _make_invoice(cls, partner, amount, post=True, invoice_date=None,
                      date_due=None):
        """Customer invoice with a single tax-free line of ``amount``."""
        values = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': invoice_date or fields.Date.today(),
            'invoice_line_ids': [Command.create({
                'name': 'Odusite test line',
                'quantity': 1.0,
                'price_unit': amount,
                'tax_ids': [Command.clear()],
            })],
        }
        if date_due:
            values['invoice_date_due'] = date_due
        invoice = cls.env['account.move'].create(values)
        if post:
            invoice.action_post()
        return invoice

    @classmethod
    def _register_full_payment(cls, invoice):
        """Fully pay a posted invoice through the payment register wizard."""
        cls.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({})._create_payments()
