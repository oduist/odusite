from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    odusite_token = fields.Char(
        string='Odusite API Token',
        config_parameter='odusite.token',
        help='Shared secret the Astro site sends in the X-Odusite-Token header.',
    )
    odusite_site_url = fields.Char(
        string='Odusite Site URL',
        config_parameter='odusite.site_url',
        help='Public base URL of the Astro site (used in emails and webhooks).',
    )
    odusite_revalidate_secret = fields.Char(
        string='Odusite Revalidate Secret',
        config_parameter='odusite.revalidate_secret',
        help='HMAC secret for cache-invalidation webhooks sent to the site.',
    )
    odusite_website_id = fields.Many2one(
        'website',
        string='Odusite Website',
        config_parameter='odusite.website_id',
        help='Odoo website whose context (languages, pricelists, published '
             'records) the API exposes.',
    )
