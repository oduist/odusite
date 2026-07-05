"""Portal profile endpoints /odusite/v1/me/* (specs/modules/odusite_portal.md).

All routes require a Bearer JWT (``auth_user=True``): the request env runs as
the JWT user, so record rules apply exactly like an ``/my/*`` session.

Subclasses portal's ``CustomerPortal`` to reuse its address form pipeline
(``_create_or_update_address``, ``_prepare_address_data``,
``_validate_address_values`` — portal/controllers/portal.py); no portal route
is overridden.
"""

from odoo import fields
from odoo.exceptions import AccessDenied
from odoo.http import request

from odoo.addons.odusite_base.controllers.api import API_PREFIX, ApiError, odusite_route
from odoo.addons.odusite_base.lib import serializers
from odoo.addons.portal.controllers.portal import CustomerPortal

ADDRESS_TYPES = ('billing', 'delivery')


class OdusiteMeController(CustomerPortal):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _serialize_address(self, partner):
        partner = partner.sudo()
        state = partner.state_id
        country = partner.country_id
        return {
            'id': partner.id,
            'name': partner.name or '',
            'email': partner.email or '',
            'phone': partner.phone or '',
            'street': partner.street or '',
            'street2': partner.street2 or '',
            'city': partner.city or '',
            'zip': partner.zip or '',
            'state': {'id': state.id, 'code': state.code, 'name': state.name} if state else None,
            'country': {'id': country.id, 'code': country.code, 'name': country.name} if country else None,
            'vat': partner.vat or '',
            'company_name': partner.commercial_company_name or partner.company_name or '',
            'type': partner.type,
        }

    def _me_payload(self):
        user = request.env.user
        partner = user.partner_id.with_context(show_address=1)
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email or user.login,
            'phone': partner.phone or '',
            'lang': user.lang or None,
            'partner': self._serialize_address(partner),
        }

    def _extract_address_form_data(self, params):
        """Keep only fields the portal form pipeline may write
        (res.partner._get_frontend_writable_fields, portal/models/res_partner.py)
        so control kwargs of _create_or_update_address (callback,
        verify_address_values, ...) cannot be injected from the JSON body."""
        allowed = set(request.env['res.partner']._get_frontend_writable_fields())
        allowed.add('zipcode')  # alias handled by _parse_form_data
        form_data = {}
        for key, value in params.items():
            if key not in allowed:
                continue
            form_data[key] = '' if value is None or value is False else value
        return form_data

    def _prefill_from_partner(self, form_data, partner_sudo):
        """Complete a partial update with the record's current values, so
        _validate_address_values sees a full form like the portal one."""
        Partner = request.env['res.partner']
        for fname in Partner._get_frontend_writable_fields():
            if fname in form_data or fname not in Partner._fields:
                continue
            value = partner_sudo[fname]
            if Partner._fields[fname].type == 'many2one':
                value = value.id
            form_data[fname] = value or ''
        return form_data

    def _ensure_request_lang(self):
        """portal's _complete_address_values reads ``request.lang``, which is
        only set by http_routing's frontend dispatch; provide it for API
        requests (mirrors http_routing/models/ir_http.py)."""
        if getattr(request, 'lang', None):
            return
        Lang = request.env['res.lang']
        code = request.env.context.get('lang') or request.website.default_lang_id.code
        request.lang = Lang._get_data(code=code) \
            or Lang._get_data(code=request.website.default_lang_id.code)

    def _raise_address_feedback(self, feedback):
        """Convert _create_or_update_address feedback into a 422 ApiError."""
        if feedback.get('redirectUrl') is not None:
            return
        invalid_fields = list(feedback.get('invalid_fields') or [])
        messages = [str(message) for message in (feedback.get('messages') or [])]
        raise ApiError(
            422, 'validation_error',
            ' '.join(messages) or 'Invalid address values.',
            # portal reports one message list for all invalid fields; expose
            # it per field so the frontend can highlight inputs.
            {'fields': dict.fromkeys(invalid_fields, messages or ['Invalid value.'])},
        )

    def _get_own_address(self, address_id):
        """Return an address the JWT user may edit through the address book:
        a child of their commercial partner, excluding the main/commercial
        addresses (those are managed through /me)."""
        address_sudo = request.env['res.partner'].with_context(
            show_address=1).sudo().browse(address_id).exists()
        if not address_sudo or not address_sudo._can_be_edited_by_current_customer():
            # Do not reveal other customers' partner ids.
            raise ApiError(404, 'not_found', 'The requested address does not exist.')
        partner = request.env.user.partner_id
        if address_sudo.id in (partner.id, partner.commercial_partner_id.id):
            raise ApiError(403, 'forbidden',
                           'The main address is managed through /me.')
        return address_sudo

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    @odusite_route(f'{API_PREFIX}/me', methods=['GET'], auth_user=True)
    def me_get(self, **params):
        return self._me_payload()

    @odusite_route(f'{API_PREFIX}/me', methods=['PUT'], auth_user=True)
    def me_update(self, **params):
        """Update the profile / main address, with the exact /my/account
        pipeline (VAT & commercial fields rules included)."""
        partner_sudo = request.env.user.partner_id.with_context(show_address=1)
        form_data = self._prefill_from_partner(
            self._extract_address_form_data(params), partner_sudo)
        self._ensure_request_lang()
        _partner, feedback = self._create_or_update_address(
            partner_sudo,
            address_type='billing',
            # The main address serves as both billing and delivery address,
            # like the /my/account form.
            use_delivery_as_billing='true',
            callback='',
            **form_data,
        )
        self._raise_address_feedback(feedback)
        return self._me_payload()

    @odusite_route(f'{API_PREFIX}/me/password', methods=['PUT'], auth_user=True)
    def me_password(self, old_password=None, new_password=None, refresh_token=None, **params):
        if not isinstance(old_password, str) or not old_password:
            raise ApiError(422, 'validation_error', 'old_password is required.',
                           {'fields': {'old_password': 'This field is required.'}})
        if not isinstance(new_password, str) or not new_password.strip():
            raise ApiError(422, 'validation_error', 'new_password is required.',
                           {'fields': {'new_password': 'This field is required.'}})
        try:
            # Verifies the old password through _check_credentials before
            # writing (base/models/res_users.py change_password).
            request.env['res.users'].change_password(old_password, new_password)
        except AccessDenied:
            raise ApiError(
                422, 'validation_error',
                'The old password you provided is incorrect.',
                {'fields': {'old_password': 'Incorrect password.'}})
        # Invalidate the other sessions. The optional refresh_token lets the
        # caller keep its own session alive (an access JWT cannot be mapped
        # back to a refresh-token row).
        request.env['odusite.refresh.token']._revoke_all(
            request.env.user, keep_raw_token=refresh_token)
        return {'ok': True}

    # ------------------------------------------------------------------
    # Address book (mirrors /my/addresses, /my/address/submit, .../archive)
    # ------------------------------------------------------------------

    @odusite_route(f'{API_PREFIX}/me/addresses', methods=['GET'], auth_user=True)
    def me_addresses(self, **params):
        address_data = self._prepare_address_data(request.env.user.partner_id)
        return {
            'billing': [self._serialize_address(partner)
                        for partner in address_data['billing_addresses']],
            'delivery': [self._serialize_address(partner)
                         for partner in address_data['delivery_addresses']],
        }

    @odusite_route(f'{API_PREFIX}/me/addresses', methods=['POST'], auth_user=True)
    def me_address_create(self, address_type=None, **params):
        if address_type not in ADDRESS_TYPES:
            raise ApiError(
                422, 'validation_error',
                "address_type must be 'billing' or 'delivery'.",
                {'fields': {'address_type': "Expected 'billing' or 'delivery'."}})
        self._ensure_request_lang()
        form_data = self._extract_address_form_data(params)
        partner_sudo, feedback = self._create_or_update_address(
            request.env['res.partner'].with_context(show_address=1).sudo().browse(),
            address_type=address_type,
            use_delivery_as_billing='false',
            callback='',
            **form_data,
        )
        self._raise_address_feedback(feedback)
        return self._serialize_address(partner_sudo)

    @odusite_route(f'{API_PREFIX}/me/addresses/<int:address_id>',
                   methods=['PUT'], auth_user=True)
    def me_address_update(self, address_id, address_type=None, **params):
        address_sudo = self._get_own_address(address_id)
        if address_type is None:
            address_type = 'delivery' if address_sudo.type == 'delivery' else 'billing'
        elif address_type not in ADDRESS_TYPES:
            raise ApiError(
                422, 'validation_error',
                "address_type must be 'billing' or 'delivery'.",
                {'fields': {'address_type': "Expected 'billing' or 'delivery'."}})
        self._ensure_request_lang()
        form_data = self._prefill_from_partner(
            self._extract_address_form_data(params), address_sudo)
        _partner, feedback = self._create_or_update_address(
            address_sudo,
            address_type=address_type,
            use_delivery_as_billing='false',
            callback='',
            **form_data,
        )
        self._raise_address_feedback(feedback)
        return self._serialize_address(address_sudo)

    @odusite_route(f'{API_PREFIX}/me/addresses/<int:address_id>',
                   methods=['DELETE'], auth_user=True)
    def me_address_delete(self, address_id, **params):
        # Archive, never unlink — mirrors /my/address/archive.
        address_sudo = self._get_own_address(address_id)
        address_sudo.action_archive()
        return None

    # ------------------------------------------------------------------
    # Counters
    # ------------------------------------------------------------------

    @odusite_route(f'{API_PREFIX}/me/counters', methods=['GET'], auth_user=True)
    def me_counters(self, counters=None, **params):
        keys = [key.strip() for key in str(counters or '').split(',') if key.strip()]
        return request.env['odusite.api']._portal_counters(keys)

    # ------------------------------------------------------------------
    # Sessions (refresh tokens)
    # ------------------------------------------------------------------

    @odusite_route(f'{API_PREFIX}/me/sessions', methods=['GET'], auth_user=True)
    def me_sessions(self, **params):
        # sudo: odusite.refresh.token is system-only; scoped to the JWT user.
        tokens = request.env['odusite.refresh.token'].sudo().search([
            ('user_id', '=', request.env.uid),
            ('revoked', '=', False),
            ('expires_at', '>', fields.Datetime.now()),
        ], order='id desc')
        return [
            {
                'id': token.id,
                'user_agent': token.user_agent or '',
                'ip': token.ip or '',
                'created_at': serializers.datetime_utc(token.create_date),
                'last_used_at': serializers.datetime_utc(token.last_used_at),
                'expires_at': serializers.datetime_utc(token.expires_at),
                # Access JWTs are not tied to a refresh-token row, so the
                # current session cannot be singled out.
                'is_current': False,
            }
            for token in tokens
        ]

    @odusite_route(f'{API_PREFIX}/me/sessions/<int:session_id>',
                   methods=['DELETE'], auth_user=True)
    def me_session_revoke(self, session_id, **params):
        token = request.env['odusite.refresh.token'].sudo().search([
            ('id', '=', session_id),
            ('user_id', '=', request.env.uid),
        ], limit=1)
        if not token:
            raise ApiError(404, 'not_found', 'Unknown session.')
        token.write({'revoked': True})
        return None
