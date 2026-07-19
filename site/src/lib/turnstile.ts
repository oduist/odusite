// Cloudflare Turnstile server-side verification + enforcement.
//
// Shared infra (src/lib) so every block enforces the anti-bot check the same
// way. `enforceTurnstile` fails CLOSED: once the widget is configured
// (PUBLIC_TURNSTILE_SITE_KEY set), a missing secret or a missing/invalid token
// blocks the request instead of silently letting it through — the previous
// per-endpoint `if (env.TURNSTILE_SECRET_KEY)` gate skipped verification
// entirely when the secret was unset (fail-open on misconfiguration).
import type { OdusiteEnv } from './env';

const SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';

export interface TurnstileResult {
  ok: boolean;
  hostname: string | null;
  action: string | null;
  codes: string[];
}

/**
 * Whether Turnstile protection is expected for this deployment. Keyed on the
 * *site* key: that is the value that makes the widget render, so its presence
 * is the signal that submissions are meant to carry a token. (A secret without
 * a site key would render no widget, so enforcing it would break every form.)
 */
export function turnstileEnabled(env: Pick<OdusiteEnv, 'PUBLIC_TURNSTILE_SITE_KEY'>): boolean {
  return Boolean(env.PUBLIC_TURNSTILE_SITE_KEY);
}

/**
 * Verify a `cf-turnstile-response` token against Cloudflare siteverify.
 * Fails closed on a missing token or a network error.
 */
export async function verifyTurnstile(
  secret: string,
  token: string | null,
  remoteIp?: string | null,
): Promise<TurnstileResult> {
  if (!token) {
    return { ok: false, hostname: null, action: null, codes: ['missing-input-response'] };
  }
  const body = new URLSearchParams({ secret, response: token });
  if (remoteIp) body.set('remoteip', remoteIp);
  try {
    const response = await fetch(SITEVERIFY_URL, { method: 'POST', body });
    const result = (await response.json()) as {
      success?: boolean;
      hostname?: string;
      action?: string;
      'error-codes'?: string[];
    };
    return {
      ok: result.success === true,
      hostname: result.hostname ?? null,
      action: result.action ?? null,
      codes: result['error-codes'] ?? [],
    };
  } catch {
    return { ok: false, hostname: null, action: null, codes: ['siteverify-unreachable'] };
  }
}

function block(status: number, code: string, message: string): Response {
  return new Response(JSON.stringify({ error: { code, message } }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * Enforce Turnstile on a request. Returns a ready-to-return error `Response`
 * when the request must be rejected, or `null` when it may proceed.
 *
 *  - widget not configured (no site key) -> null   (feature off, allow)
 *  - site key set but secret missing     -> 503    (misconfig, fail CLOSED)
 *  - token missing / invalid             -> 403
 *  - token solved on a different host     -> 403    (token replay, see below)
 *  - token valid                         -> null
 *
 * `expectedHostname` should be the host the form was served from (the API is
 * same-origin, so `new URL(request.url).hostname`). Matching it against the
 * hostname Cloudflare reports blocks tokens minted on another site that shares
 * this secret. Skipped when either side is unknown, so test keys still pass.
 */
export async function enforceTurnstile(
  env: Pick<OdusiteEnv, 'PUBLIC_TURNSTILE_SITE_KEY' | 'TURNSTILE_SECRET_KEY'>,
  token: string | null,
  remoteIp?: string | null,
  expectedHostname?: string | null,
): Promise<Response | null> {
  if (!turnstileEnabled(env)) return null;
  if (!env.TURNSTILE_SECRET_KEY) {
    return block(
      503,
      'turnstile_misconfigured',
      'Anti-bot verification is temporarily unavailable. Please try again later.',
    );
  }
  const result = await verifyTurnstile(env.TURNSTILE_SECRET_KEY, token, remoteIp);
  const hostMismatch =
    Boolean(expectedHostname) && Boolean(result.hostname) && result.hostname !== expectedHostname;
  if (!result.ok || hostMismatch) {
    return block(
      403,
      'turnstile_failed',
      'Anti-bot verification failed. Please reload the page and try again.',
    );
  }
  return null;
}
