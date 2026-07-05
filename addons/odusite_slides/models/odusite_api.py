from odoo import models


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _sitemap_entries(self, website):
        entries = super()._sitemap_entries(website)
        slug = self.env['ir.http']._slug
        channels = self.env['slide.channel'].search(
            website.website_domain()
            + [('is_published', '=', True), ('visibility', '=', 'public')]
        )
        entries.extend({
            'url': f'/courses/{slug(channel)}',
            'lastmod': channel.write_date,
        } for channel in channels)
        return entries
