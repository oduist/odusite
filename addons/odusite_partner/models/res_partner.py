from odoo import models


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'odusite.watched.mixin']
    _odusite_tag = 'partners'
    # Partner writes are frequent: only website-facing fields are watched
    # (is_published is always watched by the mixin, and unpublished partners
    # never emit update events). grade_id / website_tag_ids only exist when
    # the optional modules are installed; extra names in vals are harmless.
    _odusite_watch_fields = (
        'name', 'website_description', 'website_short_description',
        'website_tag_ids', 'grade_id', 'assigned_partner_id',
        'city', 'country_id', 'industry_id', 'website', 'image_1920',
    )
