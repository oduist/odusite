// Data shapes for the events block — mirror specs/modules/odusite_event.md and
// the common field conventions in specs/02-api-conventions.md.

export interface EventTag {
  id: number;
  slug: string;
  name: string;
  category: string | null;
}

export interface EventAddress {
  city: string | null;
  country: string | null;
}

/** SEO block present on every detail entity (specs/02-api-conventions.md). */
export interface Seo {
  title: string | null;
  description: string | null;
  keywords: string | null;
  og_image: string | null;
}

/** Item of GET /events. */
export interface EventListItem {
  id: number;
  slug: string;
  name: string;
  subtitle: string | null;
  /** ISO 8601 UTC. */
  date_begin: string;
  /** ISO 8601 UTC. */
  date_end: string;
  /** IANA timezone of the event, e.g. "Europe/Warsaw". */
  timezone: string;
  is_ongoing: boolean;
  is_done: boolean;
  address: EventAddress | null;
  cover: string | null;
  tags: EventTag[];
}

export interface EventOrganizer {
  name: string;
  email: string | null;
}

export interface EventSeats {
  limited: boolean;
  available: number | null;
  sold_out: boolean;
}

/** Ticket type from event.event.ticket. */
export interface EventTicket {
  id: number;
  name: string;
  description: string | null;
  price: number;
  currency: string;
  seats_available: number | null;
  sale_start: string | null;
  sale_end: string | null;
  is_free: boolean;
}

/** GET /events/<id_or_slug>. */
export interface EventDetail extends EventListItem {
  /** Server-sanitized HTML. */
  description_html: string;
  organizer: EventOrganizer | null;
  seats: EventSeats;
  registrations_open: boolean;
  tickets: EventTicket[];
  seo: Seo;
  /** Odoo-side ICS URL; the site links to the same-origin /api proxy instead. */
  ics_url?: string;
}

/** Body of POST /api/events/register (same-origin), forwarded to Odoo. */
export interface RegistrationAttendee {
  name: string;
  email: string;
  phone?: string;
  /** Extra registration answers (forwarded as-is). */
  [answer: string]: unknown;
}

export interface RegistrationTicket {
  ticket_id: number;
  attendees: RegistrationAttendee[];
}

export interface RegistrationRequest {
  event_id: number;
  tickets: RegistrationTicket[];
}
