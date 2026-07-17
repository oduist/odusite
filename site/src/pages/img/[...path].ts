// Image proxy: /img/** -> Odoo /web/image/** with edge caching (ADR-009).
import type { APIRoute } from 'astro';
import { getEnv, odooAccessHeaders } from '@lib/env';

export const prerender = false;

export const GET: APIRoute = async (context) => {
  const env = getEnv(context);
  const path = context.params.path ?? '';
  const upstream = new URL(`/web/image/${path}`, env.ODOO_URL);
  upstream.search = new URL(context.request.url).search;

  const cacheKey = new Request(context.request.url, { method: 'GET' });
  const cache = typeof caches !== 'undefined' ? await caches.open('odusite:img') : null;
  const hit = await cache?.match(cacheKey);
  if (hit) return hit;

  const response = await fetch(upstream, {
    headers: {
      Accept: context.request.headers.get('Accept') ?? 'image/*',
      ...odooAccessHeaders(env),
    },
  });
  if (!response.ok) {
    return new Response(null, { status: response.status });
  }

  const immutable = upstream.searchParams.has('unique');
  const headers = new Headers(response.headers);
  headers.set(
    'Cache-Control',
    immutable ? 'public, max-age=31536000, immutable' : 'public, max-age=86400',
  );
  headers.delete('Set-Cookie');
  const proxied = new Response(response.body, { status: 200, headers });

  if (cache) {
    const runtime = (context.locals as App.Locals).runtime;
    const store = cache.put(cacheKey, proxied.clone());
    runtime?.ctx?.waitUntil?.(store);
  }
  return proxied;
};
