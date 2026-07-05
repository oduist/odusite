// POST /api/portal/password — form proxy for PUT /me/password. Odoo revokes
// all other refresh tokens on success; the current session stays valid.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { packFormError, redirect303 } from '../../lib';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  if (!context.locals.user) return redirect303(context, '/login?next=%2Fportal%2Fsecurity');

  const form = await context.request.formData().catch(() => null);
  if (!form) return redirect303(context, '/portal/security');

  const oldPassword = form.get('old_password');
  const newPassword = form.get('new_password');
  const confirm = form.get('confirm');

  if (typeof oldPassword !== 'string' || typeof newPassword !== 'string' || !oldPassword || !newPassword) {
    return redirect303(context, '/portal/security?error=mismatch');
  }
  if (newPassword !== confirm) {
    return redirect303(context, '/portal/security?error=mismatch');
  }

  try {
    await apiFetch(context, '/me/password', {
      method: 'PUT',
      body: { old_password: oldPassword, new_password: newPassword },
    });
    return redirect303(context, '/portal/security?changed=1');
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 401) return redirect303(context, '/login?next=%2Fportal%2Fsecurity');
      return redirect303(context, `/portal/security?err=${packFormError(error)}`);
    }
    throw error;
  }
};
