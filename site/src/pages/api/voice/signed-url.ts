// Token broker for the ElevenLabs voice assistant. The API key is server-side
// only; the browser calls this to get a short-lived signed WebSocket URL that
// already embeds the agent, so the key never ships to the client.
import type { APIRoute } from 'astro';
import { getEnv } from '@lib/env';

export const prerender = false;

const json = (body: unknown, status: number) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });

export const GET: APIRoute = async (ctx) => {
  const env = getEnv(ctx);
  if (!env.ELEVENLABS_API_KEY || !env.ELEVENLABS_AGENT_ID) {
    return json({ error: 'voice_not_configured' }, 503);
  }
  const url = new URL('https://api.elevenlabs.io/v1/convai/conversation/get-signed-url');
  url.searchParams.set('agent_id', env.ELEVENLABS_AGENT_ID);
  try {
    const resp = await fetch(url, { headers: { 'xi-api-key': env.ELEVENLABS_API_KEY } });
    if (!resp.ok) return json({ error: 'upstream_error' }, 502);
    const data = (await resp.json()) as { signed_url?: string };
    if (!data.signed_url) return json({ error: 'no_signed_url' }, 502);
    return json({ signed_url: data.signed_url }, 200);
  } catch {
    return json({ error: 'upstream_unreachable' }, 502);
  }
};
