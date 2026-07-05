from odoo import http
from odoo.http import request

from ..lib import serializers
from .api import API_PREFIX, odusite_route


class OdusiteBaseController(http.Controller):

    @odusite_route(f'{API_PREFIX}/health', methods=['GET'])
    def health(self, **kwargs):
        module = request.env['ir.module.module'].sudo().search(
            [('name', '=', 'odusite_base')], limit=1)
        return {'status': 'ok', 'version': module.latest_version or ''}

    @odusite_route(f'{API_PREFIX}/site', methods=['GET'])
    def site(self, **kwargs):
        website = request.website
        company = website.company_id.sudo()
        languages = website.language_ids or website.default_lang_id
        return {
            'name': website.name,
            'company': {
                'name': company.name,
                'street': company.street or '',
                'street2': company.street2 or '',
                'city': company.city or '',
                'zip': company.zip or '',
                'country': company.country_id.name or '',
                'email': company.email or '',
                'phone': company.phone or '',
                'vat': company.vat or '',
            },
            'logo': serializers.image_url(website, 'logo'),
            'favicon': serializers.image_url(website, 'favicon'),
            'social': {
                name: website[f'social_{name}'] or None
                for name in ('facebook', 'twitter', 'linkedin', 'youtube',
                             'instagram', 'github', 'tiktok', 'discord')
            },
            'languages': [
                {'code': lang.code, 'url_code': lang.url_code, 'name': lang.name}
                for lang in languages
            ],
            'default_language': website.default_lang_id.code,
            'currency': company.currency_id.name,
        }

    @odusite_route(f'{API_PREFIX}/menus', methods=['GET'])
    def menus(self, **kwargs):
        website = request.website
        top_menu = website.menu_id
        return [
            self._serialize_menu(child)
            for child in top_menu.child_id.sorted('sequence')
            if self._menu_visible(child)
        ]

    def _menu_visible(self, menu):
        if menu.group_ids:
            user = request.env.user
            if user._is_public() or not (user.all_group_ids & menu.group_ids):
                return False
        return bool(menu.url or menu.child_id)

    def _serialize_menu(self, menu):
        return {
            'id': menu.id,
            'name': menu.name,
            'url': menu.url or '#',
            'new_window': menu.new_window,
            'sequence': menu.sequence,
            'children': [
                self._serialize_menu(child)
                for child in menu.child_id.sorted('sequence')
                if self._menu_visible(child)
            ],
        }

    @odusite_route(f'{API_PREFIX}/sitemap', methods=['GET'])
    def sitemap(self, **kwargs):
        entries = request.env['odusite.api']._sitemap_entries(request.website)
        return [
            {
                'url': entry['url'],
                'lastmod': serializers.datetime_utc(entry.get('lastmod')),
            }
            for entry in entries
        ]

    @odusite_route(f'{API_PREFIX}/redirects', methods=['GET'])
    def redirects(self, **kwargs):
        rewrites = request.env['website.rewrite'].sudo().search([
            ('redirect_type', 'in', ('301', '302')),
            ('website_id', 'in', (False, request.website.id)),
        ])
        return [
            {'from': rewrite.url_from, 'to': rewrite.url_to,
             'type': int(rewrite.redirect_type)}
            for rewrite in rewrites
            if rewrite.url_from and rewrite.url_to
        ]

    @odusite_route(f'{API_PREFIX}/countries', methods=['GET'])
    def countries(self, **kwargs):
        countries = request.env['res.country'].sudo().search([])
        return [
            {
                'id': country.id,
                'code': country.code,
                'name': country.name,
                'zip_required': country.zip_required,
                'state_required': country.state_required,
                'states': [
                    {'id': state.id, 'code': state.code, 'name': state.name}
                    for state in country.state_ids
                ],
            }
            for country in countries
        ]
