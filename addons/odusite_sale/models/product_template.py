from odoo import models


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'odusite.watched.mixin']

    _odusite_tag = 'shop'
    _odusite_watch_fields = (
        'name',
        'list_price',
        'compare_list_price',
        'description_sale',
        'website_description',
        'description_ecommerce',
        'website_sequence',
        'website_ribbon_id',
        'image_1920',
        'product_template_image_ids',
        'public_categ_ids',
        'product_tag_ids',
        'alternative_product_ids',
        'accessory_product_ids',
        'attribute_line_ids',
        'sale_ok',
        'active',
    )
