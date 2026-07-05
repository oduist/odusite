// Site-wide API calls (odusite_base endpoints) with per-isolate memo cache.
import type { APIContext, AstroGlobal } from 'astro';
import { apiFetch } from './client';

type Ctx = APIContext | AstroGlobal;

export interface SiteLanguage {
  code: string;
  url_code: string;
  name: string;
}

export interface SiteConfig {
  name: string;
  company: {
    name: string;
    street: string;
    street2: string;
    city: string;
    zip: string;
    country: string;
    email: string;
    phone: string;
    vat: string;
  };
  logo: string | null;
  favicon: string | null;
  social: Record<string, string | null>;
  languages: SiteLanguage[];
  default_language: string;
  currency: string;
}

export interface MenuItem {
  id: number;
  name: string;
  url: string;
  new_window: boolean;
  sequence: number;
  children: MenuItem[];
}

const memo = new Map<string, { value: unknown; expires: number }>();
const MEMO_TTL_MS = 5 * 60 * 1000;

async function memoized<T>(key: string, load: () => Promise<T>): Promise<T> {
  const hit = memo.get(key);
  if (hit && hit.expires > Date.now()) return hit.value as T;
  const value = await load();
  memo.set(key, { value, expires: Date.now() + MEMO_TTL_MS });
  return value;
}

export function getSiteConfig(ctx: Ctx): Promise<SiteConfig> {
  return memoized(`site:${ctx.locals.lang}`, () =>
    apiFetch<SiteConfig>(ctx, '/site', { auth: false, cart: false }),
  );
}

export function getMenus(ctx: Ctx): Promise<MenuItem[]> {
  return memoized(`menus:${ctx.locals.lang}`, () =>
    apiFetch<MenuItem[]>(ctx, '/menus', { auth: false, cart: false }),
  );
}

export function getSitemapEntries(ctx: Ctx): Promise<{ url: string; lastmod: string | null }[]> {
  return apiFetch(ctx, '/sitemap', { auth: false, cart: false });
}
