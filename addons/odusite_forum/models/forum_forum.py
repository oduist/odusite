from odoo import models


class ForumForum(models.Model):
    _name = 'forum.forum'
    _inherit = ['forum.forum', 'odusite.watched.mixin']

    _odusite_tag = 'forum'
    _odusite_watch_fields = ('name', 'description', 'mode', 'privacy', 'active')
