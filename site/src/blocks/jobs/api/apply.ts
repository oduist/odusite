// Same-origin endpoint for the job application form.
//
// Receives multipart FormData from the browser, verifies Turnstile first
// (when TURNSTILE_SECRET_KEY is configured; skipped when unset), then
// forwards the application to Odoo as multipart.
//
// apiFetch (@lib/api/client) is JSON-only, so the multipart forward is built
// manually below, copying the X-Odusite-Token / lang pattern from client.ts.
import type { APIRoute } from 'astro';
import { getEnv } from '@lib/env';
import { verifyTurnstile } from '../lib/turnstile';

export const prerender = false;

const CV_NAME_RE = /\.(pdf|docx?)$/i;
const OPTIONAL_FIELDS = ['linkedin', 'short_introduction'] as const;

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

  let form: FormData;
  try {
    form = await context.request.formData();
  } catch {
    return jsonError(400, 'bad_request', 'Expected multipart form data.');
  }

  // Anti-bot check comes first; only forward verified submissions.
  if (env.TURNSTILE_SECRET_KEY) {
    const token = form.get('cf-turnstile-response');
    const result = await verifyTurnstile(
      env.TURNSTILE_SECRET_KEY,
      typeof token === 'string' ? token : null,
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

  const text = (key: string): string => {
    const value = form.get(key);
    return typeof value === 'string' ? value.trim() : '';
  };

  const jobId = Number.parseInt(text('job_id'), 10);
  if (!Number.isInteger(jobId) || jobId <= 0) {
    return jsonError(400, 'bad_request', 'Missing job reference.');
  }

  const name = text('name');
  const email = text('email');
  const phone = text('phone');
  const cv = form.get('cv');
  if (!name || !email || !phone || !(cv instanceof File) || cv.size === 0) {
    return jsonError(
      422,
      'missing_fields',
      'Please fill in your name, email and phone, and attach a CV.',
    );
  }
  if (!CV_NAME_RE.test(cv.name)) {
    return jsonError(422, 'invalid_cv', 'The CV must be a PDF or Word document (.pdf, .doc, .docx).');
  }

  // Manual multipart forward to Odoo — same token/lang pattern as apiFetch.
  // Only whitelisted fields are forwarded (Turnstile token, honeypots and
  // anything else the browser sent are dropped).
  const url = new URL(`/odusite/v1/jobs/${jobId}/apply`, env.ODOO_URL);
  url.searchParams.set('lang', context.locals.lang ?? 'en_US');

  const outbound = new FormData();
  outbound.set('name', name);
  outbound.set('email', email);
  outbound.set('phone', phone);
  for (const field of OPTIONAL_FIELDS) {
    const value = text(field);
    if (value) outbound.set(field, value);
  }
  outbound.set('cv', cv, cv.name);

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'X-Odusite-Token': env.ODUSITE_TOKEN },
    body: outbound,
  });

  let payload: Record<string, unknown>;
  try {
    payload = (await response.json()) as Record<string, unknown>;
  } catch {
    return jsonError(502, 'bad_gateway', 'Invalid response from the backend.');
  }

  if (!response.ok || payload.error) {
    const error = (payload.error ?? {}) as { code?: string; message?: string };
    const code = error.code ?? 'internal';
    if (response.status === 409 || code === 'already_applied') {
      return jsonError(
        409,
        'already_applied',
        'You have already applied for this position recently — your application is on file.',
      );
    }
    return jsonError(
      response.ok ? 502 : response.status,
      code,
      error.message ?? 'Could not submit your application. Please try again later.',
    );
  }

  return json(200, { data: payload.data ?? { ok: true } });
};
