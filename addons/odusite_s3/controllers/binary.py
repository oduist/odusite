"""Direct download of S3-backed originals via a 302 -> presigned URL.

The 15.0 reference module hooked ``ir.http._get_content_common`` /
``ir.http._content_image``. Odoo 19 removed those: ``/web/content`` and
``/web/image`` are served by the ``web`` ``Binary`` controller, which delegates
access control to ``ir.binary._find_record`` and stream building to
``ir.binary._get_stream_from`` / ``_get_image_stream_from``. Those model helpers
are also used server-side (e.g. spreadsheet ``.read()``), so redirecting there
would break internal byte readers. We therefore inject the redirect at the exact
19.0 equivalent of the reference's hook — the HTTP handler — by extending the
``Binary`` controller.

For an S3-backed *original* (no resize/crop) we run the SAME access check the
real handler does (``_find_record``) and, on success, 302-redirect to a
short-lived presigned URL so the bytes leave the object store directly. Resized
image variants fall through to normal serving (bytes read from S3, resized and
edge-cached by Odoo). Gated by the ``odusite.s3.direct_download`` setting.
"""

import logging

from odoo.http import request
from odoo.addons.web.controllers.binary import Binary

_logger = logging.getLogger(__name__)


class OdusiteS3Binary(Binary):

    def _odusite_s3_resolve_attachment(self, record, field):
        """Return the ir.attachment backing the served binary, or empty rs."""
        if record._name == 'ir.attachment':
            return record
        return request.env['ir.attachment'].sudo().search([
            ('res_model', '=', record._name),
            ('res_id', '=', record.id),
            ('res_field', '=', field),
        ], limit=1)

    def _odusite_s3_try_redirect(self, xmlid=None, model='ir.attachment', id=None,
                                 field='raw', access_token=None, download=None,
                                 filename=None):
        """Return a 302 to a presigned URL for S3-backed originals, else None.

        Access control is enforced exactly like the real handler (via
        ``ir.binary._find_record``) *before* the redirect, so the short-lived
        presigned URL is only handed out to an authorized caller. Any error
        (missing/forbidden record, signing failure) returns None so the caller
        falls through to normal serving, which reproduces the same behaviour.
        """
        Attachment = request.env['ir.attachment']
        if not Attachment._odusite_s3_direct_download_enabled():
            return None
        try:
            record = request.env['ir.binary']._find_record(
                xmlid, model, id and int(id), access_token, field=field)
        except Exception:  # noqa: BLE001 - fall through to the normal handler
            return None
        attachment = self._odusite_s3_resolve_attachment(record, field)
        if not attachment or not attachment._odusite_s3_is_s3(attachment.store_fname):
            return None
        url = attachment._odusite_s3_presigned_url(download=download, filename=filename)
        if not url:
            return None
        return request.redirect(url, code=302, local=False)

    # pylint: disable=redefined-builtin,invalid-name
    def content_common(self, xmlid=None, model='ir.attachment', id=None, field='raw',
                       filename=None, filename_field='name', mimetype=None, unique=False,
                       download=False, access_token=None, nocache=False):
        redirect = self._odusite_s3_try_redirect(
            xmlid=xmlid, model=model, id=id, field=field,
            access_token=access_token, download=download, filename=filename)
        if redirect is not None:
            return redirect
        return super().content_common(
            xmlid=xmlid, model=model, id=id, field=field, filename=filename,
            filename_field=filename_field, mimetype=mimetype, unique=unique,
            download=download, access_token=access_token, nocache=nocache)

    # pylint: disable=redefined-builtin,invalid-name
    def content_image(self, xmlid=None, model='ir.attachment', id=None, field='raw',
                      filename_field='name', filename=None, mimetype=None, unique=False,
                      download=False, width=0, height=0, crop=False, access_token=None,
                      nocache=False):
        # Only redirect when the original image is served as-is; resize/crop
        # transforms need the actual bytes, which are read from S3 normally.
        if not (int(width or 0) or int(height or 0) or crop):
            redirect = self._odusite_s3_try_redirect(
                xmlid=xmlid, model=model, id=id, field=field,
                access_token=access_token, download=download, filename=filename)
            if redirect is not None:
                return redirect
        return super().content_image(
            xmlid=xmlid, model=model, id=id, field=field,
            filename_field=filename_field, filename=filename, mimetype=mimetype,
            unique=unique, download=download, width=width, height=height,
            crop=crop, access_token=access_token, nocache=nocache)
