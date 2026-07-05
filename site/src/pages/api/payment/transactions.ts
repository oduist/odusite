// Same-origin proxy: create a payment transaction (specs/04-payments.md).
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  let body: unknown;
  try {
    body = await context.request.json();
  } catch {
    return new Response(JSON.stringify({ error: { code: 'bad_request' } }), { status: 400 });
  }
  try {
    const data = await apiFetch(context, '/payment/transactions', { method: 'POST', body });
    return new Response(JSON.stringify({ data }), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      return new Response(
        JSON.stringify({ error: { code: error.code, message: error.message, details: error.details } }),
        { status: error.status, headers: { 'Content-Type': 'application/json' } },
      );
    }
    throw error;
  }
};
