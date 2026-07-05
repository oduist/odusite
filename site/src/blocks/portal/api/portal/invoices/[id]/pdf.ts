// GET /api/portal/invoices/[id]/pdf — streams the legal invoice PDF from
// Odoo (auth via the Bearer token attached from the session cookie).
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';

export const prerender = false;

export const GET: APIRoute = async (context) => {
  const id = context.params.id ?? '';
  if (!/^\d+$/.test(id)) return new Response('Not found', { status: 404 });
  if (!context.locals.user) {
    return context.redirect(`/login?next=${encodeURIComponent(`/portal/invoices/${id}`)}`, 303);
  }

  try {
    const upstream = await apiFetch<Response>(context, `/my/invoices/${id}/pdf`, { raw: true });
    if (!upstream.ok) {
      return new Response('Unable to fetch the document.', { status: upstream.status });
    }
    const headers = new Headers({
      'Content-Type': upstream.headers.get('Content-Type') ?? 'application/pdf',
      'Cache-Control': 'private, no-store',
    });
    const disposition = upstream.headers.get('Content-Disposition');
    if (disposition) headers.set('Content-Disposition', disposition);
    return new Response(upstream.body, { status: 200, headers });
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      return new Response('Unable to fetch the document.', { status: error.status });
    }
    throw error;
  }
};
