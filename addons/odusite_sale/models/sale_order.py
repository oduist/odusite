from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Let portal customers post chatter comments on their own orders through
    # the odusite chatter API. Upstream sale.order requires 'write' to post
    # (no _mail_post_access), unlike account.move or project.task which allow
    # posting with read access; the stock portal works around it with the
    # record access_token. Aligning with those models is the smallest fix.
    _mail_post_access = 'read'
