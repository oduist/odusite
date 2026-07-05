from odoo import models


class EventTag(models.Model):
    _name = 'event.tag'
    _inherit = ['event.tag', 'odusite.watched.mixin']

    _odusite_tag = 'events'
    _odusite_watch_fields = ('name', 'category_id', 'color')

    def _odusite_tags(self):
        # tag changes invalidate event listings, not a specific event page
        self.ensure_one()
        return ['events']
