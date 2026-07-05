// POST /api/auth/confirm — confirms an email address from the double
// opt-in link. On success sets the auth cookies (auto-login) and lands on
// /portal; on failure bounces back to /confirm/<token> with an error so the
// page can offer a resend.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { setAuthCookies } from '@lib/auth/session';
import { redirect303 } from '../../lib';
import type { AuthTokens } from '../../types';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData().catch(() => null);
  const token = form?.get('token');
  if (typeof token !== 'string' || !token) return redirect303(context, '/login');
  const back = (error: string) => `/confirm/${encodeURIComponent(token)}?error=${error}`;

  try {
    const tokens = await apiFetch<AuthTokens>(context, '/auth/confirm', {
      method: 'POST',
      body: { token },
      auth: false,
      cart: false,
    });
    setAuthCookies(context, tokens.access_token, tokens.refresh_token);
    return redirect303(context, '/portal');
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 401) return redirect303(context, back('expired'));
      if (error.status === 400) return redirect303(context, back('invalid'));
    }
    return redirect303(context, back('unknown'));
  }
};
