from odoo import models
from odoo.fields import Domain


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _sitemap_entries(self, website):
        entries = super()._sitemap_entries(website)
        slug = self.env['ir.http']._slug

        ProductTemplate = self.env['product.template'].sudo()
        product_domain = Domain.AND([
            [('sale_ok', '=', True), ('is_published', '=', True)],
            [('service_tracking', 'in', ProductTemplate._get_saleable_tracking_types())],
            website.website_domain(),
        ])
        for template in ProductTemplate.with_context(prefetch_fields=False).search(product_domain):
            entries.append({'url': f'/shop/{slug(template)}', 'lastmod': template.write_date})

        category_domain = Domain.AND([
            website.website_domain(),
            [('has_published_products', '=', True)],
        ])
        for category in self.env['product.public.category'].sudo().search(category_domain):
            entries.append({'url': f'/shop/{slug(category)}', 'lastmod': category.write_date})

        return entries

    def _portal_counters(self, counters):
        values = super()._portal_counters(counters)
        requested = {'orders', 'quotes'} & set(counters)
        if not requested:
            return values

        SaleOrder = self.env['sale.order']
        if not SaleOrder.has_access('read'):
            values.update(dict.fromkeys(requested, 0))
            return values

        # Mirrors sale/controllers/portal.py _prepare_quotations_domain /
        # _prepare_orders_domain.
        commercial_partner = self.env.user.partner_id.commercial_partner_id
        if 'quotes' in requested:
            values['quotes'] = SaleOrder.search_count([
                ('partner_id', 'child_of', [commercial_partner.id]),
                ('state', '=', 'sent'),
            ])
        if 'orders' in requested:
            values['orders'] = SaleOrder.search_count([
                ('partner_id', 'child_of', [commercial_partner.id]),
                ('state', '=', 'sale'),
            ])
        return values

    def _chatter_models(self):
        return super()._chatter_models() | {'sale.order'}
