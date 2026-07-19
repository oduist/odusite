from odoo import http
from odoo.http import request
from odoo.tools import email_normalize, parse_contact_from_email

from odoo.addons.odusite_base.controllers.api import API_PREFIX, ApiError, odusite_route

HONEYPOT_FIELD = 'website_hp'


class OdusiteMassMailingController(http.Controller):
    """Newsletter subscription backed by mass_mailing.

    Mirrors the upstream /website_mass_mailing/subscribe controller
    (MassMailController.subscribe_to_newsletter, email flavour) without the
    recaptcha and session parts: the API is server-to-server, anti-spam is a
    honeypot field like the odusite_crm forms.
    """

    def _honeypot_triggered(self, kwargs):
        return bool(str(kwargs.get(HONEYPOT_FIELD) or '').strip())

    def _resolve_list(self, list_id):
        """Return the target public mailing list or raise 404 ``no_list``.

        Upstream has no per-website default newsletter list: the website
        builder snippet simply binds a public list (``is_public=True``).
        Without an explicit ``list_id`` the first public list (lowest id,
        i.e. the stock "Newsletter" list on standard databases) is used.
        """
        Lists = request.env['mailing.list'].sudo()
        if list_id:
            try:
                list_id = int(list_id)
            except (TypeError, ValueError):
                raise ApiError(400, 'bad_request', 'Invalid list_id.')
            mailing_list = Lists.search(
                [('id', '=', list_id), ('is_public', '=', True)], limit=1)
        else:
            mailing_list = Lists.search([('is_public', '=', True)], order='id', limit=1)
        if not mailing_list:
            raise ApiError(404, 'no_list', 'No public mailing list to subscribe to.')
        return mailing_list

    @odusite_route(f'{API_PREFIX}/newsletter/lists', methods=['GET'])
    def newsletter_lists(self, **kwargs):
        lists = request.env['mailing.list'].sudo().search(
            [('is_public', '=', True)], order='id')
        return [{'id': mailing_list.id, 'name': mailing_list.name}
                for mailing_list in lists]

    @odusite_route(f'{API_PREFIX}/newsletter/subscribe', methods=['POST'])
    def newsletter_subscribe(self, **kwargs):
        if self._honeypot_triggered(kwargs):
            # Silent success: bots must not learn they were detected.
            return {'subscribed': True}
        # Per-IP throttle (defense in depth behind the site-side Turnstile).
        request.env['odusite.rate.limit']._enforce(scope='newsletter', limit=10, window=3600)
        email = str(kwargs.get('email') or '').strip()
        if not email_normalize(email):
            raise ApiError(422, 'validation_error', 'Invalid email address.',
                           {'fields': {'email': 'invalid'}})
        mailing_list = self._resolve_list(kwargs.get('list_id'))
        self._subscribe(mailing_list, email)
        return {'subscribed': True, 'list': mailing_list.name}

    def _subscribe(self, mailing_list, email):
        """Create/reactivate the subscription like the upstream controller:
        find the subscription by list + contact email; when missing, reuse or
        create the mailing.contact and subscribe it; when opted out, opt back
        in. Re-subscribing an active subscription is a no-op (idempotent)."""
        name, email = parse_contact_from_email(email)
        Subscription = request.env['mailing.subscription'].sudo()
        Contact = request.env['mailing.contact'].sudo()
        subscription = Subscription.search(
            [('list_id', '=', mailing_list.id), ('contact_id.email', '=', email)],
            limit=1)
        if not subscription:
            contact = Contact.search([('email', '=', email)], limit=1)
            if not contact:
                contact = Contact.create({'name': name, 'email': email})
            Subscription.create({'contact_id': contact.id, 'list_id': mailing_list.id})
        elif subscription.opt_out:
            subscription.opt_out = False
