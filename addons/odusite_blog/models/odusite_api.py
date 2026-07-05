from odoo import fields, models
from odoo.fields import Domain


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _sitemap_entries(self, website):
        entries = super()._sitemap_entries(website)
        posts = self.env['blog.post'].sudo().search(Domain.AND([
            website.website_domain(),
            [('is_published', '=', True), ('post_date', '<=', fields.Datetime.now())],
        ]))
        slug = self.env['ir.http']._slug
        entries.extend(
            {'url': f'/blog/{slug(post)}', 'lastmod': post.write_date}
            for post in posts
        )
        return entries

    def _chatter_models(self):
        return super()._chatter_models() | {'blog.post'}
