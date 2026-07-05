"""Unified site search over Odoo's website search (website.searchable.mixin).

Wraps ``website._search_with_fuzzy()`` — the same machinery behind
``/website/search`` — and flattens the per-model results into a single list of
``{type, id, name, url, description?, image?}`` items. Publication filtering is
NOT re-implemented here: each searchable model's ``_search_get_detail()``
already constrains its base domain to the website (``website_domain()``) and
published records (explicitly, or through the public-user record rules when the
model is searched without sudo). This controller must therefore never search
with a sudo env — see :func:`_request_website`.
"""

from textwrap import shorten

from odoo import http
from odoo.http import request

from .api import API_PREFIX, DEFAULT_LIMIT, MAX_LIMIT, ApiError, odusite_route

# website.page QWeb pages are intentionally not exposed to the Astro site
# (see specs/decisions.md: marketing pages live in Astro, not in Odoo).
EXCLUDED_MODELS = {'website.page'}

DESCRIPTION_MAX_CHARS = 300


class OdusiteSearchController(http.Controller):

    @odusite_route(f'{API_PREFIX}/search', methods=['GET'])
    def search(self, q=None, types=None, limit=None, **kwargs):
        term = (q or '').strip()
        if not term:
            raise ApiError(400, 'bad_request', 'Missing required parameter: q.')
        limit = self._parse_limit(limit)

        website = self._request_website()
        # Same default order as website's /website/search (_get_search_order).
        order = 'is_published desc, name asc, id desc'
        options = self._search_options(website)

        search_details = website._search_get_details('all', order, options)
        search_details = self._filter_details(search_details, types)
        if not search_details:
            # No searchable model matches (e.g. the requested types belong to
            # modules that are not installed) — graceful empty result.
            return {'results': [], 'fuzzy_term': None}, {'count': 0}

        # Mirrors website._search_with_fuzzy(), which cannot be called
        # directly because the details list must be filtered first.
        fuzzy_term = False
        if options.get('allowFuzzy', True):
            fuzzy_term = website._search_find_fuzzy_term(search_details, term)
            if fuzzy_term:
                count, results = website._search_exact(search_details, fuzzy_term, limit, order)
                if fuzzy_term.lower() == term.lower():
                    fuzzy_term = False
            else:
                count, results = website._search_exact(search_details, term, limit, order)
        else:
            count, results = website._search_exact(search_details, term, limit, order)

        results = website._search_render_results(results, limit)
        items = []
        for detail in results:
            items.extend(self._map_results(detail))
        return {'results': items, 'fuzzy_term': fuzzy_term or None}, {'count': count}

    # -- helpers -----------------------------------------------------------

    def _parse_limit(self, limit):
        if limit is None:
            return DEFAULT_LIMIT
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise ApiError(400, 'bad_request', 'Invalid limit parameter.')
        return max(1, min(limit, MAX_LIMIT))

    def _request_website(self):
        """Return request.website bound to the request env (public or JWT
        user). ``odusite_route`` resolves the website with sudo; searching
        from a sudo env would bypass the public record rules that hide
        unpublished records on models like product.template and blog.post."""
        return request.website.with_env(request.env)

    def _search_options(self, website):
        # Same shape as Website._get_hybrid_search_options(); prices/extra
        # details are left out — detail endpoints of the odusite_* modules
        # are the source of entity data, search only needs the essentials.
        options = {
            'displayDescription': True,
            'displayDetail': False,
            'displayExtraDetail': False,
            'displayExtraLink': False,
            'displayImage': True,
            'allowFuzzy': True,
        }
        if 'currency_id' in website._fields:
            # website_sale models read it when rendering monetary fields.
            options['display_currency'] = website.currency_id
        return options

    def _filter_details(self, search_details, types):
        search_details = [
            detail for detail in search_details
            if detail['model'] not in EXCLUDED_MODELS
        ]
        if types:
            wanted = {name.strip() for name in types.split(',') if name.strip()}
            search_details = [
                detail for detail in search_details if detail['model'] in wanted
            ]
        return search_details

    def _map_results(self, detail):
        """Flatten one rendered search detail into API result items using its
        ``mapping`` (see website.searchable.mixin._search_get_detail)."""
        mapping = detail['mapping']
        name_field = mapping.get('name', {}).get('name')
        url_field = mapping.get('website_url', {}).get('name')
        description_field = mapping.get('description', {}).get('name')
        image_field = mapping.get('image_url', {}).get('name')

        items = []
        for data in detail.get('results_data', []):
            item = {
                'type': detail['model'],
                'id': data['id'],
                'name': str(data.get(name_field) or '') if name_field else '',
                'url': str(data.get(url_field) or '') if url_field else '',
            }
            description = description_field and data.get(description_field)
            if description:
                item['description'] = shorten(
                    str(description), DESCRIPTION_MAX_CHARS, placeholder='…')
            image = image_field and data.get(image_field)
            if image:
                item['image'] = str(image)
            items.append(item)
        return items
