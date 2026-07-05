"""Catalog endpoints: categories tree, product listing, product detail,
combination info (see specs/modules/odusite_sale.md)."""

from odoo import fields, http
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

from .common import amount, peek_cart, serialize_combination_info

PRODUCT_ORDER_WHITELIST = {
    'relevance': 'website_sequence asc',
    'price_asc': 'list_price asc',
    'price_desc': 'list_price desc',
    'name': 'name asc',
    'newest': 'publish_date desc',
}


class OdusiteShopController(http.Controller):

    # === CATEGORIES === #

    @odusite_route(f'{API_PREFIX}/shop/categories', methods=['GET'])
    def shop_categories(self, **kwargs):
        website = request.website
        Category = request.env['product.public.category'].sudo()
        categories = Category.search(Domain.AND([
            website.website_domain(),
            [('has_published_products', '=', True)],
        ]))

        counts = {}
        if categories:
            groups = request.env['product.template'].sudo()._read_group(
                Domain.AND([
                    [('public_categ_ids', 'in', categories.ids)],
                    self._published_product_domain(),
                ]),
                groupby=['public_categ_ids'],
                aggregates=['__count'],
            )
            counts = {category.id: count for category, count in groups}

        def serialize(category):
            return {
                'id': category.id,
                'slug': serializers.slug(category),
                'name': category.name,
                'parent_id': category.parent_id.id or None,
                'product_count': counts.get(category.id, 0),
                'cover': (
                    serializers.image_url(category, 'image_512')
                    or serializers.image_url(category, 'cover_image')
                ),
                'children': [
                    serialize(child)
                    for child in category.child_id.sorted('sequence')
                    if child in categories
                ],
            }

        return [
            serialize(category)
            for category in categories
            if not category.parent_id or category.parent_id not in categories
        ]

    # === PRODUCT LISTING === #

    @odusite_route(f'{API_PREFIX}/shop/products', methods=['GET'])
    def shop_products(self, category=None, search='', min_price=0.0, max_price=0.0,
                      tags='', attribs='', **kwargs):
        peek_cart()
        website = request.website
        page, limit, offset, order = parse_pagination(
            kwargs, PRODUCT_ORDER_WHITELIST, default_order='relevance')
        order = f'{order}, id desc'  # unique sort key, like _get_search_order()

        domain = self._product_listing_domain(category, search, min_price, max_price,
                                              tags, attribs)
        templates = request.env['product.template'].sudo().with_context(bin_size=True).search(
            domain, order=order)
        total = len(templates)
        page_templates = templates[offset:offset + limit].with_company(website.company_id)

        prices = page_templates._get_sales_prices(website)
        data = [self._serialize_product_item(template, prices) for template in page_templates]
        meta = list_meta(total, page, limit, facets=self._product_facets(templates.ids))
        return data, meta

    def _published_product_domain(self):
        # Built with the request (public/JWT) env so the published/saleable
        # user domain of website.sale_product_domain() applies.
        return Domain(request.env['website'].sale_product_domain())

    def _product_listing_domain(self, category, search, min_price, max_price, tags, attribs):
        """Mirror website_sale's shop domain (main.py _get_shop_domain)."""
        website = request.website
        domains = [self._published_product_domain()]

        if search:
            for word in str(search).split(' '):
                if not word:
                    continue
                domains.append(Domain.OR([
                    Domain('name', 'ilike', word),
                    Domain('variants_default_code', 'ilike', word),
                    Domain('website_description', 'ilike', word),
                    Domain('description_sale', 'ilike', word),
                ]))

        if category:
            category_id = serializers.unslug(str(category))[1]
            category_record = request.env['product.public.category'].sudo().browse(
                category_id or 0).exists()
            if (
                not category_record
                or not category_record.filtered_domain(website.website_domain())
            ):
                raise ApiError(404, 'not_found', 'Category not found.')
            domains.append(Domain('public_categ_ids', 'child_of', category_record.id))

        min_price, max_price = self._parse_price(min_price), self._parse_price(max_price)
        if min_price or max_price:
            # list_price is stored in the company currency; convert the
            # website-currency bounds like the stock shop does.
            company_currency = website.company_id.sudo().currency_id
            conversion_rate = request.env['res.currency']._get_conversion_rate(
                company_currency, website.currency_id, website.company_id,
                fields.Date.today(),
            )
            if min_price:
                domains.append(Domain('list_price', '>=', min_price / conversion_rate))
            if max_price:
                domains.append(Domain('list_price', '<=', max_price / conversion_rate))

        if tags:
            tag_ids = [
                serializers.unslug(token.strip())[1]
                for token in str(tags).split(',') if token.strip()
            ]
            tag_ids = [tag_id for tag_id in tag_ids if tag_id]
            if tag_ids:
                domains.append(Domain.OR([
                    Domain('product_tag_ids', 'in', tag_ids),
                    Domain('product_variant_ids.additional_product_tag_ids', 'in', tag_ids),
                ]))

        attribute_value_dict = self._parse_attribs(attribs)
        if attribute_value_dict:
            domains.extend(
                Domain(item) for item in
                request.env['product.template']._get_attribute_value_domain(
                    attribute_value_dict)
            )

        return Domain.AND(domains)

    @staticmethod
    def _parse_price(value):
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_attribs(attribs):
        """Parse ``attribs=<attr>-<val>,...`` into {attribute_id: [value_ids]}
        (value ids are `product.attribute.value` ids, like the stock shop's
        ``attribute_values`` query parameter)."""
        result = {}
        for token in str(attribs or '').split(','):
            token = token.strip()
            if not token:
                continue
            attribute_id, _, value_id = token.partition('-')
            if not attribute_id.isdigit() or not value_id.isdigit():
                raise ApiError(400, 'bad_request', f'Malformed attribs token: {token}')
            result.setdefault(int(attribute_id), []).append(int(value_id))
        return result

    def _product_facets(self, template_ids):
        """Attribute facets (value counts) for the current result set."""
        if not template_ids:
            return {'attributes': []}
        groups = request.env['product.template.attribute.line'].sudo()._read_group(
            [
                ('product_tmpl_id', 'in', template_ids),
                ('attribute_id.visibility', '=', 'visible'),
            ],
            groupby=['attribute_id', 'value_ids'],
            aggregates=['product_tmpl_id:count_distinct'],
        )
        facets = {}
        for attribute, value, count in groups:
            if not value:
                continue
            entry = facets.setdefault(attribute.id, {
                'id': attribute.id,
                'name': attribute.name,
                'display_type': attribute.display_type,
                'values': [],
            })
            entry['values'].append({
                'id': value.id,
                'name': value.name,
                'html_color': value.html_color or None,
                'count': count,
            })
        return {'attributes': list(facets.values())}

    def _serialize_product_item(self, template, prices):
        website = request.website
        currency = website.currency_id
        price_vals = prices.get(template.id, {})
        price = price_vals.get('price_reduce', 0.0)
        base_price = price_vals.get('base_price')

        images = template._get_images()
        second_image = serializers.image_url(images[1], 'image_512') if len(images) > 1 else None

        values = {
            'id': template.id,
            'slug': serializers.slug(template),
            'name': template.name,
            'list_price': amount(base_price if base_price else price, currency),
            'price': amount(price, currency),
            'has_discounted_price': (
                bool(base_price) and currency.compare_amounts(base_price, price) == 1
            ),
            'currency': currency.name,
            'image': serializers.image_url(template._get_image_holder(), 'image_512'),
            'second_image': second_image,
            'tags': [
                {'id': tag.id, 'name': tag.name}
                for tag in template.product_tag_ids.filtered('visible_to_customers')
            ],
            'category_ids': template.public_categ_ids.filtered(
                lambda c: not c.website_id or c.website_id == website
            ).ids,
        }
        if template.rating_count:
            values['rating'] = {
                'avg': round(template.rating_avg, 2),
                'count': template.rating_count,
            }
        return values

    # === PRODUCT DETAIL === #

    @odusite_route(f'{API_PREFIX}/shop/products/<string:id_or_slug>', methods=['GET'])
    def shop_product_detail(self, id_or_slug, **kwargs):
        peek_cart()
        template = self._get_published_template(id_or_slug)
        return self._serialize_product_detail(template)

    def _get_published_template(self, id_or_slug):
        template_id = serializers.unslug(str(id_or_slug))[1]
        template_sudo = request.env['product.template'].sudo().browse(
            template_id or 0).exists()
        if not template_sudo or not template_sudo.filtered_domain(
            self._published_product_domain()
        ):
            raise ApiError(404, 'not_found', 'Product not found.')
        # Keep the request (public/JWT) env on the record: website_sale model
        # code sudoes internally exactly where the stock controllers do.
        return request.env['product.template'].browse(template_sudo.id).with_company(
            request.website.company_id)

    def _combination_context(self):
        context = {}
        if 'allow_out_of_stock_order' in request.env['product.template']._fields:
            # website_sale_stock is installed: include stock info.
            context['website_sale_stock_get_quantity'] = True
        return context

    def _serialize_product_detail(self, template):
        website = request.website
        currency = website.currency_id
        template_sudo = template.sudo()

        combination_info = template.with_context(
            **self._combination_context()
        )._get_combination_info()

        alternatives = template._get_website_alternative_product()
        alternative_prices = alternatives._get_sales_prices(website) if alternatives else {}
        accessories = template._get_website_accessory_product()
        documents = template_sudo.product_document_ids.filtered(
            lambda document: document.active and document.shown_on_product_page
        )
        template_slug = serializers.slug(template)

        values = {
            'id': template.id,
            'slug': template_slug,
            'name': template.name,
            'description_html': (
                serializers.html_field(template, 'website_description')
                or serializers.html_field(template, 'description_ecommerce')
            ),
            'images': [
                {
                    'id': image.id,
                    'name': image.name or '',
                    'image': serializers.image_url(image, 'image_1024'),
                    'video_url': (
                        image.video_url if 'video_url' in image._fields else None
                    ) or None,
                }
                for image in template_sudo._get_images()
            ],
            'attribute_lines': [
                self._serialize_attribute_line(ptal, currency)
                for ptal in template_sudo.valid_product_template_attribute_line_ids
            ],
            'combination': serialize_combination_info(combination_info, template),
            'alternatives': [
                {
                    'id': alternative.id,
                    'slug': serializers.slug(alternative),
                    'name': alternative.name,
                    'image': serializers.image_url(
                        alternative._get_image_holder(), 'image_512'),
                    'price': amount(
                        alternative_prices.get(alternative.id, {}).get('price_reduce'),
                        currency),
                    'currency': currency.name,
                }
                for alternative in alternatives
            ],
            'accessories': [
                {
                    'id': accessory.id,
                    'template_id': accessory.product_tmpl_id.id,
                    'slug': serializers.slug(accessory.product_tmpl_id),
                    'name': accessory.display_name,
                    'image': serializers.image_url(accessory, 'image_512'),
                }
                for accessory in accessories
            ],
            'documents': [
                {
                    'id': document.id,
                    'name': document.name or '',
                    # Stock public download route from website_sale.
                    'url': f'/shop/{template_slug}/document/{document.id}',
                }
                for document in documents
            ],
            'tags': [
                {'id': tag.id, 'name': tag.name}
                for tag in template_sudo.product_tag_ids.filtered('visible_to_customers')
            ],
            'category_ids': template_sudo.public_categ_ids.filtered(
                lambda c: not c.website_id or c.website_id == website
            ).ids,
            'seo': serializers.seo(template),
            'json_ld': template._to_markup_data(website),
        }
        if template_sudo.rating_count:
            values['rating'] = {
                'avg': round(template_sudo.rating_avg, 2),
                'count': template_sudo.rating_count,
            }
        return values

    def _serialize_attribute_line(self, ptal, currency):
        return {
            'id': ptal.id,
            'attribute': {'id': ptal.attribute_id.id, 'name': ptal.attribute_id.name},
            'display_type': ptal.attribute_id.display_type,
            'create_variant': ptal.attribute_id.create_variant,
            'values': [
                {
                    'id': ptav.id,
                    'name': ptav.name,
                    'html_color': ptav.html_color or None,
                    'price_extra': amount(ptav.price_extra, currency),
                    'is_custom': ptav.is_custom,
                }
                for ptav in ptal.product_template_value_ids._only_active()
            ],
        }

    # === COMBINATION INFO === #

    @odusite_route(f'{API_PREFIX}/shop/products/<int:template_id>/combination',
                   methods=['POST'])
    def shop_product_combination(self, template_id, combination=None, quantity=1, **kwargs):
        peek_cart()
        template = self._get_published_template(template_id)

        try:
            ptav_ids = [int(value) for value in (combination or [])]
            add_qty = float(quantity or 1)
        except (TypeError, ValueError):
            raise ApiError(400, 'bad_request', 'Invalid combination payload.')

        ptavs_sudo = request.env['product.template.attribute.value'].sudo().browse(
            ptav_ids).exists()
        if ptavs_sudo.filtered(lambda ptav: ptav.product_tmpl_id.id != template.id):
            raise ApiError(400, 'bad_request',
                           'The combination does not belong to this product.')

        combination_info = template.with_context(
            **self._combination_context()
        )._get_combination_info(
            combination=request.env['product.template.attribute.value'].browse(
                ptavs_sudo.ids),
            add_qty=add_qty,
        )
        return serialize_combination_info(combination_info, template)
