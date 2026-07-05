// GET  /api/courses/quiz?course_id=&slide_id= — quiz questions (no correctness).
// POST /api/courses/quiz — submit answers {course_id, slide_id, answers}.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { badRequest, errorResponse, json, proxyAction, readJson } from './_proxy';

export const prerender = false;

export const GET: APIRoute = async (context) => {
  const courseId = Number(context.url.searchParams.get('course_id'));
  const slideId = Number(context.url.searchParams.get('slide_id'));
  if (!Number.isInteger(courseId) || courseId <= 0 || !Number.isInteger(slideId) || slideId <= 0) {
    return badRequest('course_id and slide_id query params are required.');
  }
  try {
    const data = await apiFetch<unknown>(
      context,
      `/courses/${courseId}/slides/${slideId}/quiz`,
      { cart: false },
    );
    return json({ data });
  } catch (error) {
    if (error instanceof OdusiteApiError) return errorResponse(error);
    throw error;
  }
};

export const POST: APIRoute = async (context) => {
  const body = await readJson(context);
  const courseId = Number(body?.course_id);
  const slideId = Number(body?.slide_id);
  const answers = body?.answers;
  if (
    !Number.isInteger(courseId) ||
    courseId <= 0 ||
    !Number.isInteger(slideId) ||
    slideId <= 0 ||
    !answers ||
    typeof answers !== 'object' ||
    Array.isArray(answers)
  ) {
    return badRequest('course_id, slide_id and answers are required.');
  }
  return proxyAction(context, `/courses/${courseId}/slides/${slideId}/quiz`, {
    answers: answers as Record<string, unknown>,
  });
};
