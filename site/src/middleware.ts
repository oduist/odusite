import type { APIContext } from 'astro';
import { defineMiddleware } from 'astro:middleware';
import { getEnv, odooAccessHeaders } from './lib/env';
import { matchPage, storePage } from './lib/cache';
import { getLocaleInfo, splitLocale } from './lib/i18n';
import {
  COOKIES,
  decodeJwtPayload,
  getAccessToken,
  getRefreshToken,
  isJwtExpired,
  setAuthCookies,
  clearAuthCookies,
} from './lib/auth/session';

const LANG_MAX_AGE = 60 * 60 * 24 * 365;
// Requests that never carry a locale prefix (API proxies, image proxy, assets):
// skip locale resolution and just honour the cookie, so they don't pay a site
// config lookup or risk mis-parsing a path segment as a language.
const NON_PAGE = /^\/(api|img|_)|\.[a-z0-9]+$/i;

// Image proxy (/img/** -> Odoo /web/image/**, ADR-009). Handled in the
// middleware, before Astro route matching, so it never depends on rest-route
// priority (/img/[...path] vs the [...slug] catch-all) — that resolution proved
// unstable on Cloudflare and made images intermittently 404. Only the `unique`
// cache-buster is forwarded upstream (extra params make Odoo /web/image 500).
async function proxyImage(context: APIContext): Promise<Response> {
  const env = getEnv(context);
  const path = context.url.pathname.slice('/img/'.length);
  const upstream = new URL(`/web/image/${path}`, env.ODOO_URL);
  const unique = context.url.searchParams.get('unique');
  if (unique) upstream.searchParams.set('unique', unique);

  const cache = typeof caches !== 'undefined' ? await caches.open('odusite:img') : null;
  const cacheKey = new Request(context.request.url, { method: 'GET' });
  const hit = await cache?.match(cacheKey);
  if (hit) return hit;

  const response = await fetch(upstream, {
    headers: {
      Accept: context.request.headers.get('Accept') ?? 'image/*',
      ...odooAccessHeaders(env),
    },
  });
  if (!response.ok) return new Response(null, { status: response.status });

  const headers = new Headers(response.headers);
  headers.set(
    'Cache-Control',
    unique ? 'public, max-age=31536000, immutable' : 'public, max-age=86400',
  );
  headers.delete('Set-Cookie');
  const proxied = new Response(response.body, { status: 200, headers });
  if (cache) {
    const runtime = (context.locals as App.Locals).runtime;
    runtime?.ctx?.waitUntil?.(cache.put(cacheKey, proxied.clone()));
  }
  return proxied;
}

export const onRequest = defineMiddleware(async (context, next) => {
  const { cookies, locals, url } = context;

  // Image proxy: resolve before any routing/locale/auth work.
  if (url.pathname.startsWith('/img/') && context.request.method === 'GET') {
    return proxyImage(context);
  }

  // 1. Language + locale routing. A non-default language is a URL prefix
  //    (`/ru/...`): resolve it, remember it in the cookie so later unprefixed
  //    navigation stays localized, and strip it before route matching. The
  //    Odoo `lang` code drives every API response.
  let activePath = url.pathname;
  let rewritePath: string | undefined;
  if (NON_PAGE.test(url.pathname)) {
    const info = await getLocaleInfo(context);
    const cookieLang = cookies.get(COOKIES.lang)?.value;
    locals.lang = cookieLang && info.byCode.has(cookieLang) ? cookieLang : info.defaultCode;
    locals.locale = (info.byCode.get(locals.lang) ?? info.byCode.get(info.defaultCode))!.url_code;
  } else {
    const info = await getLocaleInfo(context);
    const { urlCode, rest } = splitLocale(url.pathname, info);
    if (urlCode) {
      const lang = info.byUrlCode.get(urlCode)!;
      locals.lang = lang.code;
      locals.locale = lang.url_code;
      cookies.set(COOKIES.lang, lang.code, {
        path: '/',
        maxAge: LANG_MAX_AGE,
        sameSite: 'lax',
      });
      if (urlCode === info.defaultUrlCode) {
        // The default language is canonical without a prefix. An explicit
        // `/en/...` is the "switch back to default" signal: remember it in the
        // cookie (above) and redirect to the clean path.
        return context.redirect(rest + url.search, 302);
      }
      activePath = rest;
      rewritePath = rest + url.search;
    } else {
      const cookieLang = cookies.get(COOKIES.lang)?.value;
      locals.lang = cookieLang && info.byCode.has(cookieLang) ? cookieLang : info.defaultCode;
      locals.locale = (info.byCode.get(locals.lang) ?? info.byCode.get(info.defaultCode))!.url_code;
    }
  }

  // 2. Auth: refresh the access token when expired and a refresh token exists.
  let access = getAccessToken(context);
  if (access && isJwtExpired(access)) {
    access = null;
    const refresh = getRefreshToken(context);
    if (refresh) {
      try {
        const env = getEnv(context);
        const response = await fetch(new URL('/odusite/v1/auth/refresh', env.ODOO_URL), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Odusite-Token': env.ODUSITE_TOKEN,
          },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (response.ok) {
          const { data } = (await response.json()) as {
            data: { access_token: string; refresh_token: string };
          };
          setAuthCookies(context, data.access_token, data.refresh_token);
          access = data.access_token;
        } else {
          clearAuthCookies(context);
        }
      } catch {
        clearAuthCookies(context);
      }
    }
  }
  if (access) {
    const payload = decodeJwtPayload(access);
    locals.user = payload
      ? {
          id: Number(payload.sub ?? 0),
          name: String(payload.name ?? ''),
          email: String(payload.email ?? ''),
        }
      : null;
  } else {
    locals.user = null;
  }

  // 3. Edge cache for anonymous visitors: pages opt in by setting
  //    s-maxage + X-Odusite-Tags headers (see lib/cache.ts).
  const isPrivate = /^\/(portal|cart|checkout|login|signup|reset|confirm)/.test(activePath);
  const anonymous = !access && !getRefreshToken(context) && !cookies.get(COOKIES.cart)?.value;
  // Never route NON_PAGE requests (the /img and /api proxies, assets) through the
  // page cache: they set their own caching, and sharing the page-cache keyspace
  // lets a query string (e.g. an image `?unique=` checksum) collide with a
  // stored page entry.
  const cacheable =
    context.request.method === 'GET' && !isPrivate && anonymous && !NON_PAGE.test(url.pathname);

  if (cacheable) {
    const hit = await matchPage(context);
    if (hit) {
      const response = new Response(hit.body, hit);
      response.headers.set('X-Odusite-Cache', 'hit');
      return response;
    }
  }

  let response = rewritePath ? await next(rewritePath) : await next();

  if (isPrivate) {
    response.headers.set('Cache-Control', 'private, no-store');
  } else if (
    cacheable &&
    response.ok &&
    /s-maxage=\d/.test(response.headers.get('Cache-Control') ?? '')
  ) {
    response = storePage(context, response);
  }
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  response.headers.set('X-Frame-Options', 'DENY');
  return response;
});
