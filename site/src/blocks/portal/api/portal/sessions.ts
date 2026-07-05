// POST /api/portal/sessions — form proxy for DELETE /me/sessions
// (revoke one refresh-token session by id, or all with all=1).
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { redirect303 } from '../../lib';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  if (!context.locals.user) return redirect303(context, '/login?next=%2Fportal%2Fsecurity');

  const form = await context.request.formData().catch(() => null);
  if (!form) return redirect303(context, '/portal/security');

  const id = form.get('id');
  const all = form.get('all') === '1';
  const body: Record<string, unknown> = {};
  if (all) {
    body.all = true;
  } else if (typeof id === 'string' && /^\d+$/.test(id)) {
    body.id = Number(id);
  } else {
    return redirect303(context, '/portal/security');
  }

  try {
    await apiFetch(context, '/me/sessions', { method: 'DELETE', body });
    return redirect303(context, '/portal/security?revoked=1');
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 401) return redirect303(context, '/login?next=%2Fportal%2Fsecurity');
      return redirect303(context, '/portal/security');
    }
    throw error;
  }
};
