from odoo import _, fields, models
from odoo.exceptions import UserError

from . import odusite_s3_client as s3


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    odusite_s3_enabled = fields.Boolean(
        string='Offload attachments to S3/R2',
        config_parameter='odusite.s3.enabled',
        help='Master switch. When off, Odoo uses its normal local filestore.',
    )
    odusite_s3_endpoint_url = fields.Char(
        string='S3 Endpoint URL',
        config_parameter='odusite.s3.endpoint_url',
        help='S3-compatible endpoint, e.g. '
             'https://<account>.r2.cloudflarestorage.com. Leave empty for AWS S3.',
    )
    odusite_s3_region = fields.Char(
        string='S3 Region',
        config_parameter='odusite.s3.region',
        help="Region (use 'auto' for Cloudflare R2).",
    )
    odusite_s3_bucket = fields.Char(
        string='S3 Bucket',
        config_parameter='odusite.s3.bucket',
    )
    odusite_s3_access_key = fields.Char(
        string='S3 Access Key',
        config_parameter='odusite.s3.access_key',
    )
    odusite_s3_secret_key = fields.Char(
        string='S3 Secret Key',
        config_parameter='odusite.s3.secret_key',
    )
    odusite_s3_public_base_url = fields.Char(
        string='Public Base URL',
        config_parameter='odusite.s3.public_base_url',
        help='Public CDN/R2 base URL for public objects, e.g. '
             'https://media.example.com. Empty => only the /img proxy and '
             'presigned URLs are used.',
    )
    odusite_s3_url_expiry = fields.Integer(
        string='Presigned URL Expiry (s)',
        config_parameter='odusite.s3.url_expiry',
        default=900,
        help='Lifetime in seconds of presigned GET URLs for private documents.',
    )

    def action_odusite_s3_test_connection(self):
        """Validate the currently entered credentials by writing and deleting a
        probe object. Raises UserError on failure, notifies on success."""
        self.ensure_one()
        bucket = (self.odusite_s3_bucket or '').strip()
        if not bucket:
            raise UserError(_("Set the bucket name before testing the connection."))
        client = s3.make_client(
            self.odusite_s3_endpoint_url,
            self.odusite_s3_region,
            self.odusite_s3_access_key,
            self.odusite_s3_secret_key,
        )
        key = 'odusite/.connection-probe'
        try:
            client.put_object(Bucket=bucket, Key=key, Body=b'odusite probe')
            client.get_object(Bucket=bucket, Key=key)
            client.delete_object(Bucket=bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 - surface any boto3/botocore error
            raise UserError(_("S3 connection test failed: %s", exc))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _("Object Storage"),
                'message': _("Connection successful: wrote and deleted a probe object."),
                'sticky': False,
            },
        }
