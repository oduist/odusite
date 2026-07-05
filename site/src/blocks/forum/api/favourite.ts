// POST /api/forum/favourite — toggle favourite on a question.
import type { APIRoute } from 'astro';
import { badRequest, proxyAction, readJson } from './_proxy';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const body = await readJson(context);
  const postId = Number(body?.post_id);
  if (!Number.isInteger(postId) || postId <= 0) {
    return badRequest('post_id is required.');
  }
  return proxyAction(context, `/forum/posts/${postId}/favourite`);
};
