from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import odusite_s3_client as s3


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- connection ---
    odusite_s3_enabled = fields.Boolean(
        string='Offload attachments to S3/R2',
        config_parameter='odusite.s3.enabled',
        help='Master switch. When off, Odoo uses its normal local filestore.')
    odusite_s3_endpoint_url = fields.Char(
        string='S3 Endpoint URL',
        config_parameter='odusite.s3.endpoint_url',
        help='S3-compatible endpoint, e.g. '
             'https://<account>.r2.cloudflarestorage.com. Leave empty for AWS S3. '
             'Overridden by odusite_s3_endpoint_url in odoo.conf / env.')
    odusite_s3_public_endpoint_url = fields.Char(
        string='Public S3 Endpoint URL',
        config_parameter='odusite.s3.public_endpoint_url',
        help='Endpoint used to sign presigned URLs when the browser-reachable '
             'host differs from the internal one (e.g. internal MinIO behind a '
             'public proxy). Empty = use the endpoint above.')
    odusite_s3_region = fields.Char(
        string='S3 Region',
        config_parameter='odusite.s3.region',
        help="Region (use 'auto' for Cloudflare R2).")
    odusite_s3_bucket = fields.Char(
        string='S3 Bucket', config_parameter='odusite.s3.bucket')
    odusite_s3_access_key = fields.Char(
        string='S3 Access Key', config_parameter='odusite.s3.access_key')
    odusite_s3_secret_key = fields.Char(
        string='S3 Secret Key', config_parameter='odusite.s3.secret_key')
    odusite_s3_public_base_url = fields.Char(
        string='Public Base URL',
        config_parameter='odusite.s3.public_base_url',
        help='Public CDN/R2 base URL for public objects, e.g. '
             'https://media.example.com. Empty => only the /img proxy and '
             'presigned URLs are used.')
    odusite_s3_url_expiry = fields.Integer(
        string='Presigned URL Expiry (s)',
        config_parameter='odusite.s3.url_expiry', default=900,
        help='Lifetime in seconds of presigned GET URLs.')

    # --- routing (what stays in Odoo) ---
    odusite_s3_keep_assets_local = fields.Boolean(
        string='Keep web assets (CSS/JS) in Odoo',
        config_parameter='odusite.s3.keep_assets_local', default=True,
        help='Serve web asset bundles (CSS / JavaScript) from Odoo instead of '
             'S3. Recommended — they are tiny and latency-sensitive.')
    odusite_s3_keep_images_below_kb = fields.Integer(
        string='Keep images smaller than (KB) in Odoo',
        config_parameter='odusite.s3.keep_images_below_kb', default=50,
        help='Images below this size stay in Odoo (avatars, thumbnails). '
             'Set to 0 to send all images to S3.')
    odusite_s3_keep_local_mimetypes = fields.Char(
        string='Also keep these MIME types in Odoo',
        config_parameter='odusite.s3.keep_local_mimetypes',
        help='Advanced: comma-separated MIME type prefixes to keep local, '
             'e.g. "application/xml, text/". Leave empty if unsure.')

    # --- direct download ---
    odusite_s3_direct_download = fields.Boolean(
        string='Direct download via presigned URL',
        config_parameter='odusite.s3.direct_download', default=True,
        help='Serve S3-backed originals by redirecting (302) to a short-lived '
             'presigned URL after access rights are checked, so the bytes are '
             'fetched straight from the object store instead of through Odoo. '
             'Resized image variants keep being served (and cached) by Odoo.')

    # --- migration ---
    odusite_s3_migrate_batch_size = fields.Integer(
        string='Migration batch size',
        config_parameter='odusite.s3.migrate_batch_size', default=100,
        help='Number of attachments scanned per batch during migration.')
    odusite_s3_migrate_workers = fields.Integer(
        string='Migration upload threads',
        config_parameter='odusite.s3.migrate_workers', default=8,
        help='Parallel upload threads for migration. These only do network I/O '
             '(no database connection), so the count is independent of '
             'db_maxconn. Higher = faster backfill, bounded by S3 latency.')
    odusite_s3_migrate_window_start = fields.Integer(
        string='Run from (hour)',
        config_parameter='odusite.s3.migrate_window_start', default=0,
        help='Migration only runs at or after this hour. Leave start = end to '
             'allow migration at any time.')
    odusite_s3_migrate_window_end = fields.Integer(
        string='Run until (hour)',
        config_parameter='odusite.s3.migrate_window_end', default=0,
        help='Migration stops when this hour is reached (and resumes next day). '
             'Supports overnight windows, e.g. 22 -> 6.')
    odusite_s3_migrate_window_tz = fields.Char(
        string='Window timezone',
        config_parameter='odusite.s3.migrate_window_tz',
        help='Timezone for the migration window hours (e.g. Europe/Warsaw). '
             'Empty = the current user timezone, then UTC.')

    # --- read-only diagnostics / progress ---
    odusite_s3_status = fields.Char(
        string='Connection status', compute='_compute_odusite_s3_status')
    odusite_s3_migrated_count = fields.Integer(
        string='Attachments on S3', compute='_compute_odusite_s3_progress')
    odusite_s3_local_count = fields.Integer(
        string='Local attachments pending', compute='_compute_odusite_s3_progress')
    odusite_s3_migration_running = fields.Boolean(
        string='Migration running', compute='_compute_odusite_s3_progress')

    @api.depends('odusite_s3_enabled')
    def _compute_odusite_s3_status(self):
        for rec in self:
            rec.odusite_s3_status = rec._odusite_s3_check_status()

    @api.depends('odusite_s3_enabled')
    def _compute_odusite_s3_progress(self):
        Att = self.env['ir.attachment']
        migrated = Att._odusite_s3_migrated_count()
        local = Att._odusite_s3_local_pending_count()
        running = Att._odusite_s3_migrate_is_running()
        for rec in self:
            rec.odusite_s3_migrated_count = migrated
            rec.odusite_s3_local_count = local
            rec.odusite_s3_migration_running = running

    def _odusite_s3_check_status(self):
        cfg = s3.read_config(self.env)
        if not s3.has_boto3():
            return _('boto3 is not installed on the Odoo server')
        if not s3.is_configured(cfg):
            return _('Not configured (set bucket + access/secret keys)')
        try:
            s3.get_client(self.env, cfg=cfg).head_bucket(Bucket=cfg['bucket'])
            return _('Connected — bucket "%s" reachable') % cfg['bucket']
        except Exception as exc:  # noqa: BLE001 - surface any connection error
            return _('Error reaching bucket "%s": %s') % (cfg['bucket'], exc)

    # --- actions ---
    def action_odusite_s3_test_connection(self):
        """Validate the entered credentials by writing/reading/deleting a probe."""
        self.ensure_one()
        bucket = (self.odusite_s3_bucket or '').strip()
        if not bucket:
            raise UserError(_("Set the bucket name before testing the connection."))
        client = s3.make_client(
            self.odusite_s3_endpoint_url, self.odusite_s3_region,
            self.odusite_s3_access_key, self.odusite_s3_secret_key)
        key = 'odusite/.connection-probe'
        try:
            client.put_object(Bucket=bucket, Key=key, Body=b'odusite probe')
            client.get_object(Bucket=bucket, Key=key)
            client.delete_object(Bucket=bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 - surface any boto3/botocore error
            raise UserError(_("S3 connection test failed: %s", exc))
        return self._odusite_s3_notify(
            _("Object Storage"),
            _("Connection successful: wrote and deleted a probe object."))

    def action_odusite_s3_migrate_start(self):
        self.ensure_one()
        self.env['ir.attachment']._odusite_s3_migrate_set_running(True)
        return self._odusite_s3_notify(
            _('Migration started'),
            _('Attachments are being moved to S3 in the background. Reopen '
              'Settings to watch the progress; press Stop to halt.'))

    def action_odusite_s3_migrate_stop(self):
        self.ensure_one()
        self.env['ir.attachment']._odusite_s3_migrate_set_running(False)
        return self._odusite_s3_notify(
            _('Migration stopping'),
            _('Migration will halt after the current batch.'))

    def action_odusite_s3_refresh(self):
        # reopen the settings so the progress counters are recomputed
        self.ensure_one()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _odusite_s3_notify(self, title, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': title,
                'message': message,
                'sticky': False,
            },
        }
