// POST /api/auth/logout — revokes the refresh token in Odoo, clears the
// auth cookies and redirects home.
import type { APIRoute } from 'astro';
import { apiFetch } from '@lib/api/client';
import { clearAuthCookies, getRefreshToken } from '@lib/auth/session';
import { redirect303 } from '../../lib';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const refresh = getRefreshToken(context);
  if (refresh) {
    try {
      await apiFetch(context, '/auth/logout', {
        method: 'POST',
        body: { refresh_token: refresh },
        cart: false,
      });
    } catch {
      // Best effort — the cookies are cleared regardless.
    }
  }
  clearAuthCookies(context);
  return redirect303(context, '/');
};
