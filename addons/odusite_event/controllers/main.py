"""Odusite events API (see specs/modules/odusite_event.md).

Published filtering mirrors website_event: ``website.website_domain()`` +
``is_visible_on_website`` (public visibility / participation) +
``is_published``. Phase 1 supports free registration only.
"""

import json
import re

from odoo import fields, http
from odoo.exceptions import ValidationError
from odoo.http import content_disposition, request
from odoo.tools import email_normalize

from odoo.addons.odusite_base.controllers.api import (
    API_PREFIX,
    ApiError,
    list_meta,
    odusite_route,
    parse_pagination,
)
from odoo.addons.odusite_base.lib import serializers

EVENT_ORDERS = {
    'date': 'date_begin asc, id asc',
    'date_desc': 'date_begin desc, id desc',
}


class OdusiteEventController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _published_domain(self):
        """Same visibility rules as the upstream /event controller
        (event.event._search_get_detail) + explicit publish filter."""
        website = request.website
        return (
            website.website_domain()
            + [('is_visible_on_website', '=', True), ('is_published', '=', True)]
        )

    def _get_event(self, id_or_slug):
        _name, event_id = serializers.unslug(str(id_or_slug))
        if not event_id:
            raise ApiError(404, 'not_found', 'Event not found.')
        event = request.env['event.event'].search(
            self._published_domain() + [('id', '=', event_id)], limit=1)
        if not event:
            raise ApiError(404, 'not_found', 'Event not found.')
        return event

    def _event_cover(self, event):
        """Extract the cover image URL from website.cover_properties.mixin."""
        try:
            props = json.loads(event.sudo().cover_properties or '{}')
        except ValueError:
            return None
        match = re.search(r"url\('?\"?([^'\")]+)'?\"?\)", props.get('background-image') or '')
        return match.group(1) if match else None

    def _serialize_tag(self, tag):
        tag = tag.sudo()
        return {
            'id': tag.id,
            'slug': serializers.slug(tag),
            'name': tag.name,
            'category': tag.category_id.name or None,
        }

    def _event_tags(self, event):
        # mirror the public record rule on event.tag: published category + color
        return [
            self._serialize_tag(tag)
            for tag in event.sudo().tag_ids
            if tag.color and tag.category_id.website_published
        ]

    def _serialize_event(self, event):
        address = event.sudo().address_id
        return {
            'id': event.id,
            'slug': serializers.slug(event),
            'name': event.name,
            'subtitle': event.subtitle or '',
            'date_begin': serializers.datetime_utc(event.date_begin),
            'date_end': serializers.datetime_utc(event.date_end),
            'timezone': event.date_tz,
            'is_ongoing': event.is_ongoing,
            'is_done': event.is_done,
            'address': {
                'city': address.city or None,
                'country': address.country_id.name or None,
            } if address else None,
            'cover': self._event_cover(event),
            'tags': self._event_tags(event),
        }

    def _serialize_ticket(self, ticket):
        ticket = ticket.sudo()
        # `price` / `currency_id` only exist when event_sale is installed;
        # without it every ticket is free (phase 1).
        price = ticket.price if 'price' in ticket._fields else 0.0
        if 'currency_id' in ticket._fields and ticket.currency_id:
            currency = ticket.currency_id
        else:
            currency = request.website.company_id.sudo().currency_id
        return {
            'id': ticket.id,
            'name': ticket.name,
            'description': ticket.description or '',
            'price': serializers.money(price, currency)['amount'],
            'currency': currency.name,
            'seats_available': ticket.seats_available if ticket.seats_max else None,
            'sale_start': serializers.datetime_utc(ticket.start_sale_datetime),
            'sale_end': serializers.datetime_utc(ticket.end_sale_datetime),
            'is_free': not price,
        }

    def _serialize_event_detail(self, event):
        data = self._serialize_event(event)
        organizer = event.sudo().organizer_id
        data.update({
            'description_html': serializers.html_field(event, 'description'),
            'organizer': {
                'name': organizer.name,
                'email': organizer.email or None,
            } if organizer else None,
            'seats': {
                'limited': event.seats_limited,
                'available': event.seats_available if event.seats_limited else None,
                'sold_out': event.event_registrations_sold_out,
            },
            'registrations_open': event.event_registrations_open,
            'tickets': [
                self._serialize_ticket(ticket)
                for ticket in event.sudo().event_ticket_ids
            ],
            'seo': serializers.seo(event),
            'ics_url': f'{API_PREFIX}/events/{event.id}/ics',
        })
        return data

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @odusite_route(f'{API_PREFIX}/events', methods=['GET'])
    def events_list(self, **kwargs):
        period = kwargs.get('period') or 'upcoming'
        if period not in ('upcoming', 'past'):
            raise ApiError(400, 'bad_request', 'period must be "upcoming" or "past".')
        page, limit, offset, order = parse_pagination(
            kwargs, order_whitelist=EVENT_ORDERS,
            default_order='date_desc' if period == 'past' else 'date')

        domain = self._published_domain()
        now = fields.Datetime.now()
        if period == 'upcoming':
            domain += [('date_end', '>=', now)]
        else:
            domain += [('date_end', '<', now)]

        if kwargs.get('tag'):
            _name, tag_id = serializers.unslug(str(kwargs['tag']))
            if not tag_id:
                raise ApiError(400, 'bad_request', 'Invalid tag.')
            domain += [('tag_ids', 'in', [tag_id])]

        if kwargs.get('country'):
            country = kwargs['country']
            if isinstance(country, str) and not country.isdigit():
                country_rec = request.env['res.country'].sudo().search(
                    [('code', '=', country.upper())], limit=1)
                if not country_rec:
                    raise ApiError(400, 'bad_request', 'Unknown country.')
                domain += [('country_id', '=', country_rec.id)]
            else:
                domain += [('country_id', '=', int(country))]

        if kwargs.get('search'):
            domain += ['|', ('name', 'ilike', kwargs['search']),
                       ('subtitle', 'ilike', kwargs['search'])]

        Event = request.env['event.event']
        total = Event.search_count(domain)
        events = Event.search(domain, limit=limit, offset=offset, order=order)
        return (
            [self._serialize_event(event) for event in events],
            list_meta(total, page, limit),
        )

    @odusite_route(f'{API_PREFIX}/events/<string:id_or_slug>', methods=['GET'])
    def event_detail(self, id_or_slug, **kwargs):
        event = self._get_event(id_or_slug)
        return self._serialize_event_detail(event)

    @odusite_route(f'{API_PREFIX}/events/<int:event_id>/register', methods=['POST'])
    def event_register(self, event_id, **kwargs):
        # Per-IP throttle: registrations send confirmation emails to arbitrary
        # attendee addresses, so cap them (defense in depth behind Turnstile).
        request.env['odusite.rate.limit']._enforce(scope='event_register', limit=10, window=3600)
        event = self._get_event(event_id)
        event_sudo = event.sudo()

        if event_sudo.is_multi_slots:
            raise ApiError(422, 'validation_error',
                           'Multi-slot events are not supported by this API yet.')
        if not event.event_registrations_open:
            raise ApiError(422, 'registrations_closed',
                           'Registrations are closed for this event.')

        tickets_payload = kwargs.get('tickets')
        if not isinstance(tickets_payload, list) or not tickets_payload:
            raise ApiError(422, 'validation_error', 'Missing tickets.',
                           {'fields': {'tickets': 'required'}})

        event_tickets = {ticket.id: ticket for ticket in event_sudo.event_ticket_ids}
        registrations_values = []
        slot_ticket_counts = {}
        for ticket_entry in tickets_payload:
            if not isinstance(ticket_entry, dict):
                raise ApiError(422, 'validation_error', 'Invalid ticket entry.')
            ticket_id = ticket_entry.get('ticket_id')
            ticket = None
            if event_tickets:
                ticket = event_tickets.get(ticket_id)
                if not ticket:
                    # same behavior as upstream _process_attendees_form
                    raise ApiError(422, 'validation_error',
                                   'This ticket is not available for sale for this event.',
                                   {'fields': {'ticket_id': 'invalid'}})
                price = ticket.price if 'price' in ticket._fields else 0.0
                if price:
                    raise ApiError(
                        409, 'payment_required',
                        'Paid tickets cannot be registered through this endpoint.')
                if not ticket.sale_available:
                    raise ApiError(422, 'ticket_unavailable',
                                   'This ticket is sold out or not on sale.')
            attendees = ticket_entry.get('attendees')
            if not isinstance(attendees, list) or not attendees:
                raise ApiError(422, 'validation_error', 'Missing attendees.',
                               {'fields': {'attendees': 'required'}})
            for attendee in attendees:
                registrations_values.append(
                    self._prepare_registration_values(event, ticket, attendee))
            key = ticket.id if ticket else False
            slot_ticket_counts[key] = slot_ticket_counts.get(key, 0) + len(attendees)

        # seats check, same as upstream registration_confirm
        try:
            event_sudo._verify_seats_availability([
                (False, event_tickets.get(ticket_id) or False, count)
                for ticket_id, count in slot_ticket_counts.items()
            ])
        except ValidationError:
            raise ApiError(422, 'sold_out',
                           'There are not enough seats available for this event.')

        registrations = request.env['event.registration'].sudo().create(
            registrations_values)
        return {
            'event_id': event.id,
            'registrations': [
                {
                    'id': registration.id,
                    'name': registration.name,
                    'email': registration.email or None,
                    'ticket': registration.event_ticket_id.name or None,
                    'state': registration.state,
                }
                for registration in registrations
            ],
        }

    def _prepare_registration_values(self, event, ticket, attendee):
        if not isinstance(attendee, dict):
            raise ApiError(422, 'validation_error', 'Invalid attendee entry.')

        def text(field):
            value = attendee.get(field)
            return str(value).strip() if value is not None else ''

        missing = {
            field: 'required'
            for field in ('name', 'email')
            if not text(field)
        }
        if missing:
            raise ApiError(422, 'validation_error', 'Missing attendee fields.',
                           {'fields': missing})
        if not email_normalize(text('email')):
            raise ApiError(422, 'validation_error', 'Invalid attendee email address.',
                           {'fields': {'email': 'invalid'}})
        values = {
            'event_id': event.id,
            'event_ticket_id': ticket.id if ticket else False,
            'name': text('name'),
            'email': text('email'),
            'phone': text('phone') or False,
            'company_name': text('company_name') or False,
        }
        if not request.env.user._is_public():
            values['partner_id'] = request.env.user.partner_id.id
        answer_commands = self._prepare_answer_commands(event, attendee.get('answers'))
        if answer_commands:
            values['registration_answer_ids'] = answer_commands
        return values

    def _prepare_answer_commands(self, event, answers):
        if not answers:
            return []
        if not isinstance(answers, list):
            raise ApiError(422, 'validation_error', 'answers must be a list.',
                           {'fields': {'answers': 'invalid'}})
        questions = {question.id: question for question in event.sudo().question_ids}
        commands = []
        for answer in answers:
            if not isinstance(answer, dict) or 'question_id' not in answer:
                raise ApiError(422, 'validation_error', 'Invalid answer entry.',
                               {'fields': {'answers': 'invalid'}})
            question = questions.get(answer.get('question_id'))
            if not question:
                raise ApiError(422, 'validation_error', 'Unknown question.',
                               {'fields': {'answers': 'unknown_question'}})
            value = answer.get('value')
            if question.question_type == 'simple_choice':
                try:
                    answer_values = {'question_id': question.id,
                                     'value_answer_id': int(value)}
                except (TypeError, ValueError):
                    raise ApiError(422, 'validation_error',
                                   'Choice answers expect an answer id.',
                                   {'fields': {'answers': 'invalid_choice'}})
                if answer_values['value_answer_id'] not in question.answer_ids.ids:
                    raise ApiError(422, 'validation_error', 'Unknown answer choice.',
                                   {'fields': {'answers': 'invalid_choice'}})
            else:
                answer_values = {'question_id': question.id,
                                 'value_text_box': str(value or '')}
            commands.append((0, 0, answer_values))
        return commands

    @odusite_route(f'{API_PREFIX}/events/<int:event_id>/ics', methods=['GET'])
    def event_ics(self, event_id, **kwargs):
        event = self._get_event(event_id)
        # same call as the upstream /event/<event>/ics controller
        files = event._get_ics_file(slot=request.env['event.slot'].sudo().browse(False))
        if event.id not in files:
            raise ApiError(404, 'not_found', 'ICS file is not available.')
        content = files[event.id]
        return request.make_response(content, [
            ('Content-Type', 'text/calendar'),
            ('Content-Length', len(content)),
            ('Content-Disposition', content_disposition('%s.ics' % event.name)),
        ])
