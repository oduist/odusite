// POST /api/auth/forgot — requests the stock Odoo reset email. Always
// redirects to the "sent" state (no account enumeration).
import type { APIRoute } from 'astro';
import { apiFetch } from '@lib/api/client';
import { redirect303 } from '../../lib';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData().catch(() => null);
  const login = form?.get('login');
  if (typeof login === 'string' && login) {
    try {
      await apiFetch(context, '/auth/password/forgot', {
        method: 'POST',
        body: { login },
        auth: false,
        cart: false,
      });
    } catch {
      // Deliberately swallowed — same response either way.
    }
  }
  return redirect303(context, '/reset?sent=1');
};
