# odusite_event

Depends: `odusite_base`, `website_event` (brings `event`).
Phase 1: listing, detail, free registration. Paid tickets via cart — phase 2
(website_event_sale bridge). Tracks/agenda/booths/exhibitors — phase 2.

## Endpoints

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/events` | GET | Paginated published events. Filters: `?tag=&country=&period=upcoming\|past&search=`. Item: `{id, slug, name, subtitle, date_begin, date_end, timezone, is_ongoing, is_done, address: {city, country}, cover, tags[{id, slug, name, category}]}`. Default order: date_begin asc (upcoming). |
| `/odusite/v1/events/<id_or_slug>` | GET | Detail: + `description_html`, organizer `{name, email}`, seats `{limited, available, sold_out}`, `registrations_open`, ticket types `[{id, name, description, price, currency, seats_available, sale_start, sale_end, is_free}]` (from `event.event.ticket`), `seo`, ICS url. |
| `/odusite/v1/events/<id>/register` | POST | Free tickets only (v1): `{tickets: [{ticket_id, attendees: [{name, email, phone, ...registration answers}]}]}` → creates `event.registration` records (open state), sends stock confirmation mail. 422 when sold out/closed; 409 `payment_required` for paid tickets (until phase 2). |
| `/odusite/v1/events/<id>/ics` | GET | ICS file stream. |

## Webhooks / sitemap

Watched: `event.event` (dates, name, publish, seats), `event.tag`.
Tags: `events`, `events:<id>`. Sitemap: `/events/<slug>`.

## Site block `events`

`/events` (upcoming/past toggle, tag filter), `/events/[event]` (hero with
dates/venue, description, ticket selection, registration form with per-attendee
fields, success state), calendar links (ICS/Google).
