import type { APIRoute } from 'astro';
import { getEnv } from '@lib/env';

export const prerender = false;

export const GET: APIRoute = (context) => {
  const env = getEnv(context);
  const origin = env.PUBLIC_SITE_URL || new URL(context.request.url).origin;
  const body = `User-agent: *
Allow: /
Disallow: /portal
Disallow: /cart
Disallow: /checkout
Disallow: /login
Disallow: /signup

Sitemap: ${origin}/sitemap.xml
`;
  return new Response(body, { headers: { 'Content-Type': 'text/plain' } });
};
