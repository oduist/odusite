from odoo import models


class ProductPublicCategory(models.Model):
    _name = 'product.public.category'
    _inherit = ['product.public.category', 'odusite.watched.mixin']

    _odusite_tag = 'shop-cat'
    _odusite_watch_fields = (
        'name',
        'parent_id',
        'sequence',
        'image_1920',
        'cover_image',
        'website_description',
        'website_id',
    )
