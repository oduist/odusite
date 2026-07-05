// POST /api/forum/vote — vote on a question or an answer (1, -1, 0 = retract).
import type { APIRoute } from 'astro';
import { badRequest, proxyAction, readJson } from './_proxy';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const body = await readJson(context);
  const postId = Number(body?.post_id);
  const vote = Number(body?.vote);
  if (!Number.isInteger(postId) || postId <= 0 || ![-1, 0, 1].includes(vote)) {
    return badRequest('post_id and vote (1, -1 or 0) are required.');
  }
  return proxyAction(context, `/forum/posts/${postId}/vote`, { vote });
};
