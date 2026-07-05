// POST /api/portal/orders/[id]/accept — form proxy for the stock sign flow:
// {name, signature (base64 PNG)} → POST /my/orders/<id>/accept.
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
  if (!form) return redirect303(context, `${page}?error=sign`);

  const name = form.get('name');
  let signature = form.get('signature');
  if (typeof signature === 'string' && signature.startsWith('data:')) {
    signature = signature.split(',')[1] ?? '';
  }

  if (typeof name !== 'string' || !name.trim() || typeof signature !== 'string' || !signature) {
    return redirect303(context, `${page}?error=sign`);
  }

  try {
    await apiFetch(context, `/my/orders/${id}/accept`, {
      method: 'POST',
      body: { name: name.trim(), signature },
    });
    return redirect303(context, `${page}?accepted=1`);
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 401) return redirect303(context, `/login?next=${encodeURIComponent(page)}`);
      return redirect303(context, `${page}?error=sign`);
    }
    throw error;
  }
};
