// Same-origin endpoint for the contact form.
//
// Receives a JSON body from the browser, verifies Turnstile first (when
// TURNSTILE_SECRET_KEY is configured; skipped when unset), then forwards the
// payload to Odoo via apiFetch, enriched with attribution meta (page + UTM
// values from the Referer / query string). The honeypot field (website_hp)
// is passed through — the Odoo side rejects non-empty values.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { getEnv } from '@lib/env';
import { verifyTurnstile } from '../lib/turnstile';
import type { ContactMeta, ContactPayload } from '../types';

export const prerender = false;

const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign'] as const;

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
  const env = getEnv(context);

  let body: Record<string, unknown>;
  try {
    body = (await context.request.json()) as Record<string, unknown>;
  } catch {
    return jsonError(400, 'bad_request', 'Expected a JSON body.');
  }

  const text = (key: string): string =>
    typeof body[key] === 'string' ? (body[key] as string).trim() : '';

  // Anti-bot check comes first; only forward verified submissions.
  if (env.TURNSTILE_SECRET_KEY) {
    const token = typeof body['cf-turnstile-response'] === 'string'
      ? (body['cf-turnstile-response'] as string)
      : null;
    const result = await verifyTurnstile(
      env.TURNSTILE_SECRET_KEY,
      token,
      context.request.headers.get('CF-Connecting-IP'),
    );
    if (!result.ok) {
      return jsonError(
        403,
        'turnstile_failed',
        'Anti-bot verification failed. Please reload the page and try again.',
      );
    }
  }

  const name = text('name');
  const email = text('email');
  const message = text('message');
  if (!name || !email || !message) {
    return jsonError(422, 'missing_fields', 'Please fill in your name, email and message.');
  }

  // Attribution meta: page from the Referer path, UTM values from the
  // Referer's query string (falling back to this request's own query).
  const meta: ContactMeta = {};
  let refererUrl: URL | null = null;
  const referer = context.request.headers.get('Referer');
  if (referer) {
    try {
      refererUrl = new URL(referer);
    } catch {
      refererUrl = null;
    }
  }
  if (refererUrl) meta.page = refererUrl.pathname;
  for (const key of UTM_KEYS) {
    const value = refererUrl?.searchParams.get(key) ?? context.url.searchParams.get(key);
    if (value) meta[key] = value;
  }

  const payload: ContactPayload = {
    name,
    email,
    message,
    website_hp: text('website_hp'),
  };
  const phone = text('phone');
  const company = text('company');
  const subject = text('subject');
  if (phone) payload.phone = phone;
  if (company) payload.company = company;
  if (subject) payload.subject = subject;
  if (Object.keys(meta).length > 0) payload.meta = meta;

  try {
    const data = await apiFetch<{ id: number }>(context, '/forms/contact', {
      method: 'POST',
      body: payload,
      auth: false,
      cart: false,
    });
    return json(200, { data });
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      const friendly =
        error.status === 422 ? 'Please fill in all required fields.' : error.message;
      return jsonError(error.status, error.code, friendly);
    }
    throw error;
  }
};
