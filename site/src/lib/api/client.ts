// Typed Odoo API client. Server-side only — the token must never reach the
// browser. Browser islands call same-origin /api/* endpoints instead.
import type { APIContext, AstroGlobal } from 'astro';
import { getEnv } from '../env';
import { getAccessToken, getCartBinding } from '../auth/session';

export class OdusiteApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

export interface ListMeta {
  total: number;
  page: number;
  limit: number;
  pages: number;
  [key: string]: unknown;
}

export interface ApiListResult<T> {
  data: T[];
  meta: ListMeta;
}

type Ctx = APIContext | AstroGlobal;

interface ApiFetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  /** Extra query params appended to the URL. */
  query?: Record<string, string | number | undefined>;
  /** Attach the user's Bearer token (default: true when present). */
  auth?: boolean;
  /** Attach the guest cart header (default: true when present). */
  cart?: boolean;
  /** Return the raw Response (binary streams). */
  raw?: boolean;
}

export async function apiFetch<T = unknown>(
  ctx: Ctx,
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const env = getEnv(ctx);
  const url = new URL(`/odusite/v1${path}`, env.ODOO_URL);
  url.searchParams.set('lang', ctx.locals.lang ?? 'en_US');
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }

  const headers: Record<string, string> = {
    'X-Odusite-Token': env.ODUSITE_TOKEN,
    'Content-Type': 'application/json',
  };
  if (options.auth !== false) {
    const token = getAccessToken(ctx);
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }
  if (options.cart !== false) {
    const cart = getCartBinding(ctx);
    if (cart) headers['X-Odusite-Cart'] = `${cart.id}:${cart.token}`;
  }

  const response = await fetch(url, {
    method: options.method ?? 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (options.raw) return response as unknown as T;

  if (response.status === 204) return undefined as T;

  let payload: Record<string, unknown>;
  try {
    payload = (await response.json()) as Record<string, unknown>;
  } catch {
    throw new OdusiteApiError(response.status, 'bad_gateway', 'Invalid response from Odoo');
  }

  if (!response.ok || payload.error) {
    const error = (payload.error ?? {}) as {
      code?: string;
      message?: string;
      details?: Record<string, unknown>;
    };
    throw new OdusiteApiError(
      response.status,
      error.code ?? 'internal',
      error.message ?? 'Unknown error',
      error.details ?? {},
    );
  }

  if ('meta' in payload) {
    return { data: payload.data, meta: payload.meta } as T;
  }
  return payload.data as T;
}

/** Rewrite Odoo-relative image URLs (/web/image/...) to the /img proxy. */
export function imgUrl(odooPath: string | null | undefined): string | null {
  if (!odooPath) return null;
  return odooPath.startsWith('/web/image')
    ? odooPath.replace('/web/image', '/img')
    : odooPath;
}
