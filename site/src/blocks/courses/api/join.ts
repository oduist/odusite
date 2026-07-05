// POST /api/courses/join — join a public-enroll course.
import type { APIRoute } from 'astro';
import { badRequest, proxyAction, readJson } from './_proxy';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  const body = await readJson(context);
  const courseId = Number(body?.course_id);
  if (!Number.isInteger(courseId) || courseId <= 0) {
    return badRequest('course_id is required.');
  }
  return proxyAction(context, `/courses/${courseId}/join`);
};
