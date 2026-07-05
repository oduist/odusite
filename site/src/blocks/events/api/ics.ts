// Same-origin ICS proxy: streams the Odoo calendar file for an event.
import type { APIRoute } from 'astro';
import { apiFetch } from '@lib/api/client';

export const prerender = false;

export const GET: APIRoute = async (context) => {
  const id = context.params.id ?? '';
  if (!/^\d+$/.test(id)) {
    return new Response(
      JSON.stringify({ error: { code: 'bad_request', message: 'Invalid event id' } }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }

  const upstream = await apiFetch<Response>(context, `/events/${id}/ics`, {
    raw: true,
    auth: false,
    cart: false,
  });

  if (!upstream.ok) {
    return new Response(null, { status: upstream.status === 404 ? 404 : 502 });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': upstream.headers.get('Content-Type') ?? 'text/calendar; charset=utf-8',
      'Content-Disposition': `attachment; filename="event-${id}.ics"`,
      'Cache-Control': 'public, max-age=0, s-maxage=600',
      'X-Odusite-Tags': `events,events:${id}`,
    },
  });
};
