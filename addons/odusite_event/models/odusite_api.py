from odoo import models


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _sitemap_entries(self, website):
        entries = super()._sitemap_entries(website)
        slug = self.env['ir.http']._slug
        events = self.env['event.event'].search(
            website.website_domain()
            + [('is_published', '=', True), ('website_visibility', '=', 'public')]
        )
        entries.extend({
            'url': f'/events/{slug(event)}',
            'lastmod': event.write_date,
        } for event in events)
        return entries
