// POST /api/auth/reset — sets a new password from a reset-email token.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { redirect303 } from '../../lib';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData().catch(() => null);
  if (!form) return redirect303(context, '/reset');

  const token = form.get('token');
  const password = form.get('password');
  const confirm = form.get('confirm');

  if (typeof token !== 'string' || !token) return redirect303(context, '/reset');
  const back = (error: string) => `/reset/${encodeURIComponent(token)}?error=${error}`;

  if (typeof password !== 'string' || !password) return redirect303(context, back('unknown'));
  if (password !== confirm) return redirect303(context, back('mismatch'));

  try {
    await apiFetch(context, '/auth/password/reset', {
      method: 'POST',
      body: { token, password },
      auth: false,
      cart: false,
    });
    return redirect303(context, '/login?reset=1');
  } catch (error) {
    if (error instanceof OdusiteApiError && error.status !== 500) {
      return redirect303(context, back('invalid'));
    }
    return redirect303(context, back('unknown'));
  }
};
