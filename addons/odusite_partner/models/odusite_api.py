from odoo import models
from odoo.fields import Domain


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _sitemap_entries(self, website):
        entries = super()._sitemap_entries(website)
        partners = self.env['res.partner'].sudo().search(Domain.AND([
            website.website_domain(),
            [('is_published', '=', True)],
        ]))
        slug = self.env['ir.http']._slug
        entries.extend(
            {'url': f'/partners/{slug(partner)}', 'lastmod': partner.write_date}
            for partner in partners
        )
        return entries
