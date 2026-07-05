from odoo import models


class SlideChannel(models.Model):
    _name = 'slide.channel'
    _inherit = ['slide.channel', 'odusite.watched.mixin']

    _odusite_tag = 'courses'
    _odusite_watch_fields = (
        'name', 'description', 'description_short', 'description_html',
        'tag_ids', 'channel_type', 'visibility', 'enroll',
        'prerequisite_channel_ids', 'active',
    )
