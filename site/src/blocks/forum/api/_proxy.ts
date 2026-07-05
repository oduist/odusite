// Shared helpers for the forum same-origin action endpoints (not a route —
// only files listed in manifest.mjs are injected).
import type { APIContext } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export function loginRequired(): Response {
  return json({ error: { code: 'login_required', message: 'Sign in to continue.' } }, 401);
}

export function badRequest(message: string): Response {
  return json({ error: { code: 'bad_request', message } }, 400);
}

export async function readJson(context: APIContext): Promise<Record<string, unknown> | null> {
  try {
    const body = (await context.request.json()) as unknown;
    return body && typeof body === 'object' ? (body as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/** Thin proxy for a POST action on the Odoo forum API. 401 becomes
 * `login_required`; 403 `karma_required` (message + details) and every other
 * API error pass through with their status. */
export async function proxyAction(
  context: APIContext,
  path: string,
  body?: Record<string, unknown>,
): Promise<Response> {
  if (!context.locals.user) return loginRequired();
  try {
    const data = await apiFetch<unknown>(context, path, { method: 'POST', body, cart: false });
    return json({ data: data ?? { ok: true } });
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 401) return loginRequired();
      return json(
        { error: { code: error.code, message: error.message, details: error.details } },
        error.status,
      );
    }
    throw error;
  }
}
