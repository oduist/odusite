// GET /api/courses/binary/[courseId]/[slideId] — stream a slide's binary
// (document/infographic) through the site so the Odoo token never reaches
// the browser. Resolves the slide's binary_url first, then streams it.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import type { SlideContent } from '../../../types';

export const prerender = false;

/** Normalize binary_url to a path relative to /odusite/v1 (what apiFetch expects). */
function apiPath(binaryUrl: string): string {
  let path = binaryUrl;
  if (path.startsWith('http://') || path.startsWith('https://')) {
    const url = new URL(path);
    path = url.pathname + url.search;
  }
  if (path.startsWith('/odusite/v1')) path = path.slice('/odusite/v1'.length);
  return path;
}

export const GET: APIRoute = async (context) => {
  const courseId = Number(context.params.courseId);
  const slideId = Number(context.params.slideId);
  if (!Number.isInteger(courseId) || courseId <= 0 || !Number.isInteger(slideId) || slideId <= 0) {
    return new Response(null, { status: 400 });
  }

  try {
    const content = await apiFetch<SlideContent>(
      context,
      `/courses/${courseId}/slides/${slideId}`,
      { cart: false },
    );
    if (!content.binary_url) return new Response(null, { status: 404 });

    const upstream = await apiFetch<Response>(context, apiPath(content.binary_url), {
      raw: true,
      cart: false,
    });
    if (!upstream.ok) return new Response(null, { status: upstream.status });

    const headers = new Headers();
    for (const name of ['Content-Type', 'Content-Length', 'Content-Disposition']) {
      const value = upstream.headers.get(name);
      if (value) headers.set(name, value);
    }
    // Access depends on membership — never cache at the edge or share.
    headers.set('Cache-Control', 'private, max-age=0');
    return new Response(upstream.body, { status: 200, headers });
  } catch (error) {
    if (error instanceof OdusiteApiError) return new Response(null, { status: error.status });
    throw error;
  }
};
