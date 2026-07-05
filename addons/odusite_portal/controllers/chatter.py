"""Generic portal chatter endpoints (specs/modules/odusite_portal.md).

Only models whitelisted through the ``odusite.api._chatter_models()`` registry
hook are reachable. Reads are allowed either through the JWT user's record
rules or through the record's portal ``access_token``
(CustomerPortal._document_check_access pattern); posting always requires a
JWT (token-authenticated posting is phase 2).
"""

from odoo.fields import Domain
from odoo.http import request

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    list_meta,
    odusite_route,
    parse_pagination,
)
from odoo.addons.odusite_base.lib import serializers
from odoo.addons.portal.controllers.portal import CustomerPortal

# Message body used by the mail client for deleted messages; treated as empty
# (portal/controllers/portal_thread.py _get_non_empty_message_domain).
EMPTY_EDITED_BODY = '<span class="o-mail-Message-edited"></span>'


class OdusiteChatterController(CustomerPortal):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _chatter_check_model(self, model_name):
        if (model_name not in request.env['odusite.api']._chatter_models()
                or model_name not in request.env):
            # Same response as an unknown record: don't reveal model names.
            raise ApiError(404, 'not_found',
                           'This document is not available through the chatter API.')

    def _chatter_record(self, model_name, res_id, access_token=None):
        """Whitelist + access check. Returns ``(record_sudo, token_only)``
        where ``token_only`` tells whether access was granted by the record's
        access_token instead of the JWT user's record rules."""
        self._chatter_check_model(model_name)
        # _document_check_access (portal/controllers/portal.py) raises
        # MissingError -> 404 / AccessError -> 403 through odusite_route.
        record_sudo = self._document_check_access(
            model_name, res_id, access_token=access_token)
        token_only = not request.env[model_name].browse(res_id).has_access('read')
        return record_sudo, token_only

    def _message_domain(self, model_name, res_id):
        """Share-safe comment-only domain, mirroring portal
        ``/mail/chatter_fetch`` (portal/controllers/portal_thread.py):
        website_message_ids comodel domain + mail.mt_comment subtype +
        mail.message._get_search_domain_share() + non-empty body."""
        return (
            Domain('model', '=', model_name)
            & Domain('res_id', '=', res_id)
            & Domain('message_type', 'in',
                     ('comment', 'email', 'email_outgoing', 'auto_comment', 'out_of_office'))
            & Domain('subtype_id', '=', request.env.ref('mail.mt_comment').id)
            & request.env['mail.message']._get_search_domain_share()
            & (Domain('body', 'not in', [False, EMPTY_EDITED_BODY])
               | Domain('attachment_ids', '!=', False))
        )

    def _serialize_messages(self, messages, access_token=None):
        """Spec shape adapted from mail.message.portal_message_format
        (portal/models/mail_message.py)."""
        options = {'token': access_token} if access_token else {}
        items = []
        for values in messages.portal_message_format(options=options):
            body = values.get('body')
            if isinstance(body, (list, tuple)):  # wrapped as ['markup', html]
                body = body[1] if len(body) > 1 else ''
            items.append({
                'id': values['id'],
                'body': str(body or ''),
                'date': serializers.datetime_utc(values.get('date')),
                'author': {
                    'name': (values.get('author_id') or {}).get('name') or '',
                    'avatar': values.get('author_avatar_url'),
                },
                'attachments': [
                    {
                        'id': attachment['id'],
                        'name': attachment.get('filename') or attachment.get('name') or '',
                        'mimetype': attachment.get('mimetype') or '',
                        'url': '/web/content/%s?access_token=%s' % (
                            attachment['id'], attachment.get('raw_access_token') or ''),
                    }
                    for attachment in (values.get('attachment_ids') or [])
                ],
            })
        return items

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    @odusite_route(f'{API_PREFIX}/chatter/<string:model>/<int:res_id>/messages',
                   methods=['GET'])
    def chatter_messages(self, model, res_id, access_token=None, **params):
        _record_sudo, token_only = self._chatter_record(
            model, res_id, access_token=access_token)
        page, limit, offset, _order = parse_pagination(params)
        # sudo only for token-authenticated reads; the JWT user path keeps
        # mail.message's own access filtering (mirrors /mail/chatter_fetch).
        Message = request.env['mail.message'].sudo() if token_only \
            else request.env['mail.message']
        domain = self._message_domain(model, res_id)
        total = Message.search_count(domain)
        messages = Message.search(domain, order='id desc', limit=limit, offset=offset)
        items = self._serialize_messages(
            messages, access_token=access_token if token_only else None)
        return items, list_meta(total, page, limit)

    @odusite_route(f'{API_PREFIX}/chatter/<string:model>/<int:res_id>/messages',
                   methods=['POST'], auth_user=True)
    def chatter_post_message(self, model, res_id, body=None, attachment_ids=None, **params):
        """Post a comment as the JWT user.

        Mirrors ``/mail/message/post`` (mail/controllers/thread.py): posting
        rights come from the document's ``_mail_post_access`` and are checked
        as the JWT user before the sudo()ed message_post (the author stays
        the JWT user's partner — sudo keeps the uid).
        """
        self._chatter_check_model(model)
        record = request.env[model].browse(res_id)
        if not record.sudo().exists():
            raise ApiError(404, 'not_found', 'The requested record does not exist.')

        body = body.strip() if isinstance(body, str) else ''
        if attachment_ids is not None and not (
                isinstance(attachment_ids, list)
                and all(isinstance(attachment_id, int) for attachment_id in attachment_ids)):
            raise ApiError(400, 'bad_request', 'attachment_ids must be a list of integers.')
        if not body and not attachment_ids:
            raise ApiError(422, 'validation_error', 'A message body or attachments are required.',
                           {'fields': {'body': 'This field is required.'}})

        record_sudo = record.sudo()
        access_mode = record_sudo._mail_get_operation_for_mail_message_operation(
            'create').get(record_sudo)
        if not access_mode:
            raise ApiError(403, 'forbidden', 'You cannot post on this document.')
        record.check_access(access_mode)  # AccessError -> 403 via odusite_route

        thread = record
        if not record.has_access('write'):
            thread = thread.with_context(
                mail_post_autofollow_author_skip=True, mail_post_autofollow=False)
        # str body is escaped by message_post; pending attachments not created
        # by the JWT user are dropped by _process_attachments_for_post.
        message = thread.sudo().message_post(
            body=body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            attachment_ids=attachment_ids or [],
        )
        return self._serialize_messages(message.sudo())[0]

    @odusite_route(f'{API_PREFIX}/chatter/attachments', methods=['POST'], auth_user=True)
    def chatter_attachment_upload(self, **params):
        """Multipart upload of a pending attachment (field name ``file``),
        to be linked to a message through POST .../messages.

        Mirrors ``/mail/attachment/upload`` (mail/controllers/attachment.py):
        the attachment is created as pending (res_model mail.compose.message,
        res_id 0); create_uid stays the JWT user so message_post's ownership
        filter accepts it. Requires a JWT like message posting.
        """
        ufile = (request.httprequest.files.get('file')
                 or request.httprequest.files.get('ufile'))
        if ufile is None:
            raise ApiError(400, 'bad_request', "Missing multipart file field 'file'.")
        attachment = request.env['ir.attachment'].sudo().create({
            'name': ufile.filename or 'attachment',
            'raw': ufile.read(),
            'res_model': 'mail.compose.message',
            'res_id': 0,
        })
        attachment._post_add_create()
        attachment.generate_access_token()
        return {
            'id': attachment.id,
            'name': attachment.name,
            'mimetype': attachment.mimetype or '',
            'size': attachment.file_size,
            'access_token': attachment.access_token,
            'url': f'/web/content/{attachment.id}?access_token={attachment.access_token}',
        }
