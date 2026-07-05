// POST /api/portal/chatter — form proxy posting a message to
// /odusite/v1/chatter/<model>/<id>/messages. Only whitelisted portal
// document models are accepted.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { redirect303, safePath } from '../../lib';

export const prerender = false;

const MODELS = new Set(['sale.order', 'account.move', 'project.task', 'project.project']);

export const POST: APIRoute = async (context) => {
  if (!context.locals.user) return redirect303(context, '/login');

  const form = await context.request.formData().catch(() => null);
  if (!form) return redirect303(context, '/portal');

  const model = form.get('model');
  const id = form.get('id');
  const body = form.get('body');
  const back = safePath(form.get('return'), '/portal');
  const separator = back.includes('?') ? '&' : '?';

  if (
    typeof model !== 'string' ||
    !MODELS.has(model) ||
    typeof id !== 'string' ||
    !/^\d+$/.test(id) ||
    typeof body !== 'string' ||
    !body.trim()
  ) {
    return redirect303(context, `${back}${separator}error=chatter#chatter`);
  }

  try {
    await apiFetch(context, `/chatter/${model}/${id}/messages`, {
      method: 'POST',
      body: { body: body.trim() },
    });
    return redirect303(context, `${back}${separator}posted=1#chatter`);
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 401) return redirect303(context, `/login?next=${encodeURIComponent(back)}`);
      return redirect303(context, `${back}${separator}error=chatter#chatter`);
    }
    throw error;
  }
};
