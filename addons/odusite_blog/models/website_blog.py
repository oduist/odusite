from odoo import models


class BlogPost(models.Model):
    _name = 'blog.post'
    _inherit = ['blog.post', 'odusite.watched.mixin']
    _odusite_tag = 'blog'
    _odusite_watch_fields = (
        'name', 'subtitle', 'content', 'teaser_manual', 'tag_ids',
        'post_date', 'published_date', 'author_id', 'cover_properties', 'blog_id',
    )


class BlogTag(models.Model):
    _name = 'blog.tag'
    _inherit = ['blog.tag', 'odusite.watched.mixin']
    _odusite_tag = 'blog'

    def _odusite_tags(self):
        # Tag changes invalidate the blog collection, not a single post.
        self.ensure_one()
        return ['blog']
