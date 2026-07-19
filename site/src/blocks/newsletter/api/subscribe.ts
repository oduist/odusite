// Same-origin endpoint for the footer newsletter form.
//
// Receives {email, list_id?, website_hp?} JSON from the browser and forwards
// it to Odoo via apiFetch. Anti-abuse: the honeypot field (passed through —
// Odoo silently drops non-empty values) plus Turnstile when configured.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { getEnv } from '@lib/env';
import { enforceTurnstile } from '@lib/turnstile';

export const prerender = false;

function json(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function jsonError(status: number, code: string, message: string): Response {
  return json(status, { error: { code, message } });
}

export const POST: APIRoute = async (context) => {
  let body: Record<string, unknown>;
  try {
    body = (await context.request.json()) as Record<string, unknown>;
  } catch {
    return jsonError(400, 'bad_request', 'Expected a JSON body.');
  }

  // Anti-bot check comes first; fails closed when the widget is configured but
  // the secret is missing.
  const turnstileBlocked = await enforceTurnstile(
    getEnv(context),
    typeof body['cf-turnstile-response'] === 'string' ? (body['cf-turnstile-response'] as string) : null,
    context.request.headers.get('CF-Connecting-IP'),
    new URL(context.request.url).hostname,
  );
  if (turnstileBlocked) return turnstileBlocked;

  const text = (key: string): string =>
    typeof body[key] === 'string' ? (body[key] as string).trim() : '';

  const email = text('email');
  if (!email) {
    return jsonError(422, 'validation_error', 'Please enter your email address.');
  }

  const payload: Record<string, unknown> = {
    email,
    website_hp: text('website_hp'),
  };
  if (typeof body.list_id === 'number') payload.list_id = body.list_id;

  try {
    const data = await apiFetch<{ subscribed: boolean; list?: string }>(
      context,
      '/newsletter/subscribe',
      { method: 'POST', body: payload, auth: false, cart: false },
    );
    return json(200, { data });
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      const friendly =
        error.status === 422
          ? 'Please enter a valid email address.'
          : error.status === 404
            ? 'Newsletter subscription is not available right now.'
            : error.message;
      return jsonError(error.status, error.code, friendly);
    }
    throw error;
  }
};
