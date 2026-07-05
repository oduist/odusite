import json
import time

from odoo import http
from odoo.http import request
from odoo.tools import email_normalize, escape_psql
from odoo.tools.mail import plaintext2html

from odoo.addons.odusite_base.controllers.api import API_PREFIX, ApiError, odusite_route

HONEYPOT_FIELD = 'website_hp'
THROTTLE_PARAM = 'odusite.form_throttle'
THROTTLE_DEFAULT_LIMIT = 20
THROTTLE_DEFAULT_WINDOW = 3600


class OdusiteCrmController(http.Controller):

    def _honeypot_triggered(self, kwargs):
        return bool(str(kwargs.get(HONEYPOT_FIELD) or '').strip())

    def _check_rate_limit(self):
        """Per-IP submission throttle, defense in depth behind the site-side
        Turnstile check. Counters live in a single ir.config_parameter as
        {ip: [window_start, count]}; expired windows are pruned on the fly."""
        icp = request.env['ir.config_parameter'].sudo()
        try:
            limit = int(icp.get_param('odusite.form_rate_limit', THROTTLE_DEFAULT_LIMIT))
            window = int(icp.get_param('odusite.form_rate_window', THROTTLE_DEFAULT_WINDOW))
        except (TypeError, ValueError):
            limit, window = THROTTLE_DEFAULT_LIMIT, THROTTLE_DEFAULT_WINDOW
        if limit <= 0:
            return
        ip = request.httprequest.remote_addr or 'unknown'
        now = int(time.time())
        try:
            counters = json.loads(icp.get_param(THROTTLE_PARAM) or '{}')
        except ValueError:
            counters = {}
        counters = {
            key: value for key, value in counters.items()
            if isinstance(value, list) and len(value) == 2 and value[0] > now - window
        }
        start, count = counters.get(ip, (now, 0))
        if count >= limit:
            raise ApiError(429, 'too_many_requests',
                           'Too many form submissions, please retry later.')
        counters[ip] = [start, count + 1]
        icp.set_param(THROTTLE_PARAM, json.dumps(counters))

    def _get_or_create_utm(self, model, name):
        name = str(name or '').strip()
        if not name:
            return None
        Utm = request.env[model].sudo()
        record = Utm.search([('name', '=ilike', escape_psql(name))], limit=1)
        return record or Utm.create({'name': name})

    def _validate_required(self, kwargs, required):
        missing = {
            field: 'required' for field in required
            if not str(kwargs.get(field) or '').strip()
        }
        if missing:
            raise ApiError(422, 'validation_error', 'Missing required fields.',
                           {'fields': missing})

    @odusite_route(f'{API_PREFIX}/forms/contact', methods=['POST'])
    def form_contact(self, **kwargs):
        if self._honeypot_triggered(kwargs):
            return {'id': 0}
        self._check_rate_limit()
        self._validate_required(kwargs, ('name', 'email', 'message'))
        email = str(kwargs['email']).strip()
        if not email_normalize(email):
            raise ApiError(422, 'validation_error', 'Invalid email address.',
                           {'fields': {'email': 'invalid'}})
        meta = kwargs.get('meta')
        if not isinstance(meta, dict):
            meta = {}

        website = request.website
        name = str(kwargs['name']).strip()
        description = plaintext2html(str(kwargs['message']))
        if meta.get('page'):
            description += plaintext2html(f"Submitted from: {meta['page']}")
        medium = (self._get_or_create_utm('utm.medium', meta.get('utm_medium'))
                  or request.env['utm.medium'].sudo()._fetch_or_create_utm_medium('website'))
        source = self._get_or_create_utm('utm.source', meta.get('utm_source'))
        campaign = self._get_or_create_utm('utm.campaign', meta.get('utm_campaign'))

        values = {
            'type': 'lead',
            'name': str(kwargs.get('subject') or '').strip() or f'Website contact: {name}',
            'contact_name': name,
            'email_from': email,
            'phone': str(kwargs.get('phone') or '').strip() or False,
            'partner_name': str(kwargs.get('company') or '').strip() or False,
            'description': description,
            'company_id': website.company_id.id,
            'team_id': website.crm_default_team_id.id or False,
            'user_id': website.crm_default_user_id.id or False,
            'medium_id': medium.id,
            'source_id': source and source.id or False,
            'campaign_id': campaign and campaign.id or False,
        }
        lang_code = request.env.context.get('lang')
        if lang_code:
            lang_data = request.env['res.lang']._get_data(code=lang_code)
            if lang_data:
                values['lang_id'] = lang_data.id
        lead = request.env['crm.lead'].sudo().create(values)
        return {'id': lead.id}

    @odusite_route(f'{API_PREFIX}/forms/generic/<string:model>', methods=['POST'])
    def form_generic(self, model, **kwargs):
        """Whitelisted generic form endpoint. Other odusite modules register
        models via odusite.api._form_models():
        {model: {'fields': [...], 'required': [...], 'hook': callable|None}}
        where hook(record, values) post-processes the created record."""
        if self._honeypot_triggered(kwargs):
            return {'id': 0}
        self._check_rate_limit()
        form_spec = request.env['odusite.api']._form_models().get(model)
        if not form_spec:
            raise ApiError(404, 'not_found', 'Unknown form model.')
        self._validate_required(kwargs, form_spec.get('required', ()))
        values = {
            field: kwargs[field]
            for field in form_spec.get('fields', ())
            if field in kwargs
        }
        try:
            record = request.env[model].sudo().create(values)
        except ValueError as exc:
            raise ApiError(400, 'bad_request', str(exc))
        hook = form_spec.get('hook')
        if callable(hook):
            hook(record, kwargs)
        return {'id': record.id}
