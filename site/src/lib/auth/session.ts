// Cookie-based session helpers (see specs/01-architecture.md).
// Cookies: od_access (JWT, 15 min), od_refresh (30 d), od_cart, od_lang.
import type { APIContext, AstroGlobal } from 'astro';

type Ctx = APIContext | AstroGlobal;

const SECURE = import.meta.env.PROD;

export const COOKIES = {
  access: 'od_access',
  refresh: 'od_refresh',
  cart: 'od_cart',
  lang: 'od_lang',
} as const;

export function getAccessToken(ctx: Ctx): string | null {
  return ctx.cookies.get(COOKIES.access)?.value ?? null;
}

export function getRefreshToken(ctx: Ctx): string | null {
  return ctx.cookies.get(COOKIES.refresh)?.value ?? null;
}

export function getCartBinding(ctx: Ctx): { id: number; token: string } | null {
  const raw = ctx.cookies.get(COOKIES.cart)?.value;
  if (!raw) return null;
  const [id, token] = raw.split(':');
  if (!id || !token || !/^\d+$/.test(id)) return null;
  return { id: Number(id), token };
}

export function setCartBinding(ctx: Ctx, id: number, token: string): void {
  ctx.cookies.set(COOKIES.cart, `${id}:${token}`, {
    httpOnly: true,
    secure: SECURE,
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 24 * 90,
  });
}

export function clearCartBinding(ctx: Ctx): void {
  ctx.cookies.delete(COOKIES.cart, { path: '/' });
}

export function setAuthCookies(ctx: Ctx, accessToken: string, refreshToken: string): void {
  ctx.cookies.set(COOKIES.access, accessToken, {
    httpOnly: true,
    secure: SECURE,
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 15,
  });
  ctx.cookies.set(COOKIES.refresh, refreshToken, {
    httpOnly: true,
    secure: SECURE,
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 24 * 30,
  });
}

export function clearAuthCookies(ctx: Ctx): void {
  ctx.cookies.delete(COOKIES.access, { path: '/' });
  ctx.cookies.delete(COOKIES.refresh, { path: '/' });
}

/** Decode a JWT payload WITHOUT verification — for UI decisions only.
 * Odoo verifies the signature on every API call. */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const segment = token.split('.')[1];
  if (!segment) return null;
  try {
    const base64 = segment.replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

function base64UrlToBytes(segment: string): ArrayBuffer {
  const base64 = segment.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

/**
 * Verify an HS256 access token against the shared Odoo secret and return its
 * payload, or `null` when the signature/type/expiry is invalid. Mirrors
 * odusite_base/lib/jwt.py: HMAC-SHA256 is always computed before the payload is
 * trusted, so a forged `alg:none`/unsigned token is rejected.
 */
export async function verifyAccessToken(
  token: string,
  secret: string,
): Promise<Record<string, unknown> | null> {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  const [header, payload, signature] = parts;
  try {
    const key = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(secret),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['verify'],
    );
    const valid = await crypto.subtle.verify(
      'HMAC',
      key,
      base64UrlToBytes(signature),
      new TextEncoder().encode(`${header}.${payload}`),
    );
    if (!valid) return null;
    const claims = JSON.parse(new TextDecoder().decode(base64UrlToBytes(payload))) as Record<
      string,
      unknown
    >;
    if (claims.typ !== 'access') return null;
    if (typeof claims.exp === 'number' && Date.now() / 1000 > claims.exp) return null;
    return claims;
  } catch {
    return null;
  }
}

export function isJwtExpired(token: string, skewSeconds = 30): boolean {
  const payload = decodeJwtPayload(token);
  const exp = typeof payload?.exp === 'number' ? payload.exp : 0;
  return Date.now() / 1000 > exp - skewSeconds;
}
