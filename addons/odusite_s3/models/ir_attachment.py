"""Offload the ir.attachment filestore to S3-compatible object storage.

Design (see specs/modules/odusite_s3.md, ADR-008, ADR-012). The technique is
ported from an internal production reference module and adapted to Odoo 19.0.

Storage marker
--------------
An S3-backed file is recorded as an ``s3://<sha[:2]>/<sha>`` prefix in
``store_fname`` (same content-addressed scatter as the native filestore, so
dedup is preserved). Reads/deletes route on this prefix, so local and S3 files
coexist per record and the local filestore stays a free fallback during a
migration. No ``_storage()`` override is needed — the effective storage stays
``'file'``, so the stock local GC (``_gc_file_store``) keeps reclaiming local
files while our own autovacuum reclaims S3 objects.

Odoo 19 vs the 15.0 reference
-----------------------------
In Odoo <= 15 ``_get_datas_related_values`` set ``store_fname`` from the return
of ``_file_write``; the reference simply flips a context flag there and lets
``_file_write`` return the ``s3://`` marker. Odoo 19 refactored this: create()
and _set_attachment_data() now (a) get ``store_fname`` from ``_get_path`` inside
``_get_datas_related_values`` and (b) call ``_file_write`` separately, discarding
its return value (base ir_attachment.py L770/L788 and L294/L312). We therefore
re-establish the old contract explicitly: our ``_get_datas_related_values``
performs the S3 upload and owns the ``s3://`` ``store_fname``; the second,
unflagged ``_file_write`` that Odoo issues afterwards is short-circuited (it
finds the object already on S3 and skips writing a redundant local copy).
"""

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor

import psycopg2
import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import split_every, str2bool

from . import odusite_s3_client as s3

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    # Marker stored at the front of ``store_fname`` for S3-backed files.
    _S3_PREFIX = 's3://'
    # Web-asset mimetypes kept in Odoo when "keep assets local" is on.
    _S3_ASSET_MIMETYPES = (
        'text/css', 'application/javascript', 'text/javascript', 'text/scss')

    # ------------------------------------------------------------------
    # configuration helpers
    # ------------------------------------------------------------------
    def _odusite_s3_config(self):
        return s3.read_config(self.env)

    def _odusite_s3_active(self, cfg=None):
        cfg = cfg or self._odusite_s3_config()
        return bool(cfg['enabled']) and s3.is_configured(cfg)

    def _odusite_s3_configured(self, cfg=None):
        return s3.is_configured(cfg or self._odusite_s3_config())

    def _odusite_s3_should_offload(self, mimetype, size):
        """Decide whether content of this mimetype/size goes to S3.

        Everything is offloaded except, per the (friendly) settings: web assets
        (CSS/JS), images below a size threshold, and any extra mimetype prefixes
        the admin chose to keep local. Overridable.
        """
        if not self._odusite_s3_active():
            return False
        if not mimetype:
            return True
        ICP = self.env['ir.config_parameter'].sudo()
        # 1) web assets (CSS/JS) -> served by Odoo (fast admin UI)
        if str2bool(ICP.get_param('odusite.s3.keep_assets_local', 'True'), True):
            if mimetype in self._S3_ASSET_MIMETYPES:
                return False
        # 2) small images -> kept local (avatars, thumbnails); 0 disables the rule
        img_kb = int(ICP.get_param('odusite.s3.keep_images_below_kb', 50) or 0)
        if img_kb and mimetype.startswith('image/') and size <= img_kb * 1024:
            return False
        # 3) advanced: extra comma-separated mimetype prefixes
        extra = ICP.get_param('odusite.s3.keep_local_mimetypes', '') or ''
        for prefix in (p.strip() for p in extra.split(',')):
            if prefix and mimetype.startswith(prefix):
                return False
        return True

    def _odusite_s3_direct_download_enabled(self):
        if not self._odusite_s3_configured():
            return False
        param = self.env['ir.config_parameter'].sudo().get_param(
            'odusite.s3.direct_download', 'True')
        return str2bool(param or 'False', False)

    def _odusite_s3_signed_ttl(self):
        cfg = self._odusite_s3_config()
        return cfg['url_expiry']

    # ------------------------------------------------------------------
    # key / marker helpers
    # ------------------------------------------------------------------
    def _odusite_s3_key(self, checksum):
        # content-addressed key, same scatter as the native filestore
        return checksum[:2] + '/' + checksum

    def _odusite_s3_is_s3(self, fname):
        return bool(fname) and fname.startswith(self._S3_PREFIX)

    def _odusite_s3_object_key(self, fname):
        return fname[len(self._S3_PREFIX):]

    # ------------------------------------------------------------------
    # routing decision (single point, has mimetype + size)
    # ------------------------------------------------------------------
    def _get_datas_related_values(self, data, mimetype):
        values = super()._get_datas_related_values(data, mimetype)
        if data and self._odusite_s3_should_offload(mimetype, len(data)):
            # Odoo 19 already set store_fname to a *local* scatter path via
            # _get_path() above and will discard _file_write()'s return, so we
            # own store_fname here: upload now and record the s3:// marker.
            values['store_fname'] = self.with_context(
                odusite_s3_offload=True, odusite_s3_mimetype=mimetype,
            )._file_write(data, values['checksum'])
            values['db_datas'] = False
        return values

    # ------------------------------------------------------------------
    # storage backend overrides (route on the s3:// prefix)
    # ------------------------------------------------------------------
    @api.model
    def _file_write(self, bin_value, checksum):
        cfg = self._odusite_s3_config()
        if self.env.context.get('odusite_s3_offload') and self._odusite_s3_active(cfg):
            key = self._odusite_s3_key(checksum)
            s3.upload_dedup(
                s3.get_client(self.env, cfg=cfg), s3.get_bucket(self.env, cfg),
                key, bin_value, self.env.context.get('odusite_s3_mimetype'))
            return self._S3_PREFIX + key
        # Unflagged second write issued by create()/_set_attachment_data(): if the
        # object was already offloaded in _get_datas_related_values, do not also
        # write a local copy — return the marker (dedup). Otherwise store locally.
        if self._odusite_s3_active(cfg):
            key = self._odusite_s3_key(checksum)
            if s3.head_object(self.env, key):
                return self._S3_PREFIX + key
        return super()._file_write(bin_value, checksum)

    @api.model
    def _file_read(self, fname, size=None):
        if self._odusite_s3_is_s3(fname):
            data = s3.get_object(self.env, self._odusite_s3_object_key(fname))
            if data is None:
                return b''
            return data if size is None else data[:size]
        return super()._file_read(fname, size=size)

    @api.model
    def _file_delete(self, fname):
        if self._odusite_s3_is_s3(fname):
            self._odusite_s3_mark_for_gc(fname)
        else:
            super()._file_delete(fname)

    def _odusite_s3_mark_for_gc(self, fname):
        """Queue an S3 object for deferred, reference-counted deletion.

        Written in a separate cursor so the deletion intent survives a rollback
        of the current transaction (object stores are not transactional with
        PostgreSQL). Mirrors the core filestore checklist, which is likewise
        written outside the transaction.
        """
        with self.env.registry.cursor() as new_cr:
            new_cr.execute(
                "INSERT INTO odusite_s3_gc (store_fname) VALUES (%s) "
                "ON CONFLICT (store_fname) DO NOTHING",
                (fname,),
            )
            new_cr.commit()

    # ------------------------------------------------------------------
    # serving: S3-backed originals have no local file
    # ------------------------------------------------------------------
    def _to_http_stream(self):
        self.ensure_one()
        if self.type == 'binary' and self._odusite_s3_is_s3(self.store_fname):
            # Stock would build a local filestore path that does not exist;
            # stream the bytes as data (self.raw reads from S3 via _file_read).
            from odoo.http import Stream
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

    # ------------------------------------------------------------------
    # presigned direct download
    # ------------------------------------------------------------------
    def _odusite_s3_presigned_url(self, download=False, filename=None, expiry=None):
        """Return a short-lived presigned GET URL, or ``False`` if not S3-backed."""
        self.ensure_one()
        if not self._odusite_s3_is_s3(self.store_fname):
            return False
        try:
            return s3.presigned_get(
                self.env, self._odusite_s3_object_key(self.store_fname),
                expiry=expiry or self._odusite_s3_signed_ttl(),
                download=download, filename=filename or self.name)
        except Exception:  # noqa: BLE001 - never break serving on a signing error
            _logger.info("odusite_s3: presigned URL failed for %s",
                         self.store_fname, exc_info=True)
            return False

    def _odusite_presigned_url(self, expiry=None):
        """Public helper (spec-facing): presigned GET URL for an S3 attachment.

        Raises ``UserError`` for attachments that are not offloaded to S3, so
        callers (odusite_account / odusite_sale PDF endpoints) can fall back to
        streaming the file when S3 is off.
        """
        self.ensure_one()
        url = self._odusite_s3_presigned_url(expiry=expiry)
        if not url:
            raise UserError(_(
                "Attachment %s is not stored on S3; cannot build a presigned URL.",
                self.display_name))
        return url

    # ------------------------------------------------------------------
    # migration of existing (local) attachments
    # ------------------------------------------------------------------
    def _odusite_s3_offload(self):
        """Relocate each eligible local attachment in ``self`` to S3."""
        moved = 0
        for attach in self:
            if attach._odusite_s3_offload_one():
                moved += 1
        return moved

    def _odusite_s3_offload_one(self):
        """Relocate ONE local attachment to S3 at the storage layer.

        Reads the local bytes, uploads them (dedup + ContentType via the flagged
        ``_file_write``), swaps ``store_fname`` with a direct SQL UPDATE and
        garbage-collects the old local file. Deliberately bypasses the
        ir.attachment ORM ``write`` chain, so the relocation does NOT trigger the
        business-logic write hooks of sibling modules — a pure storage move that
        keeps checksum/file_size/dedup intact. Returns True if the file moved.
        """
        self.ensure_one()
        old = self.store_fname
        if not old or self._odusite_s3_is_s3(old) or self.type != 'binary':
            return False
        if not self._odusite_s3_should_offload(self.mimetype, self.file_size):
            return False
        data = self.raw or b''
        # Guard against an unhealthy source filestore (e.g. a dead network mount
        # returning ENOTCONN): core ``_file_read`` swallows the error and returns
        # b'', which would otherwise store empty content and orphan the original.
        if self.file_size and len(data) != self.file_size:
            _logger.warning(
                "odusite_s3 migrate: skipping attachment %s, read %d/%d bytes "
                "(source filestore unreadable?)", self.id, len(data), self.file_size)
            return False
        checksum = self.checksum or self._compute_checksum(data)
        new_fname = self.with_context(
            odusite_s3_offload=True, odusite_s3_mimetype=self.mimetype,
        )._file_write(data, checksum)
        # swap the storage location without going through the ORM write hooks
        self.env.cr.execute(
            "UPDATE ir_attachment SET store_fname = %s WHERE id = %s",
            (new_fname, self.id))
        self.invalidate_recordset(['store_fname', 'raw', 'datas'])
        self._file_delete(old)   # GC the now-orphaned local file (ref-counted)
        return True

    @api.model
    def _odusite_s3_migrate_domain(self):
        # Local binary attachments not yet on S3. The explicit res_field terms
        # also suppress the automatic res_field=False filter added by
        # ir.attachment._search (same trick as core force_storage), so
        # binary-field attachments are included.
        return [
            ('type', '=', 'binary'),
            ('store_fname', '!=', False),
            ('store_fname', 'not like', 's3://%'),
            '|', ('res_field', '=', False), ('res_field', '!=', False),
        ]

    @api.model
    def _odusite_s3_local_pending_count(self):
        if not self._odusite_s3_configured():
            return 0
        return self.search_count(self._odusite_s3_migrate_domain())

    @api.model
    def _odusite_s3_migrated_count(self):
        return self.search_count([
            ('store_fname', '=like', 's3://%'),
            '|', ('res_field', '=', False), ('res_field', '!=', False),
        ])

    @api.model
    def _odusite_s3_migrate_is_running(self):
        # read the live (committed) value, bypassing the ORM cache
        self.env.cr.execute(
            "SELECT value FROM ir_config_parameter "
            "WHERE key = 'odusite.s3.migrate_active'")
        row = self.env.cr.fetchone()
        return bool(row) and row[0] in ('1', 'True', 'true')

    @api.model
    def _odusite_s3_migrate_in_window(self):
        """True if the current time is within the configured migration window.

        Hours are interpreted in ``odusite.s3.migrate_window_tz`` (falling back
        to the current user's timezone, then UTC). When start == end the window
        is disabled and migration may run at any time. Overnight windows
        (e.g. 22 -> 6) are supported.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        start = int(ICP.get_param('odusite.s3.migrate_window_start', 0) or 0)
        end = int(ICP.get_param('odusite.s3.migrate_window_end', 0) or 0)
        if start == end:
            return True
        tzname = ICP.get_param('odusite.s3.migrate_window_tz') or self.env.user.tz or 'UTC'
        try:
            tz = pytz.timezone(tzname)
        except Exception:  # noqa: BLE001 - bad tz name -> UTC
            tz = pytz.UTC
        hour = pytz.utc.localize(fields.Datetime.now()).astimezone(tz).hour
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    @api.model
    def _odusite_s3_migrate_set_flag(self, value):
        """Flip only the on/off parameter (never touches the cron row)."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('odusite.s3.migrate_active', '1' if value else '0')
        # keep _odusite_s3_migrate_is_running() (raw SQL) consistent
        self.env['ir.config_parameter'].flush_model(['value'])

    @api.model
    def _odusite_s3_migrate_set_running(self, running):
        if not self.env.is_admin():
            raise AccessError(_("Only administrators can manage S3 migration."))
        if running and not self._odusite_s3_active():
            raise UserError(_("S3 attachment storage is not enabled/configured."))
        self._odusite_s3_migrate_set_flag(running)
        cron = self.env.ref(
            'odusite_s3.ir_cron_odusite_s3_migrate', raise_if_not_found=False)
        if not cron:
            return
        # Writing the cron row would deadlock if a job is live, so guard it.
        # Start is only reachable when not running, so activation is safe; Stop
        # relies on the flag (checked between batches), the cron write is only a
        # best-effort tidy-up.
        if running:
            try:
                cron.sudo().write({'active': True, 'nextcall': fields.Datetime.now()})
                cron.sudo()._trigger()
            except Exception:  # noqa: BLE001
                pass
        else:
            try:
                cron.sudo().write({'active': False})
            except Exception:  # noqa: BLE001
                pass

    @api.model
    def _odusite_s3_migrate_workers(self):
        """Number of parallel upload threads for migration (capped 1..64)."""
        n = int(self.env['ir.config_parameter'].sudo().get_param(
            'odusite.s3.migrate_workers', 8) or 8)
        return max(1, min(n, 64))

    @api.model
    def _cron_odusite_s3_migrate(self):
        """Background migration worker: relocate eligible local attachments to S3.

        Gated by the ``odusite.s3.migrate_active`` flag (Start/Stop) and the
        configured time window. The slow, network-bound work (read the local
        file + head/put to S3) runs in a thread pool that does NOT touch the
        database, so the worker count is independent of ``db_maxconn``; all DB
        work (metadata read, ``store_fname`` swap, commit) stays single-threaded
        in this orchestrator. Re-checks the flag and window between batches and
        clears the flag once a full sweep finds nothing left to move. Never
        writes the cron record itself (that would deadlock on its own row lock).
        """
        if not self._odusite_s3_migrate_is_running():
            return
        if not self._odusite_s3_active():
            self._odusite_s3_migrate_set_flag(False)
            return
        if not self._odusite_s3_migrate_in_window():
            return  # outside the allowed window -> nothing to do this tick
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'odusite.s3.migrate_batch_size', 100) or 100)
        domain = self._odusite_s3_migrate_domain()
        cfg = self._odusite_s3_config()
        client = s3.get_client(self.env, cfg=cfg)
        bucket = s3.get_bucket(self.env, cfg)
        filestore = self._filestore()
        prefix = self._S3_PREFIX

        def _upload(item):
            # runs in a worker thread: local disk + S3 only, NO database cursor
            rid, fname, checksum, mimetype, file_size = item
            try:
                full = os.path.join(filestore, re.sub('[.:]', '', fname).strip('/\\'))
                with open(full, 'rb') as fh:
                    data = fh.read()
                if file_size and len(data) != file_size:
                    return (rid, None, 'unreadable')  # source filestore unhealthy
                if not checksum:
                    checksum = self._compute_checksum(data)
                key = checksum[:2] + '/' + checksum
                s3.upload_dedup(client, bucket, key, data, mimetype)
                return (rid, prefix + key, fname)
            except (IOError, OSError):
                return (rid, None, 'unreadable')
            except Exception as exc:  # noqa: BLE001 - network/S3 error -> retry
                return (rid, None, 'error:%s' % exc)

        cr = self.env.cr
        last_id = 0
        moved = 0
        skipped = 0
        with ThreadPoolExecutor(max_workers=self._odusite_s3_migrate_workers()) as pool:
            while True:
                if not self._odusite_s3_migrate_is_running():
                    _logger.info("odusite_s3 migration stopped (%d moved this run)", moved)
                    return
                if not self._odusite_s3_migrate_in_window():
                    _logger.info("odusite_s3 migration paused: outside allowed "
                                 "window (%d moved this run)", moved)
                    return
                batch = self.search(
                    domain + [('id', '>', last_id)], order='id', limit=batch_size)
                if not batch:
                    break
                last_id = batch[-1].id
                # one DB read for the batch; release the snapshot before uploading
                cr.execute(
                    "SELECT id, store_fname, checksum, mimetype, file_size "
                    "FROM ir_attachment WHERE id IN %s", (tuple(batch.ids),))
                rows = cr.fetchall()
                cr.commit()
                items = [
                    (rid, sf, checksum, mimetype, file_size)
                    for (rid, sf, checksum, mimetype, file_size) in rows
                    if sf and not sf.startswith(prefix)
                    and self._odusite_s3_should_offload(mimetype, file_size)
                ]
                if not items:
                    continue
                # parallel uploads (no DB), then apply the swaps single-threaded
                done_ids = []
                for rid, new_fname, info in pool.map(_upload, items):
                    if not new_fname:
                        if str(info).startswith('error:'):
                            skipped += 1  # transient (network/S3) -> retry next sweep
                            _logger.warning("odusite_s3 migrate: %s on attachment %s", info, rid)
                        else:
                            _logger.warning("odusite_s3 migrate: skipping attachment "
                                            "%s (source filestore unreadable?)", rid)
                        continue
                    try:
                        cr.execute("UPDATE ir_attachment SET store_fname = %s "
                                   "WHERE id = %s", (new_fname, rid))
                        cr.commit()
                    except psycopg2.OperationalError:
                        cr.rollback()
                        skipped += 1
                        _logger.warning("odusite_s3 migrate: deferring attachment %s "
                                        "(concurrent update)", rid)
                        continue
                    self._file_delete(info)  # info == old local fname -> GC mark
                    done_ids.append(rid)
                    moved += 1
                if done_ids:
                    self.browse(done_ids).invalidate_recordset(
                        ['store_fname', 'raw', 'datas'])
        if skipped:
            # records were deferred this sweep -> keep the flag on so the next
            # tick re-sweeps and retries them (do NOT declare completion).
            _logger.info("odusite_s3 migration sweep: %d moved, %d deferred "
                         "(retry next run)", moved, skipped)
            return
        # full sweep with no deferrals -> migration finished
        self._odusite_s3_migrate_set_flag(False)
        _logger.info("odusite_s3 migration finished (%d moved this run)", moved)

    # ------------------------------------------------------------------
    # garbage collection of orphaned S3 objects (dedup-aware)
    # ------------------------------------------------------------------
    @api.autovacuum
    def _gc_odusite_s3_store(self):
        if not self._odusite_s3_configured():
            return
        cr = self.env.cr
        # Continue in a new transaction; the LOCK below must be the first
        # statement so the snapshot sees the most recent ir_attachment changes.
        cr.commit()
        cr.execute("SET LOCAL lock_timeout TO '10s'")
        try:
            cr.execute("LOCK ir_attachment IN SHARE MODE")
        except psycopg2.errors.LockNotAvailable:
            cr.rollback()
            return False
        self._gc_odusite_s3_collect()
        cr.commit()

    def _gc_odusite_s3_collect(self):
        """The actual orphan sweep, without transaction management.

        Split out from ``_gc_odusite_s3_store`` so it can be exercised inside a
        test transaction (the commit/LOCK in the autovacuum wrapper would
        otherwise break the test savepoints).
        """
        cr = self.env.cr
        # make sure pending ORM writes are reflected in the raw SQL below
        self.env['ir.attachment'].flush_model(['store_fname'])
        self.env['odusite.s3.gc'].flush_model(['store_fname'])
        cr.execute("SELECT id, store_fname FROM odusite_s3_gc")
        rows = cr.fetchall()
        if not rows:
            return 0

        by_fname = {}
        for gc_id, fname in rows:
            by_fname.setdefault(fname, []).append(gc_id)

        referenced = set()
        for chunk in split_every(cr.IN_MAX, list(by_fname)):
            cr.execute(
                "SELECT store_fname FROM ir_attachment WHERE store_fname IN %s",
                [chunk])
            referenced.update(row[0] for row in cr.fetchall())

        cfg = self._odusite_s3_config()
        client = s3.get_client(self.env, cfg=cfg)
        bucket = s3.get_bucket(self.env, cfg)
        removed = 0
        processed_ids = []
        for fname, ids in by_fname.items():
            if fname not in referenced:
                try:
                    client.delete_object(
                        Bucket=bucket, Key=self._odusite_s3_object_key(fname))
                    removed += 1
                except Exception:  # noqa: BLE001
                    _logger.info("odusite_s3 gc could not delete %s", fname,
                                 exc_info=True)
                    continue  # keep the queue entry, retry next run
            processed_ids.extend(ids)

        if processed_ids:
            cr.execute(
                "DELETE FROM odusite_s3_gc WHERE id IN %s",
                [tuple(processed_ids)])
        _logger.info("odusite_s3 gc: %d checked, %d removed", len(rows), removed)
        return removed
