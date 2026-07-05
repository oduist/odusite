// POST /api/auth/resend — re-sends the email-confirmation link. Always
// redirects to the same "sent" state (backend never enumerates accounts).
import type { APIRoute } from 'astro';
import { apiFetch } from '@lib/api/client';
import { redirect303 } from '../../lib';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData().catch(() => null);
  const email = form?.get('email');
  if (typeof email === 'string' && email) {
    try {
      await apiFetch(context, '/auth/confirm/resend', {
        method: 'POST',
        body: { email },
        auth: false,
        cart: false,
      });
    } catch {
      // Deliberately swallowed — the response is identical either way.
    }
  }
  return redirect303(context, '/login?resent=1');
};
