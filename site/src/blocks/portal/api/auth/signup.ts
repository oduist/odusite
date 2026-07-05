// POST /api/auth/signup — b2c signup. On success we sign the user in
// directly (login with the just-created credentials) and land on ?next=.
// 409 (email exists) and 403 (signup disabled) map to friendly errors.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { setAuthCookies } from '@lib/auth/session';
import { redirect303, safePath } from '../../lib';
import type { AuthTokens } from '../../types';

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
    await apiFetch(context, '/auth/signup', {
      method: 'POST',
      body: { name, email, password },
      auth: false,
      cart: false,
    });
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 409) return redirect303(context, back('exists'));
      if (error.status === 403) return redirect303(context, back('disabled'));
      if (error.status === 422 || error.status === 400) return redirect303(context, back('validation'));
    }
    return redirect303(context, back('unknown'));
  }

  // Signup succeeded — obtain a token pair right away.
  try {
    const tokens = await apiFetch<AuthTokens>(context, '/auth/login', {
      method: 'POST',
      body: { login: email, password },
      auth: false,
      cart: false,
    });
    setAuthCookies(context, tokens.access_token, tokens.refresh_token);
    return redirect303(context, next);
  } catch {
    return redirect303(context, '/login?signup=1');
  }
};
