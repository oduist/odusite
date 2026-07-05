// POST /api/courses/complete — mark a slide completed (member only).
import type { APIRoute } from 'astro';
import { badRequest, proxyAction, readJson } from './_proxy';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const body = await readJson(context);
  const courseId = Number(body?.course_id);
  const slideId = Number(body?.slide_id);
  if (!Number.isInteger(courseId) || courseId <= 0 || !Number.isInteger(slideId) || slideId <= 0) {
    return badRequest('course_id and slide_id are required.');
  }
  return proxyAction(context, `/courses/${courseId}/slides/${slideId}/complete`);
};
