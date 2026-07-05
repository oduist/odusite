// POST /api/forum/ask — create a question.
import type { APIRoute } from 'astro';
import { badRequest, proxyAction, readJson } from './_proxy';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const body = await readJson(context);
  const forumId = Number(body?.forum_id);
  const name = typeof body?.name === 'string' ? body.name.trim() : '';
  const content = typeof body?.content === 'string' ? body.content.trim() : '';
  const tags = Array.isArray(body?.tags)
    ? body.tags.filter((tag): tag is string => typeof tag === 'string' && tag.trim() !== '')
    : [];
  if (!Number.isInteger(forumId) || forumId <= 0 || !name || !content) {
    return badRequest('forum_id, name and content are required.');
  }
  return proxyAction(context, '/forum/posts', { forum_id: forumId, name, content, tags });
};
