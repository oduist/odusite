from odoo import models
from odoo.fields import Domain


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _sitemap_entries(self, website):
        entries = super()._sitemap_entries(website)
        jobs = self.env['hr.job'].sudo().search(Domain.AND([
            website.website_domain(),
            [('is_published', '=', True)],
        ]))
        slug = self.env['ir.http']._slug
        entries.extend(
            {'url': f'/jobs/{slug(job)}', 'lastmod': job.write_date}
            for job in jobs
        )
        return entries
