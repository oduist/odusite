from odoo import models


class ForumPost(models.Model):
    _name = 'forum.post'
    _inherit = ['forum.post', 'odusite.watched.mixin']

    _odusite_tag = 'forum'
    _odusite_watch_fields = (
        'name', 'content', 'tag_ids', 'active', 'state', 'is_correct',
        'last_activity_date',
    )

    def _odusite_tags(self):
        # invalidate the forum the post belongs to (spec: forum, forum:<id>)
        self.ensure_one()
        return ['forum', f'forum:{self.forum_id.id}']
