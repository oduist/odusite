import { defineMiddleware } from 'astro:middleware';
import { getEnv } from './lib/env';
import { matchPage, storePage } from './lib/cache';
import {
  COOKIES,
  decodeJwtPayload,
  getAccessToken,
  getRefreshToken,
  isJwtExpired,
  setAuthCookies,
  clearAuthCookies,
} from './lib/auth/session';

const DEFAULT_LANG = 'en_US';

export const onRequest = defineMiddleware(async (context, next) => {
  const { cookies, locals, url } = context;

  // 1. Language: cookie choice, else default. (URL-prefix routing arrives
  //    with the i18n pass; the cookie keeps API responses localized already.)
  locals.lang = cookies.get(COOKIES.lang)?.value ?? DEFAULT_LANG;

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
  const isPrivate = /^\/(portal|cart|checkout|login|signup|reset)/.test(url.pathname);
  const anonymous = !access && !getRefreshToken(context) && !cookies.get(COOKIES.cart)?.value;
  const cacheable = context.request.method === 'GET' && !isPrivate && anonymous;

  if (cacheable) {
    const hit = await matchPage(context);
    if (hit) {
      const response = new Response(hit.body, hit);
      response.headers.set('X-Odusite-Cache', 'hit');
      return response;
    }
  }

  let response = await next();

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
