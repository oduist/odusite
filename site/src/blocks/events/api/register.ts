// Same-origin registration proxy: browser → here → Odoo /events/<id>/register.
// Free tickets only in v1; paid tickets surface 409 payment_required.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { getEnv } from '@lib/env';
import { enforceTurnstile } from '@lib/turnstile';
import type { RegistrationAttendee, RegistrationTicket } from '../types';

export const prerender = false;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function badRequest(message: string): Response {
  return json({ error: { code: 'bad_request', message } }, 400);
}

export const POST: APIRoute = async (context) => {
  const raw = (await context.request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!raw) return badRequest('Invalid JSON body');

  // Anti-bot check comes first; fails closed when the widget is configured but
  // the secret is missing. Guards against registration/email-bombing.
  const turnstileBlocked = await enforceTurnstile(
    getEnv(context),
    typeof raw['cf-turnstile-response'] === 'string' ? (raw['cf-turnstile-response'] as string) : null,
    context.request.headers.get('CF-Connecting-IP'),
    new URL(context.request.url).hostname,
  );
  if (turnstileBlocked) return turnstileBlocked;

  const eventId = Number(raw.event_id);
  if (!Number.isInteger(eventId) || eventId <= 0) return badRequest('Missing event_id');

  const ticketsRaw = Array.isArray(raw.tickets) ? (raw.tickets as Record<string, unknown>[]) : [];
  if (ticketsRaw.length === 0) return badRequest('Select at least one ticket');

  const tickets: RegistrationTicket[] = [];
  for (const ticket of ticketsRaw) {
    const ticketId = Number(ticket.ticket_id);
    const attendeesRaw = Array.isArray(ticket.attendees)
      ? (ticket.attendees as Record<string, unknown>[])
      : [];
    if (!Number.isInteger(ticketId) || ticketId <= 0 || attendeesRaw.length === 0) {
      return badRequest('Each ticket needs a ticket_id and at least one attendee');
    }
    const attendees: RegistrationAttendee[] = [];
    for (const attendee of attendeesRaw) {
      const name = String(attendee.name ?? '').trim();
      const email = String(attendee.email ?? '').trim();
      const phone = String(attendee.phone ?? '').trim();
      if (!name || !email) return badRequest('Each attendee needs a name and an email');
      attendees.push(phone ? { name, email, phone } : { name, email });
    }
    tickets.push({ ticket_id: ticketId, attendees });
  }

  try {
    const data = await apiFetch(context, `/events/${eventId}/register`, {
      method: 'POST',
      body: { tickets },
    });
    return json({ data });
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      const message =
        error.status === 409 && error.code === 'payment_required'
          ? 'Online payment for tickets is coming soon'
          : error.message;
      return json({ error: { code: error.code, message, details: error.details } }, error.status);
    }
    throw error;
  }
};
