from odoo import models


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _sitemap_entries(self, website):
        entries = super()._sitemap_entries(website)
        slug = self.env['ir.http']._slug
        # same domain as the upstream sitemap_forum_post
        posts = self.env['forum.post'].search(
            website.website_domain()
            + [('parent_id', '=', False), ('can_view', '=', True)]
        )
        entries.extend({
            'url': f'/forum/{slug(post.forum_id)}/{slug(post)}',
            'lastmod': post.write_date,
        } for post in posts)
        return entries
