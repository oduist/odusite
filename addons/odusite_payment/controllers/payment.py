"""Headless payment endpoints (see specs/04-payments.md).

The controller extends the stock ``payment.controllers.portal.PaymentPortal``
to reuse its ``_create_transaction`` helper: transactions are created exactly
like in the stock ``/payment/transaction`` route, only the payment context
(amount, partner, currency, document link) is resolved server-side from the
payable-document registry instead of being trusted from the client.
"""

import logging

from odoo.http import request
from odoo.tools import consteq

from odoo.addons.odusite_base.controllers.api import API_PREFIX, ApiError, odusite_route
from odoo.addons.odusite_base.lib import serializers
from odoo.addons.payment.controllers import portal as payment_portal

_logger = logging.getLogger(__name__)

# Generic keys of payment.transaction._get_processing_values() that the
# frontend does not need: it receives amount/reference/... at the top level of
# the endpoint response, and redirect forms are rebuilt from raw values.
GENERIC_PROCESSING_KEYS = {
    'provider_id', 'provider_code', 'reference', 'amount', 'currency_id',
    'partner_id', 'should_tokenize', 'state', 'state_message',
    'redirect_form_html',
}
LIVE_TX_STATES = ('pending', 'authorized', 'done')


class OdusitePaymentController(payment_portal.PaymentPortal):

    # === Helpers === #

    def _resolve_payable(self, params):
        """Resolve the ``document="<type>:<id>"`` parameter into
        ``(prefix, resolver, sudoed document)`` using the odusite.payable
        registry. Raises ApiError / AccessError / MissingError."""
        document_param = params.get('document')
        if not document_param or not isinstance(document_param, str):
            raise ApiError(400, 'bad_request', 'Missing document parameter ("<type>:<id>").')
        prefix, _, document_id = document_param.partition(':')
        if not document_id.isdigit():
            raise ApiError(400, 'bad_request', 'Malformed document parameter ("<type>:<id>").')
        resolvers = request.env['odusite.payable']._odusite_payable_resolvers()
        resolver = resolvers.get(prefix)
        if not resolver:
            raise ApiError(400, 'bad_request', f'Unknown payable document type: {prefix}',
                           {'allowed': sorted(resolvers)})
        document = resolver['browse'](int(document_id), params.get('access_token'))
        return prefix, resolver, document

    def _serialize_payment_method(self, method_sudo):
        return {
            'id': method_sudo.id,
            'code': method_sudo.code,
            'name': method_sudo.name,
            'image': serializers.image_url(method_sudo, 'image'),
            'support_tokenization': method_sudo.support_tokenization,
        }

    def _serialize_provider(self, provider_sudo, methods_sudo):
        inline = {}
        # Stripe specifics stay behind a code check: payment_stripe is an
        # optional dependency of this module.
        if provider_sudo.code == 'stripe' and hasattr(provider_sudo, '_stripe_get_publishable_key'):
            inline['publishable_key'] = provider_sudo._stripe_get_publishable_key()
        return {
            'id': provider_sudo.id,
            'code': provider_sudo.code,
            'name': provider_sudo.name,
            'state': provider_sudo.state,
            'support_tokenization': provider_sudo.allow_tokenization,
            'payment_methods': [
                self._serialize_payment_method(method)
                for method in methods_sudo
                if provider_sudo.id in method.provider_ids.ids
            ],
            'inline': inline,
        }

    def _serialize_token(self, token_sudo):
        method = token_sudo.payment_method_id
        return {
            'id': token_sudo.id,
            'provider_id': token_sudo.provider_id.id,
            'payment_details': token_sudo.payment_details or '',
            'payment_method': {
                'id': method.id,
                'code': method.code,
                'name': method.name,
            },
        }

    def _tx_processing_values(self, tx_sudo):
        """Provider-specific processing values for the frontend.

        - direct/token flows: stock ``_get_processing_values()`` filtered down
          to the provider-specific entries (for Stripe direct this is where
          the PaymentIntent is created and its ``client_secret`` returned, see
          payment_stripe/models/payment_transaction.py
          ``_get_specific_processing_values``); ``publishable_key`` is added
          for Stripe.
        - redirect flow: ``{redirect_url, form_data}`` built from
          ``_get_specific_rendering_values`` — the QWeb redirect form is not
          rendered; the site auto-submits the form itself. The stock pipeline
          is replicated here (without the form rendering) to avoid calling
          ``_get_specific_rendering_values`` twice, since it may hit the
          provider API.
        """
        if tx_sudo.operation == 'online_redirect':
            # Mirror of payment.transaction._get_processing_values() minus
            # the ir.qweb rendering of the redirect form.
            processing_values = {
                'provider_id': tx_sudo.provider_id.id,
                'provider_code': tx_sudo.provider_code,
                'reference': tx_sudo.reference,
                'amount': tx_sudo.amount,
                'currency_id': tx_sudo.currency_id.id,
                'partner_id': tx_sudo.partner_id.id,
                'should_tokenize': tx_sudo.tokenize,
            }
            processing_values.update(
                tx_sudo._get_specific_processing_values(processing_values)
            )
            rendering_values = dict(
                tx_sudo._get_specific_rendering_values(processing_values)
            )
            # By convention redirect providers expose the form action URL as
            # 'api_url' (e.g. payment_buckaroo/models/payment_transaction.py).
            redirect_url = rendering_values.pop('api_url', None)
            return {
                'redirect_url': redirect_url,
                'form_data': rendering_values,
            }

        processing_values = tx_sudo._get_processing_values()
        specific_values = {
            key: value for key, value in processing_values.items()
            if key not in GENERIC_PROCESSING_KEYS
        }
        if tx_sudo.provider_code == 'stripe':
            # The stock return_url points to Odoo's /payment/stripe/return,
            # unused in the headless flow (the site sets its own return_url).
            specific_values.pop('return_url', None)
            provider_sudo = tx_sudo.provider_id
            if hasattr(provider_sudo, '_stripe_get_publishable_key'):
                specific_values['publishable_key'] = provider_sudo._stripe_get_publishable_key()
        return specific_values

    def _transaction_document(self, tx_sudo):
        """Return ``(type, sudoed document)`` of the payable document linked
        to the transaction, or ``(None, None)``."""
        if 'invoice_ids' in tx_sudo._fields and tx_sudo.invoice_ids:
            return 'invoice', tx_sudo.invoice_ids[:1]
        if 'sale_order_ids' in tx_sudo._fields and tx_sudo.sale_order_ids:
            return 'order', tx_sudo.sale_order_ids[:1]
        return None, None

    def _transaction_accessible(self, tx_sudo, document, access_token):
        user = request.env.user
        if not user._is_public() and (
            user.partner_id.commercial_partner_id
            == tx_sudo.partner_id.commercial_partner_id
        ):
            return True
        if access_token and document is not None and document.access_token \
                and consteq(document.access_token, access_token):
            return True
        return False

    # === Endpoints === #

    @odusite_route(f'{API_PREFIX}/payment/methods', methods=['GET'])
    def odusite_payment_methods(self, **kwargs):
        """Compatible providers/payment methods (+ saved tokens for JWT users)
        for a payable document.

        Wraps payment.provider._get_compatible_providers and
        payment.method._get_compatible_payment_methods (see
        payment/controllers/portal.py `payment_pay`).
        """
        dummy, resolver, document = self._resolve_payable(kwargs)
        amount_due = resolver['amount_due'](document)
        currency = document.currency_id
        company = document.company_id or request.env.company
        partner = resolver['partner'](document)

        providers_sudo = request.env['payment.provider'].sudo()._get_compatible_providers(
            company.id, partner.id, amount_due, currency_id=currency.id,
        )
        methods_sudo = request.env['payment.method'].sudo()._get_compatible_payment_methods(
            providers_sudo.ids, partner.id, currency_id=currency.id,
        )

        tokens = []
        if not request.env.user._is_public():
            tokens_sudo = request.env['payment.token'].sudo()._get_available_tokens(
                providers_sudo.ids, partner.id,
            )
            tokens = [self._serialize_token(token) for token in tokens_sudo]

        return {
            'providers': [
                self._serialize_provider(provider, methods_sudo)
                for provider in providers_sudo
            ],
            'tokens': tokens,
            'amount': serializers.money(amount_due, currency),
            'document': resolver['state_summary'](document),
        }

    @odusite_route(f'{API_PREFIX}/payment/transactions', methods=['POST'])
    def odusite_payment_transaction_create(self, **kwargs):
        """Create a payment.transaction for a payable document.

        Validations (specs/04-payments.md): document readiness, requested
        amount == amount due, no live sibling transaction. Zero-amount
        documents are confirmed without a transaction (like
        website_sale /shop/payment/validate).
        """
        dummy, resolver, document = self._resolve_payable(kwargs)
        currency = document.currency_id
        amount_due = resolver['amount_due'](document)

        # Zero-amount documents: confirm directly, no transaction.
        if currency.is_zero(amount_due):
            resolver['confirm_zero_amount'](document)
            return {
                'state': 'done',
                'zero_amount': True,
                'document': resolver['state_summary'](document),
            }

        resolver['check_ready'](document)

        # Amount validation: the client-provided amount (if any) must match
        # the server-side amount due (website_sale pattern).
        amount = kwargs.get('amount')
        if amount is not None:
            amount = self._cast_as_float(amount)
            if amount is None or currency.compare_amounts(amount, amount_due):
                raise ApiError(
                    422, 'validation_error',
                    'The amount does not match the amount due. Please refresh.',
                    {'fields': {'amount': 'amount_mismatch'},
                     'amount_due': serializers.money(amount_due, currency)},
                )

        # Forbid a new transaction on top of a live one.
        if 'transaction_ids' in document._fields:
            live_txs = document.transaction_ids.filtered(
                lambda tx: tx.state in LIVE_TX_STATES
            )
            if live_txs:
                raise ApiError(
                    409, 'conflict',
                    'A payment is already ongoing or completed for this document.',
                )

        flow = kwargs.get('flow')
        if flow not in ('direct', 'redirect', 'token'):
            raise ApiError(400, 'bad_request',
                           'Invalid flow (expected direct, redirect or token).')

        provider_id = self._cast_as_int(kwargs.get('provider_id'))
        provider_sudo = request.env['payment.provider'].sudo().browse(provider_id or 0).exists()
        if not provider_sudo or provider_sudo.state not in ('enabled', 'test'):
            raise ApiError(400, 'bad_request', 'Invalid payment provider.')

        payment_method_id = self._cast_as_int(kwargs.get('payment_method_id'))
        token_id = self._cast_as_int(kwargs.get('token_id'))
        if flow == 'token':
            if not token_id:
                raise ApiError(400, 'bad_request', 'token_id is required for the token flow.')
        else:
            method_sudo = request.env['payment.method'].sudo().browse(
                payment_method_id or 0
            ).exists()
            if not method_sudo or provider_sudo.id not in method_sudo.provider_ids.ids:
                raise ApiError(400, 'bad_request', 'Invalid payment method.')

        partner = resolver['partner'](document)

        # Same creation path as the stock /payment/transaction route
        # (payment/controllers/portal.py PaymentPortal._create_transaction).
        # All values are resolved server-side; nothing else from the request
        # reaches the create values.
        tx_sudo = self._create_transaction(
            provider_id=provider_sudo.id,
            payment_method_id=payment_method_id,
            token_id=token_id,
            amount=amount_due,
            currency_id=currency.id,
            partner_id=partner.id,
            flow=flow,
            tokenization_requested=bool(kwargs.get('tokenize')),
            landing_route='/',  # Unused: the headless frontend handles the return.
            custom_create_values=resolver['custom_create_values'](document),
        )

        # Compute the processing values first: for Stripe direct this creates
        # the PaymentIntent and may move the transaction to 'error'.
        processing_values = self._tx_processing_values(tx_sudo)
        return {
            'transaction_id': tx_sudo.id,
            'reference': tx_sudo.reference,
            'provider_code': tx_sudo.provider_code,
            'flow': flow,
            'state': tx_sudo.state,
            'processing_values': processing_values,
        }

    @odusite_route(f'{API_PREFIX}/payment/transactions/<int:tx_id>', methods=['GET'])
    def odusite_payment_transaction_status(self, tx_id, access_token=None, **kwargs):
        """Poll a transaction state. Access through the linked document's
        access_token or as the JWT user owning the transaction."""
        tx_sudo = request.env['payment.transaction'].sudo().browse(tx_id).exists()
        if not tx_sudo:
            raise ApiError(404, 'not_found', 'The requested record does not exist.')
        document_type, document = self._transaction_document(tx_sudo)
        if not self._transaction_accessible(tx_sudo, document, access_token):
            # 404, not 403: don't leak the existence of transaction ids.
            raise ApiError(404, 'not_found', 'The requested record does not exist.')

        # Trigger the post-processing (order confirmation, invoice payment
        # reconciliation) like the stock /payment/status/poll route
        # (payment/controllers/post_processing.py). Draft transactions are
        # skipped; failures are left to the payment post-processing cron.
        if tx_sudo.state != 'draft' and not tx_sudo.is_post_processed:
            try:
                tx_sudo._post_process()
            except Exception:
                request.env.cr.rollback()
                _logger.exception(
                    'Error while post-processing transaction %s', tx_sudo.id)

        document_data = None
        if document is not None:
            resolver = request.env['odusite.payable']._odusite_payable_resolvers().get(document_type)
            if resolver:
                document_data = resolver['state_summary'](document)
            else:
                document_data = {
                    'type': document_type, 'id': document.id, 'state': document.state,
                }
        return {
            'state': tx_sudo.state,
            'state_message': tx_sudo.state_message or '',
            'is_post_processed': tx_sudo.is_post_processed,
            'document': document_data,
        }

    @odusite_route(f'{API_PREFIX}/payment/tokens', methods=['GET'], auth_user=True)
    def odusite_payment_tokens(self, **kwargs):
        """Saved payment methods of the JWT user (like /my/payment_method)."""
        partner = request.env.user.partner_id
        tokens_sudo = request.env['payment.token'].sudo()._get_available_tokens(
            None, partner.id, is_validation=True,
        )
        return [self._serialize_token(token) for token in tokens_sudo]

    @odusite_route(
        [f'{API_PREFIX}/payment/tokens', f'{API_PREFIX}/payment/tokens/<int:token_id>'],
        methods=['DELETE'], auth_user=True,
    )
    def odusite_payment_token_delete(self, token_id=None, **kwargs):
        """Archive a saved payment method (equivalent of the stock
        /payment/archive_token route: ownership check + active=False)."""
        token_id = self._cast_as_int(token_id)
        if not token_id:
            raise ApiError(400, 'bad_request', 'Missing token_id.')
        partner = request.env.user.partner_id
        token_sudo = request.env['payment.token'].sudo().search([
            ('id', '=', token_id),
            ('partner_id', 'in', [partner.id, partner.commercial_partner_id.id]),
        ])
        if not token_sudo:
            raise ApiError(404, 'not_found', 'The requested record does not exist.')
        token_sudo.active = False
        return None
