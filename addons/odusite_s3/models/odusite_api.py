from odoo import models

from . import odusite_s3_client as s3


class OdusiteApi(models.AbstractModel):
    _inherit = 'odusite.api'

    def _odusite_public_asset_url(self, record, field):
        """Direct public URL of a binary field's *original* on S3/R2.

        Returns the public URL of the underlying ir.attachment when it is a
        public, S3-offloaded object; otherwise ``None`` (the site falls back to
        the ``/img`` proxy). The object key is derived from the ``s3://``
        ``store_fname``. The public base is, in order of preference:

        * ``public_base_url`` (a CDN / custom domain serving objects directly), or
        * ``public_endpoint_url`` + ``/<bucket>`` (path-style S3 endpoint).

        Sized variants always keep using the proxy (handled by the serializer).
        """
        if not record:
            return None
        cfg = s3.read_config(self.env)
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', record._name),
            ('res_id', '=', record.id),
            ('res_field', '=', field),
        ], limit=1)
        if not attachment or not attachment.public:
            return None
        store_fname = attachment.store_fname or ''
        if not store_fname.startswith(attachment._S3_PREFIX):
            return None
        key = attachment._odusite_s3_object_key(store_fname)
        if cfg['public_base_url']:
            return '%s/%s' % (cfg['public_base_url'], key)
        if cfg['public_endpoint_url'] and cfg['bucket']:
            return '%s/%s/%s' % (cfg['public_endpoint_url'], cfg['bucket'], key)
        return None
