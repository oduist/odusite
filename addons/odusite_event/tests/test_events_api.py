"""Tests for the odusite_event API (see specs/modules/odusite_event.md).

Covers listing (period/tag filters, publish filtering), detail (dates, seats,
tickets, seo, ics_url), free registration incl. the documented deviations
(multi-slot events rejected with 422, `price` only exists with event_sale),
seat/sale availability errors and the ICS stream.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.odusite_base.tests.common import OdusiteHttpCase

try:
    import vobject
except ImportError:
    vobject = None


@tagged('post_install', '-at_install')
class TestEventsApi(OdusiteHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = fields.Datetime.now()
        cls.venue = cls.env['res.partner'].create({
            'name': 'Odusite Venue',
            'city': 'Berlin',
            'country_id': cls.env.ref('base.de').id,
        })
        # serialized tags require a color and a published category
        cls.tag_category = cls.env['event.tag.category'].create({
            'name': 'Odusite Topics',
            'is_published': True,
        })
        cls.tag = cls.env['event.tag'].create({
            'name': 'Odusite Tech',
            'category_id': cls.tag_category.id,
            'color': 1,
        })
        # visibility on the API = website_visibility 'public' (default)
        # + is_published; events without website_id match every website.
        cls.future_event = cls.env['event.event'].create({
            'name': 'Odusite Future Summit',
            'subtitle': 'The upcoming one',
            'date_begin': now + timedelta(days=30),
            'date_end': now + timedelta(days=31),
            'is_published': True,
            'address_id': cls.venue.id,
            'tag_ids': [(6, 0, cls.tag.ids)],
        })
        # website_event_sale may be auto-installed (website_sale + website_event),
        # adding a `price` field whose default follows the default event product —
        # force 0 so these fixtures stay free tickets.
        free_extra = (
            {'price': 0.0} if 'price' in cls.env['event.event.ticket']._fields else {})
        cls.future_ticket = cls.env['event.event.ticket'].create({
            'name': 'General Admission',
            'event_id': cls.future_event.id,
            **free_extra,
        })
        cls.past_event = cls.env['event.event'].create({
            'name': 'Odusite Past Meetup',
            'date_begin': now - timedelta(days=30),
            'date_end': now - timedelta(days=29),
            'is_published': True,
        })
        cls.unpublished_event = cls.env['event.event'].create({
            'name': 'Odusite Hidden Workshop',
            'date_begin': now + timedelta(days=10),
            'date_end': now + timedelta(days=11),
            'is_published': False,
        })
        # one available + one expired ticket: registrations stay open on the
        # event, but the expired ticket itself is not on sale
        cls.two_ticket_event = cls.env['event.event'].create({
            'name': 'Odusite Two Ticket Conference',
            'date_begin': now + timedelta(days=20),
            'date_end': now + timedelta(days=21),
            'is_published': True,
        })
        cls.open_ticket = cls.env['event.event.ticket'].create({
            'name': 'Open Ticket',
            'event_id': cls.two_ticket_event.id,
            **free_extra,
        })
        cls.expired_ticket = cls.env['event.event.ticket'].create({
            'name': 'Expired Ticket',
            'event_id': cls.two_ticket_event.id,
            'end_sale_datetime': now - timedelta(days=1),
            **free_extra,
        })
        # single-seat event (no tickets) for the sold-out check
        cls.tiny_event = cls.env['event.event'].create({
            'name': 'Odusite Tiny Event',
            'date_begin': now + timedelta(days=15),
            'date_end': now + timedelta(days=16),
            'is_published': True,
            'seats_limited': True,
            'seats_max': 1,
        })
        cls.multi_slot_event = cls.env['event.event'].create({
            'name': 'Odusite Multi Slot Event',
            'date_begin': now + timedelta(days=40),
            'date_end': now + timedelta(days=41),
            'is_published': True,
            'is_multi_slots': True,
        })

    # -- helpers -----------------------------------------------------------

    def _slug(self, record):
        return self.env['ir.http']._slug(record)

    def _list_ids(self, path):
        response, body = self.api('GET', path)
        self.assertEqual(response.status_code, 200, body)
        return {item['id'] for item in body['data']}

    def _register(self, event, payload):
        return self.api('POST', f'/events/{event.id}/register', payload)

    # -- listing -----------------------------------------------------------

    def test_events_list_periods(self):
        # default period is 'upcoming' (date_end >= now)
        upcoming = self._list_ids('/events?search=Odusite&limit=100')
        self.assertIn(self.future_event.id, upcoming)
        self.assertNotIn(self.past_event.id, upcoming)
        self.assertNotIn(self.unpublished_event.id, upcoming)

        past = self._list_ids('/events?search=Odusite&period=past&limit=100')
        self.assertIn(self.past_event.id, past)
        self.assertNotIn(self.future_event.id, past)
        self.assertNotIn(self.unpublished_event.id, past)

        response, body = self.api('GET', '/events?period=someday')
        self.assert_api_error(response, body, 400, 'bad_request')

    def test_events_list_tag_filter(self):
        tagged_ids = self._list_ids(f'/events?tag={self.tag.id}&limit=100')
        self.assertEqual(tagged_ids, {self.future_event.id})

        response, body = self.api('GET', '/events?search=Odusite+Future&limit=100')
        self.assertEqual(response.status_code, 200, body)
        item = next(e for e in body['data'] if e['id'] == self.future_event.id)
        self.assertEqual(item['tags'], [{
            'id': self.tag.id,
            'slug': self._slug(self.tag),
            'name': 'Odusite Tech',
            'category': 'Odusite Topics',
        }])
        self.assertEqual(item['subtitle'], 'The upcoming one')

    # -- detail ------------------------------------------------------------

    def test_event_detail(self):
        event = self.future_event
        response, body = self.api('GET', f'/events/{self._slug(event)}')
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['id'], event.id)
        self.assertEqual(data['name'], 'Odusite Future Summit')
        self.assertEqual(
            data['date_begin'],
            event.date_begin.replace(microsecond=0).isoformat() + 'Z')
        self.assertEqual(
            data['date_end'],
            event.date_end.replace(microsecond=0).isoformat() + 'Z')
        self.assertEqual(data['timezone'], event.date_tz)
        self.assertFalse(data['is_ongoing'])
        self.assertFalse(data['is_done'])
        self.assertEqual(data['address'], {'city': 'Berlin', 'country': 'Germany'})
        self.assertEqual(
            data['seats'], {'limited': False, 'available': None, 'sold_out': False})
        self.assertTrue(data['registrations_open'])
        self.assertEqual(len(data['tickets']), 1)
        ticket = data['tickets'][0]
        self.assertEqual(ticket['id'], self.future_ticket.id)
        self.assertEqual(ticket['name'], 'General Admission')
        self.assertTrue(ticket['is_free'])
        self.assertEqual(ticket['price'], 0.0)
        self.assertIsNone(ticket['seats_available'])  # no per-ticket limit
        self.assertTrue(data['seo']['title'])
        self.assertEqual(data['ics_url'], f'/odusite/v1/events/{event.id}/ics')

    def test_event_detail_unpublished_404(self):
        response, body = self.api('GET', f'/events/{self.unpublished_event.id}')
        self.assert_api_error(response, body, 404, 'not_found')
        response, body = self.api(
            'GET', f'/events/{self._slug(self.unpublished_event)}')
        self.assert_api_error(response, body, 404, 'not_found')

    # -- registration ------------------------------------------------------

    def test_register_free_ticket(self):
        response, body = self._register(self.future_event, {'tickets': [{
            'ticket_id': self.future_ticket.id,
            'attendees': [
                {'name': 'Alice Attendee', 'email': 'alice@example.com'},
                {'name': 'Bob Attendee', 'email': 'bob@example.com',
                 'phone': '+49 30 1234567'},
            ],
        }]})
        self.assertEqual(response.status_code, 200, body)
        data = body['data']
        self.assertEqual(data['event_id'], self.future_event.id)
        self.assertEqual(len(data['registrations']), 2)
        by_email = {r['email']: r for r in data['registrations']}
        self.assertEqual(by_email['alice@example.com']['name'], 'Alice Attendee')
        self.assertEqual(by_email['alice@example.com']['ticket'], 'General Admission')
        self.assertEqual(by_email['alice@example.com']['state'], 'open')

        registration = self.env['event.registration'].search([
            ('event_id', '=', self.future_event.id),
            ('email', '=', 'alice@example.com'),
        ])
        self.assertEqual(len(registration), 1)
        self.assertEqual(registration.state, 'open')
        self.assertEqual(registration.event_ticket_id, self.future_ticket)

    def test_register_validation_errors(self):
        # unknown ticket id (event has tickets -> ticket entry must match)
        response, body = self._register(self.future_event, {'tickets': [{
            'ticket_id': 99999999,
            'attendees': [{'name': 'X', 'email': 'x@example.com'}],
        }]})
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(body['error']['details']['fields'], {'ticket_id': 'invalid'})

        # missing attendees
        response, body = self._register(self.future_event, {'tickets': [{
            'ticket_id': self.future_ticket.id,
        }]})
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(body['error']['details']['fields'], {'attendees': 'required'})

        # attendee without email
        response, body = self._register(self.future_event, {'tickets': [{
            'ticket_id': self.future_ticket.id,
            'attendees': [{'name': 'No Mail'}],
        }]})
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(body['error']['details']['fields'], {'email': 'required'})

        # missing tickets list entirely
        response, body = self._register(self.future_event, {})
        self.assert_api_error(response, body, 422, 'validation_error')
        self.assertEqual(body['error']['details']['fields'], {'tickets': 'required'})

    def test_register_multi_slot_rejected(self):
        # documented deviation: phase 1 API refuses multi-slot events
        response, body = self._register(self.multi_slot_event, {'tickets': [{
            'attendees': [{'name': 'X', 'email': 'x@example.com'}],
        }]})
        self.assert_api_error(response, body, 422, 'validation_error')

    def test_register_closed_event(self):
        # past event -> event_registrations_open is False
        response, body = self._register(self.past_event, {'tickets': [{
            'attendees': [{'name': 'Late Larry', 'email': 'larry@example.com'}],
        }]})
        self.assert_api_error(response, body, 422, 'registrations_closed')

    def test_register_expired_ticket(self):
        # event still open (another ticket on sale), chosen ticket expired
        response, body = self._register(self.two_ticket_event, {'tickets': [{
            'ticket_id': self.expired_ticket.id,
            'attendees': [{'name': 'X', 'email': 'x@example.com'}],
        }]})
        self.assert_api_error(response, body, 422, 'ticket_unavailable')

    def test_register_sold_out(self):
        # 1 seat, 2 attendees -> _verify_seats_availability raises
        response, body = self._register(self.tiny_event, {'tickets': [{
            'attendees': [
                {'name': 'First', 'email': 'first@example.com'},
                {'name': 'Second', 'email': 'second@example.com'},
            ],
        }]})
        self.assert_api_error(response, body, 422, 'sold_out')
        self.assertFalse(self.env['event.registration'].search([
            ('event_id', '=', self.tiny_event.id)]))

    def test_register_paid_ticket_rejected(self):
        # `price` only exists when event_sale is installed (documented guard)
        if 'price' not in self.env['event.event.ticket']._fields:
            self.skipTest('event_sale is not installed; every ticket is free')
        paid_ticket = self.env['event.event.ticket'].create({
            'name': 'VIP',
            'event_id': self.future_event.id,
            'price': 100.0,
        })
        response, body = self._register(self.future_event, {'tickets': [{
            'ticket_id': paid_ticket.id,
            'attendees': [{'name': 'Rich Rita', 'email': 'rita@example.com'}],
        }]})
        self.assert_api_error(response, body, 409, 'payment_required')

    # -- ICS ---------------------------------------------------------------

    def test_event_ics(self):
        if vobject is None:
            self.skipTest('vobject is not installed; _get_ics_file returns nothing')
        response, _body = self.api('GET', f'/events/{self.future_event.id}/ics')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/calendar', response.headers.get('Content-Type', ''))
        self.assertIn(b'BEGIN:VCALENDAR', response.content)
        self.assertIn(b'Odusite Future Summit', response.content)

        response, body = self.api('GET', f'/events/{self.unpublished_event.id}/ics')
        self.assert_api_error(response, body, 404, 'not_found')
