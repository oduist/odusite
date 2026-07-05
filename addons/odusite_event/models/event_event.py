from odoo import models


class EventEvent(models.Model):
    _name = 'event.event'
    _inherit = ['event.event', 'odusite.watched.mixin']

    _odusite_tag = 'events'
    _odusite_watch_fields = (
        'name', 'subtitle', 'description',
        'date_begin', 'date_end', 'date_tz',
        'seats_max', 'seats_limited',
        'address_id', 'organizer_id', 'tag_ids',
        'website_visibility', 'event_ticket_ids',
    )
