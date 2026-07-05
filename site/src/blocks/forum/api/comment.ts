// POST /api/forum/comment — comment on a question or an answer.
import type { APIRoute } from 'astro';
import { badRequest, proxyAction, readJson } from './_proxy';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const body = await readJson(context);
  const postId = Number(body?.post_id);
  const content = typeof body?.content === 'string' ? body.content.trim() : '';
  if (!Number.isInteger(postId) || postId <= 0 || !content) {
    return badRequest('post_id and content are required.');
  }
  return proxyAction(context, `/forum/posts/${postId}/comments`, { content });
};
