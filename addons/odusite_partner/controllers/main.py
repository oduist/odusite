from odoo import http
from odoo.fields import Domain
from odoo.http import request

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    list_meta,
    odusite_route,
    parse_pagination,
)
from odoo.addons.odusite_base.lib import serializers


class OdusitePartnerController(http.Controller):
    """Public partner directory.

    Optional enrichment (detected at runtime through field presence):
    - website_crm_partner_assign: grade_id / assigned_partner_id /
      implemented_partner_ids (resellers and references);
    - website_customer: website_tag_ids / res.partner.tag.
    """

    def _partner_fields(self):
        return request.env['res.partner']._fields

    def _published_partner_domain(self):
        return Domain.AND([
            request.website.website_domain(),
            [('is_published', '=', True)],
        ])

    def _ref_id(self, value, label):
        _, record_id = serializers.unslug(str(value))
        if not record_id:
            raise ApiError(400, 'bad_request', f'Invalid {label}: {value}')
        return record_id

    def _country_id(self, value):
        value = str(value)
        if not value.isdigit() and len(value) == 2 and value.isalpha():
            country = request.env['res.country'].sudo().search(
                [('code', '=', value.upper())], limit=1)
            if not country:
                raise ApiError(400, 'bad_request', f'Unknown country code: {value}')
            return country.id
        return self._ref_id(value, 'country')

    def _partner_domain(self, kind=None, country=None, grade=None, tag=None,
                        search=None, **kwargs):
        partner_fields = self._partner_fields()
        domain = self._published_partner_domain()
        if kind == 'customers':
            # website_customer semantics: implemented references; fallback to
            # plain published companies when the module is not installed.
            if 'assigned_partner_id' in partner_fields:
                domain &= Domain('assigned_partner_id', '!=', False)
            else:
                domain &= Domain('is_company', '=', True)
        elif kind == 'resellers':
            # website_crm_partner_assign semantics: graded companies.
            if 'grade_id' in partner_fields:
                domain = Domain.AND([domain, [
                    ('is_company', '=', True),
                    ('grade_id', '!=', False),
                    ('grade_id.active', '=', True),
                    ('grade_id.website_published', '=', True),
                ]])
            else:
                domain &= Domain('is_company', '=', True)
        elif kind:
            raise ApiError(400, 'bad_request', f'Unsupported kind: {kind}',
                           {'allowed': ['customers', 'resellers']})
        if country:
            domain &= Domain('country_id', '=', self._country_id(country))
        if grade and 'grade_id' in partner_fields:
            domain &= Domain('grade_id', '=', self._ref_id(grade, 'grade'))
        if tag and 'website_tag_ids' in partner_fields:
            domain &= Domain('website_tag_ids', 'in', [self._ref_id(tag, 'tag')])
        if search:
            domain &= Domain.OR([
                [('name', 'ilike', search)],
                [('website_short_description', 'ilike', search)],
                [('website_description', 'ilike', search)],
                [('city', 'ilike', search)],
            ])
        return domain

    def _partner_facets(self, **kwargs):
        """Countries and grades with counts. Like the upstream directory
        controllers, each facet is computed with every filter applied except
        its own."""
        Partner = request.env['res.partner'].sudo()
        country_groups = Partner._read_group(
            self._partner_domain(**dict(kwargs, country=None)),
            ['country_id'], ['__count'])
        facets = {
            'countries': [
                {'id': country.id, 'code': country.code, 'name': country.name,
                 'count': count}
                for country, count in country_groups if country
            ],
            'grades': [],
        }
        if 'grade_id' in self._partner_fields():
            grade_groups = Partner._read_group(
                self._partner_domain(**dict(kwargs, grade=None)),
                ['grade_id'], ['__count'])
            facets['grades'] = [
                {'id': grade.id, 'name': grade.name, 'count': count}
                for grade, count in grade_groups if grade
            ]
        return facets

    def _serialize_partner(self, partner):
        partner_fields = self._partner_fields()
        data = {
            'id': partner.id,
            'slug': serializers.slug(partner),
            'name': partner.name,
            'logo': serializers.image_url(partner, 'image_512'),
            'short_description': partner.website_short_description or '',
            'city': partner.city or '',
            'country': partner.country_id.name or '',
            'tags': [],
        }
        if 'grade_id' in partner_fields:
            grade = partner.grade_id
            data['grade'] = {'id': grade.id, 'name': grade.name} if grade else None
        if 'website_tag_ids' in partner_fields:
            data['tags'] = [
                {'id': tag.id, 'name': tag.name, 'class': tag.classname}
                for tag in partner.website_tag_ids
            ]
        return data

    def _get_published_partner(self, ref):
        _, partner_id = serializers.unslug(str(ref))
        if not partner_id:
            raise ApiError(404, 'not_found', 'Partner not found.')
        partner = request.env['res.partner'].sudo().browse(partner_id).exists()
        if not partner or not partner.filtered_domain(self._published_partner_domain()):
            raise ApiError(404, 'not_found', 'Partner not found.')
        return partner

    @odusite_route(f'{API_PREFIX}/partners', methods=['GET'])
    def partners(self, **kwargs):
        page, limit, offset, _order = parse_pagination(kwargs)
        domain = self._partner_domain(**kwargs)
        Partner = request.env['res.partner'].sudo()
        total = Partner.search_count(domain)
        order = 'complete_name asc, id desc'
        if 'grade_sequence' in self._partner_fields():
            order = f'grade_sequence asc, {order}'
        partners = Partner.search(domain, limit=limit, offset=offset, order=order)
        meta = list_meta(total, page, limit, facets=self._partner_facets(**kwargs))
        return [self._serialize_partner(partner) for partner in partners], meta

    @odusite_route(f'{API_PREFIX}/partners/<string:partner_ref>', methods=['GET'])
    def partner_detail(self, partner_ref, **kwargs):
        partner = self._get_published_partner(partner_ref)
        data = self._serialize_partner(partner)
        data.update({
            'description_html': serializers.html_field(partner, 'website_description'),
            'website': partner.website or '',
            'industry': partner.industry_id.name or '',
            'seo': serializers.seo(partner),
        })
        if 'implemented_partner_ids' in self._partner_fields():
            references = partner.implemented_partner_ids.filtered(
                lambda reference: reference.active and reference.is_published)
            data['references'] = [
                {'id': reference.id, 'slug': serializers.slug(reference),
                 'name': reference.name}
                for reference in references
            ]
        return data
