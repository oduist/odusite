// Tagged edge caching (Cache API + KV tag index). See specs/06.
//
// Pages/endpoints opt in by setting response headers:
//   Astro.response.headers.set('Cache-Control', 'public, max-age=0, s-maxage=600');
//   Astro.response.headers.set('X-Odusite-Tags', 'blog,blog:42');
// The middleware stores/serves such responses for ANONYMOUS visitors only;
// /api/revalidate purges entries by tag.
import type { APIContext, AstroGlobal } from 'astro';
import { getEnv } from './env';

type Ctx = APIContext | AstroGlobal;

const CACHE_NAME = 'odusite:pages';
export const TAGS_HEADER = 'X-Odusite-Tags';

function cacheKey(url: URL, lang: string): Request {
  const normalized = new URL(url);
  // Localized responses must not collide: an anonymous visitor's language is a
  // cache dimension (the same path renders different content per `lang`).
  normalized.searchParams.set('__lang', lang);
  normalized.searchParams.sort();
  return new Request(normalized.toString(), { method: 'GET' });
}

export async function matchPage(ctx: Ctx): Promise<Response | undefined> {
  if (typeof caches === 'undefined') return undefined;
  const cache = await caches.open(CACHE_NAME);
  return cache.match(cacheKey(new URL(ctx.request.url), (ctx.locals as App.Locals).lang));
}

/** Store a cacheable response and index its tags. Returns the response to
 * send (the original — storing uses a clone in waitUntil). */
export function storePage(ctx: Ctx, response: Response): Response {
  if (typeof caches === 'undefined') return response;
  const clone = response.clone();
  const runtime = (ctx.locals as App.Locals).runtime;
  const url = cacheKey(new URL(ctx.request.url), (ctx.locals as App.Locals).lang).url;
  const tags = (response.headers.get(TAGS_HEADER) ?? '').split(',').filter(Boolean);
  const task = (async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.put(new Request(url), clone);
    await indexTags(ctx, tags, url);
  })();
  runtime?.ctx?.waitUntil?.(task);
  return response;
}

async function indexTags(ctx: Ctx, tags: string[], url: string): Promise<void> {
  const kv = getEnv(ctx).ODUSITE_CACHE_TAGS;
  if (!kv) return;
  for (const tag of tags) {
    const key = `tag:${tag}`;
    const existing = (await kv.get<string[]>(key, 'json')) ?? [];
    if (!existing.includes(url)) {
      existing.push(url);
      await kv.put(key, JSON.stringify(existing), { expirationTtl: 86400 });
    }
  }
}

export async function purgeTags(ctx: Ctx, tags: string[]): Promise<number> {
  const kv = getEnv(ctx).ODUSITE_CACHE_TAGS;
  if (typeof caches === 'undefined') return 0;
  const cache = await caches.open(CACHE_NAME);
  let purged = 0;

  let effective = tags;
  if (tags.includes('all')) {
    effective = kv ? (await kv.list({ prefix: 'tag:' })).keys.map((k) => k.name.slice(4)) : [];
  }
  for (const tag of effective) {
    const urls = kv ? ((await kv.get<string[]>(`tag:${tag}`, 'json')) ?? []) : [];
    for (const url of urls) {
      if (await cache.delete(new Request(url))) purged += 1;
    }
    await kv?.delete(`tag:${tag}`);
  }
  return purged;
}
