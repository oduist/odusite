// POST /api/auth/login — form target. Verifies credentials against Odoo,
// sets the auth cookies and redirects (303) to ?next= or /portal.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { setAuthCookies } from '@lib/auth/session';
import { redirect303, safePath } from '../../lib';
import type { AuthTokens } from '../../types';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData().catch(() => null);
  if (!form) return redirect303(context, '/login?error=unknown');

  const login = form.get('login');
  const password = form.get('password');
  const next = safePath(form.get('next'), '/portal');
  const back = (error: string) =>
    `/login?error=${error}${next !== '/portal' ? `&next=${encodeURIComponent(next)}` : ''}`;

  if (typeof login !== 'string' || typeof password !== 'string' || !login || !password) {
    return redirect303(context, back('credentials'));
  }

  try {
    const tokens = await apiFetch<AuthTokens>(context, '/auth/login', {
      method: 'POST',
      body: { login, password },
      auth: false,
      cart: false,
    });
    setAuthCookies(context, tokens.access_token, tokens.refresh_token);
    return redirect303(context, next);
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 409) return redirect303(context, back('mfa'));
      if (error.status === 401 || error.status === 403 || error.status === 422) {
        return redirect303(context, back('credentials'));
      }
    }
    return redirect303(context, back('unknown'));
  }
};
