// Cache-invalidation webhook receiver (Odoo -> site). See specs/06.
import type { APIRoute } from 'astro';
import { getEnv } from '@lib/env';
import { purgeTags } from '@lib/cache';

export const prerender = false;

async function hmacHex(secret: string, body: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const signature = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(body));
  return [...new Uint8Array(signature)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export const POST: APIRoute = async (context) => {
  const env = getEnv(context);
  if (!env.ODUSITE_REVALIDATE_SECRET) {
    return new Response(JSON.stringify({ error: 'not_configured' }), { status: 503 });
  }
  const body = await context.request.text();
  const provided = context.request.headers.get('X-Odusite-Signature') ?? '';
  const expected = await hmacHex(env.ODUSITE_REVALIDATE_SECRET, body);
  if (!timingSafeEqual(provided, expected)) {
    return new Response(JSON.stringify({ error: 'invalid_signature' }), { status: 401 });
  }

  let events: { tags?: string[] }[];
  try {
    events = (JSON.parse(body) as { events?: { tags?: string[] }[] }).events ?? [];
  } catch {
    return new Response(JSON.stringify({ error: 'bad_request' }), { status: 400 });
  }

  const tags = [...new Set(events.flatMap((event) => event.tags ?? []))];
  const purged = await purgeTags(context, tags);
  return new Response(JSON.stringify({ ok: true, tags, purged }), {
    headers: { 'Content-Type': 'application/json' },
  });
};
