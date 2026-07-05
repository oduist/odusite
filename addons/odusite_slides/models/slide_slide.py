from odoo import models


class SlideSlide(models.Model):
    _name = 'slide.slide'
    _inherit = ['slide.slide', 'odusite.watched.mixin']

    _odusite_tag = 'courses'
    _odusite_watch_fields = (
        'name', 'description', 'html_content', 'url', 'binary_content',
        'sequence', 'is_preview', 'category_id', 'completion_time',
        'slide_category', 'active',
    )

    def _odusite_tags(self):
        # slide changes invalidate the course page (spec: courses:<channel_id>)
        self.ensure_one()
        return ['courses', f'courses:{self.channel_id.id}']
