from odoo import models

from . import odusite_s3_client as s3


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _odusite_public_asset_url(self, record, field):
        """Direct public URL of a binary field's *original* on S3/R2.

        Returns the ``public_base_url/<store_fname>`` of the underlying
        ir.attachment when it is a public, S3-offloaded object and a public base
        URL is configured; otherwise ``None`` (site falls back to the /img
        proxy). Sized variants always keep using the proxy.
        """
        if not record:
            return None
        cfg = s3.read_config(self.env)
        if not cfg['public_base_url']:
            return None
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', record._name),
            ('res_id', '=', record.id),
            ('res_field', '=', field),
        ], limit=1)
        if not attachment or not attachment.store_fname:
            return None
        if not attachment.public or attachment._storage() != 'odusite_s3':
            return None
        return '%s/%s' % (cfg['public_base_url'], attachment.store_fname)
