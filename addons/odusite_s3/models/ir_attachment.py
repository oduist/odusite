"""Offload the ir.attachment filestore to S3-compatible object storage.

Design (see specs/modules/odusite_s3.md):

Odoo routes binary storage through the ``_storage`` / ``_file_read`` /
``_file_write`` / ``_file_delete`` hooks. Returning a custom ``_storage()``
string plus overriding the three ``_file_*`` methods redirects read/write/delete
to any backend. We keep the exact sha1-based ``store_fname`` scheme
(``xx/xxxxxx...`` from ``ir.attachment._get_path``) as the S3 object key, so
dedup by checksum is preserved for free.

Odoo 19 signatures (odoo/addons/base/models/ir_attachment.py):
    _storage(self)                       @api.model  L88
    _file_read(self, fname, size=None)   @api.model  L147
    _file_write(self, bin_value, checksum) @api.model L158
    _file_delete(self, fname)            @api.model  L173   (singular fname!)
    _get_path(self, bin_data, sha)       @api.model  L132
    _to_http_stream(self)                            L904

Routing subtlety: ``_file_write`` is called with an *empty* recordset during
``create`` (model-level), so it cannot inspect the record being written. To keep
backend web-asset bundles on the local filestore (fast admin UI) we build a
per-checksum route map in ``create`` from the raw ``vals`` (assets are never
image-resized, so their checksum is stable). The read/serve paths always run on
a singleton, so they evaluate the offload policy per record.
"""

import base64
import binascii
import hashlib
import logging
import os

import psycopg2

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.http import Stream

from . import odusite_s3_client as s3

_logger = logging.getLogger(__name__)

STORAGE = 'odusite_s3'
ASSET_MIMETYPES = ('text/css', 'application/javascript', 'text/scss')


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    # -- configuration helpers ------------------------------------------

    @api.model
    def _odusite_s3_enabled(self):
        return s3.read_config(self.env)['enabled']

    @api.model
    def _odusite_s3_configured(self):
        cfg = s3.read_config(self.env)
        return bool(cfg['bucket'] and cfg['access_key'] and cfg['secret_key'])

    # -- offload policy (overridable) -----------------------------------

    def _odusite_s3_offloadable(self):
        """Whether these attachments belong on S3.

        Offload everything *except* backend web assets and generated bundles.
        An empty recordset defaults to ``True`` so batched write paths route
        content to S3; per-record read/serve paths get an exact answer.
        Override to change the policy.
        """
        for att in self:
            if att.res_model == 'ir.ui.view':
                return False
            if (att.name or '').startswith('/web/assets'):
                return False
            if att.mimetype in ASSET_MIMETYPES:
                return False
            if (att.url or '').startswith('/web/assets'):
                return False
        return True

    @api.model
    def _odusite_s3_offloadable_vals(self, vals):
        """Same policy as :meth:`_odusite_s3_offloadable`, evaluated on a raw
        ``create`` values dict (used to build the write route map)."""
        if vals.get('res_model') == 'ir.ui.view':
            return False
        if (vals.get('name') or '').startswith('/web/assets'):
            return False
        if (vals.get('url') or '').startswith('/web/assets'):
            return False
        if vals.get('mimetype') in ASSET_MIMETYPES:
            return False
        return True

    # -- storage routing -------------------------------------------------

    @api.model
    def _storage(self):
        base = super()._storage()
        if base != 'db' and self._odusite_s3_enabled() and self._odusite_s3_offloadable():
            return STORAGE
        return base

    @api.model
    def _get_storage_domain(self):
        # avoid a KeyError in the stock force_storage() lookup when S3 is active
        if self._storage() == STORAGE:
            return [('store_fname', '!=', False)]
        return super()._get_storage_domain()

    @api.model
    def _odusite_s3_key(self, checksum):
        # identical scheme to ir.attachment._get_path: 'xx/xxxxxx...'
        return checksum[:2] + '/' + checksum

    # -- file backend ----------------------------------------------------

    @api.model
    def _file_read(self, fname, size=None):
        if self._odusite_s3_enabled() and self._storage() == STORAGE:
            data = s3.get_object(self.env, fname)
            if data is not None:
                return data if size is None else data[:size]
            # bytes not on S3 yet (created before enabling / not migrated)
            return super()._file_read(fname, size=size)
        # local-first; fall back to S3 when the local copy is gone (e.g. the
        # master switch was turned off after a migration) -> reversibility.
        data = super()._file_read(fname, size=size)
        if not data and self._odusite_s3_configured():
            remote = s3.get_object(self.env, fname)
            if remote is not None:
                return remote if size is None else remote[:size]
        return data

    @api.model
    def _file_write(self, bin_value, checksum):
        if self._odusite_s3_enabled() and self._odusite_s3_should_offload_write(checksum):
            key = self._odusite_s3_key(checksum)
            if not s3.head_object(self.env, key):  # dedup: skip existing object
                s3.put_object(self.env, key, bin_value)
            return key
        return super()._file_write(bin_value, checksum)

    @api.model
    def _odusite_s3_should_offload_write(self, checksum):
        route = self.env.context.get('odusite_s3_route')
        if route and checksum in route:
            return route[checksum]
        # unknown checksum (image resized after route map built, or the write
        # path where self is the real recordset) -> per-record policy.
        return self._odusite_s3_offloadable()

    @api.model
    def _file_delete(self, fname):
        # keep stock local GC bookkeeping (local assets, legacy/pre-migration files)
        super()._file_delete(fname)
        # drop the S3 object once no attachment references the key (dedup-safe gc)
        if self._odusite_s3_configured() and not self._odusite_s3_fname_in_use(fname):
            try:
                s3.delete_object(self.env, fname)
            except Exception:  # noqa: BLE001 - never break unlink on a gc error
                _logger.warning("odusite_s3: could not delete object %s", fname,
                                exc_info=True)

    @api.model
    def _odusite_s3_fname_in_use(self, fname):
        # count all attachments (incl. res_field ones) still pointing at the key
        return bool(self.sudo().search_count([
            ('store_fname', '=', fname),
            '|', ('res_field', '=', False), ('res_field', '!=', False),
        ]))

    # -- create: build the per-checksum write route ----------------------

    @api.model_create_multi
    def create(self, vals_list):
        target = self
        if self._odusite_s3_enabled():
            route = self._odusite_s3_build_route(vals_list)
            if route:
                target = self.with_context(odusite_s3_route=route)
        return super(IrAttachment, target).create(vals_list)

    @api.model
    def _odusite_s3_build_route(self, vals_list):
        route = {}
        for vals in vals_list:
            raw = self._odusite_s3_vals_raw(vals)
            if not raw:
                continue
            checksum = hashlib.sha1(raw).hexdigest()
            route[checksum] = self._odusite_s3_offloadable_vals(vals)
        return route

    @api.model
    def _odusite_s3_vals_raw(self, vals):
        raw = vals.get('raw')
        if raw is not None:
            return raw.encode() if isinstance(raw, str) else raw
        datas = vals.get('datas')
        if datas:
            try:
                return base64.b64decode(datas)
            except (binascii.Error, ValueError):
                return None
        return None

    # -- serving (S3 objects have no local file) -------------------------

    def _to_http_stream(self):
        self.ensure_one()
        if (self.type == 'binary' and self.store_fname
                and self._odusite_s3_enabled() and self._storage() == STORAGE):
            # stock would build a local filestore path that does not exist;
            # stream the bytes as data (self.raw reads from S3 via _file_read).
            data = self.raw or b''
            return Stream(
                type='data',
                data=data,
                mimetype=self.mimetype,
                download_name=self.name,
                etag=self.checksum,
                public=self.public,
                last_modified=self.write_date,
                size=len(data),
            )
        return super()._to_http_stream()

    # -- presigned URLs (private documents) ------------------------------

    def _odusite_presigned_url(self, expiry=None):
        """Time-limited signed GET URL for an S3-stored attachment.

        Raises ``UserError`` for attachments that are not offloaded to S3.
        """
        self.ensure_one()
        if not (self._odusite_s3_configured() and self.store_fname
                and self._storage() == STORAGE):
            raise UserError(_(
                "Attachment %s is not stored on S3; cannot build a presigned URL.",
                self.display_name))
        cfg = s3.read_config(self.env)
        return s3.presigned_get(self.env, self.store_fname, expiry or cfg['url_expiry'])

    # -- garbage collection ----------------------------------------------

    @api.autovacuum
    def _gc_file_store(self):
        if not self._odusite_s3_enabled():
            return super()._gc_file_store()
        # When S3 is the active storage, stock _gc_file_store() early-returns
        # (storage != 'file') and never reclaims local files. Run the local GC
        # ourselves so leftover asset bundles are cleaned. S3 objects are
        # reclaimed eagerly in _file_delete.
        cr = self.env.cr
        cr.commit()
        cr.execute("SET LOCAL lock_timeout TO '10s'")
        try:
            cr.execute("LOCK ir_attachment IN SHARE MODE")
        except psycopg2.errors.LockNotAvailable:
            cr.rollback()
            return False
        self._gc_file_store_unsafe()
        cr.commit()

    # -- migration of the existing filestore -----------------------------

    @api.model
    def _odusite_s3_migrate_batch(self, limit=200):
        """Upload one batch of offloadable local attachments to S3.

        Idempotent and batched: a config-param cursor guarantees forward
        progress across cron runs; already-uploaded objects are skipped via a
        HEAD. Returns the number of attachments processed (0 once drained).
        """
        if not self._odusite_s3_enabled():
            return 0
        icp = self.env['ir.config_parameter'].sudo()
        cursor = int(icp.get_param('odusite.s3.migrate_cursor') or 0)
        attachments = self.sudo().search([
            ('id', '>', cursor),
            ('type', '=', 'binary'),
            ('store_fname', '!=', False),
            '|', ('res_field', '=', False), ('res_field', '!=', False),
        ], limit=limit, order='id asc')
        if not attachments:
            icp.set_param('odusite.s3.migrate_cursor', '0')  # drained: rewind
            return 0
        uploaded = 0
        for att in attachments:
            try:
                if att._odusite_s3_migrate_one():
                    uploaded += 1
            except Exception:  # noqa: BLE001
                _logger.warning("odusite_s3: migration failed for attachment %s",
                                att.id, exc_info=True)
        icp.set_param('odusite.s3.migrate_cursor', str(attachments[-1].id))
        _logger.info("odusite_s3: migration batch of %s (up to id %s), %s uploaded",
                     len(attachments), attachments[-1].id, uploaded)
        return len(attachments)

    @api.model
    def _odusite_s3_migrate_all(self):
        """Migrate the whole filestore in one transaction (server action)."""
        total = 0
        while True:
            processed = self._odusite_s3_migrate_batch()
            if not processed:
                break
            total += processed
        return total

    def _odusite_s3_migrate_one(self):
        self.ensure_one()
        if not self._odusite_s3_offloadable() or not self.store_fname:
            return False
        fname = self.store_fname
        if s3.head_object(self.env, fname):
            self._odusite_s3_drop_local(fname)  # already on S3, reclaim local
            return False
        data = self.raw  # S3 miss -> local fallback in _file_read
        if not data:
            return False
        s3.put_object(self.env, fname, data)
        self._odusite_s3_drop_local(fname)
        return True

    def _odusite_s3_drop_local(self, fname):
        # offloaded content keys never collide with local-only asset keys
        # (different content -> different sha1), so removing the local file is safe.
        full_path = self._full_path(fname)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
        except OSError:
            _logger.warning("odusite_s3: could not remove local file %s", full_path,
                            exc_info=True)
