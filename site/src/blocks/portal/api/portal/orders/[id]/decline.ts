// POST /api/portal/orders/[id]/decline — form proxy: {reason} →
// POST /my/orders/<id>/decline (cancel + chatter message).
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { redirect303 } from '../../../../lib';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const id = context.params.id ?? '';
  if (!/^\d+$/.test(id)) return new Response('Not found', { status: 404 });
  const page = `/portal/orders/${id}`;
  if (!context.locals.user) return redirect303(context, `/login?next=${encodeURIComponent(page)}`);

  const form = await context.request.formData().catch(() => null);
  const reason = form?.get('reason');
  if (typeof reason !== 'string' || !reason.trim()) {
    return redirect303(context, `${page}?error=decline`);
  }

  try {
    await apiFetch(context, `/my/orders/${id}/decline`, {
      method: 'POST',
      body: { reason: reason.trim() },
    });
    return redirect303(context, `${page}?declined=1`);
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 401) return redirect303(context, `/login?next=${encodeURIComponent(page)}`);
      return redirect303(context, `${page}?error=decline`);
    }
    throw error;
  }
};
