// POST /api/auth/signup — b2c signup with email double opt-in. On success the
// backend creates an inactive account and emails a confirmation link, then
// returns {status:'confirmation_sent', email}; we land on the "check your
// email" state. 409 (email exists) and 403 (signup disabled) map to friendly
// errors. (An invited signup, not reachable from this public form, would
// return a token pair — handled defensively.)
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { setAuthCookies } from '@lib/auth/session';
import { redirect303, safePath } from '../../lib';
import type { AuthTokens } from '../../types';

interface SignupResult extends Partial<AuthTokens> {
  status?: string;
  email?: string;
}

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData().catch(() => null);
  if (!form) return redirect303(context, '/signup?error=unknown');

  const name = form.get('name');
  const email = form.get('email');
  const password = form.get('password');
  const next = safePath(form.get('next'), '/portal');
  const back = (error: string) =>
    `/signup?error=${error}${next !== '/portal' ? `&next=${encodeURIComponent(next)}` : ''}`;

  if (
    typeof name !== 'string' ||
    typeof email !== 'string' ||
    typeof password !== 'string' ||
    !name ||
    !email ||
    !password
  ) {
    return redirect303(context, back('validation'));
  }

  try {
    const result = await apiFetch<SignupResult>(context, '/auth/signup', {
      method: 'POST',
      body: { name, email, password },
      auth: false,
      cart: false,
    });
    // Invited signups return a token pair (auto-login); the b2c double
    // opt-in path returns confirmation_sent (no tokens).
    const access = result.access_token;
    const refresh = result.refresh_token;
    if (typeof access === 'string' && typeof refresh === 'string') {
      setAuthCookies(context, access, refresh);
      return redirect303(context, next);
    }
    const confirmEmail = typeof result.email === 'string' ? result.email : email;
    return redirect303(context, `/signup?sent=1&email=${encodeURIComponent(confirmEmail)}`);
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 409) return redirect303(context, back('exists'));
      if (error.status === 403) return redirect303(context, back('disabled'));
      if (error.status === 422 || error.status === 400) return redirect303(context, back('validation'));
    }
    return redirect303(context, back('unknown'));
  }
};
