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
import { enforceTurnstile } from '@lib/turnstile';

export const prerender = false;

const CV_NAME_RE = /\.(pdf|docx?)$/i;
const MAX_CV_BYTES = 10 * 1024 * 1024;
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

  // Anti-bot check comes first; only forward verified submissions. Fails
  // closed when the widget is configured but the secret is missing.
  const token = form.get('cf-turnstile-response');
  const turnstileBlocked = await enforceTurnstile(
    env,
    typeof token === 'string' ? token : null,
    context.request.headers.get('CF-Connecting-IP'),
    new URL(context.request.url).hostname,
  );
  if (turnstileBlocked) return turnstileBlocked;

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
  if (cv.size > MAX_CV_BYTES) {
    return jsonError(413, 'cv_too_large', 'The CV must be under 10 MB.');
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

  const applyHeaders: Record<string, string> = { 'X-Odusite-Token': env.ODUSITE_TOKEN };
  const clientIp = context.request.headers.get('CF-Connecting-IP');
  if (clientIp) applyHeaders['CF-Connecting-IP'] = clientIp;

  const response = await fetch(url, {
    method: 'POST',
    headers: applyHeaders,
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
