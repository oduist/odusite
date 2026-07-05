// Cloudflare Turnstile server-side verification (siteverify).
//
// NOTE: deliberately duplicated in blocks/jobs/lib/turnstile.ts — blocks
// must not import from each other (block contract, specs/site/01-blocks.md),
// and the helper is small enough that a copy beats a cross-block dependency.

const SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';

export interface TurnstileResult {
  ok: boolean;
  codes: string[];
}

/**
 * Verify a `cf-turnstile-response` token. Callers should only invoke this
 * when TURNSTILE_SECRET_KEY is configured; when the key is unset the check
 * is skipped entirely.
 */
export async function verifyTurnstile(
  secret: string,
  token: string | null,
  remoteIp?: string | null,
): Promise<TurnstileResult> {
  if (!token) return { ok: false, codes: ['missing-input-response'] };
  const body = new URLSearchParams({ secret, response: token });
  if (remoteIp) body.set('remoteip', remoteIp);
  try {
    const response = await fetch(SITEVERIFY_URL, { method: 'POST', body });
    const result = (await response.json()) as {
      success?: boolean;
      'error-codes'?: string[];
    };
    return { ok: result.success === true, codes: result['error-codes'] ?? [] };
  } catch {
    return { ok: false, codes: ['siteverify-unreachable'] };
  }
}
