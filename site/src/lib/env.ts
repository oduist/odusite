// workers-types are imported (not global): their HTMLRewriter Element/Response
// globals would clash with DOM types used by client scripts.
import type { KVNamespace } from '@cloudflare/workers-types';
import type { APIContext, AstroGlobal } from 'astro';

export interface OdusiteEnv {
  ODOO_URL: string;
  ODUSITE_TOKEN: string;
  ODUSITE_REVALIDATE_SECRET: string;
  PUBLIC_SITE_URL: string;
  TURNSTILE_SECRET_KEY?: string;
  PUBLIC_TURNSTILE_SITE_KEY?: string;
  ODUSITE_CACHE_TAGS?: KVNamespace;
}

type Ctx = APIContext | AstroGlobal;

/** Runtime env: Cloudflare bindings in production, import.meta.env in dev. */
export function getEnv(ctx: Ctx): OdusiteEnv {
  const runtime = (ctx.locals as App.Locals).runtime;
  const cf = (runtime?.env ?? {}) as Partial<OdusiteEnv>;
  return {
    ODOO_URL: cf.ODOO_URL ?? import.meta.env.ODOO_URL ?? 'http://localhost:8069',
    ODUSITE_TOKEN: cf.ODUSITE_TOKEN ?? import.meta.env.ODUSITE_TOKEN ?? '',
    ODUSITE_REVALIDATE_SECRET:
      cf.ODUSITE_REVALIDATE_SECRET ?? import.meta.env.ODUSITE_REVALIDATE_SECRET ?? '',
    PUBLIC_SITE_URL: cf.PUBLIC_SITE_URL ?? import.meta.env.PUBLIC_SITE_URL ?? '',
    TURNSTILE_SECRET_KEY: cf.TURNSTILE_SECRET_KEY ?? import.meta.env.TURNSTILE_SECRET_KEY,
    PUBLIC_TURNSTILE_SITE_KEY:
      cf.PUBLIC_TURNSTILE_SITE_KEY ?? import.meta.env.PUBLIC_TURNSTILE_SITE_KEY,
    ODUSITE_CACHE_TAGS: cf.ODUSITE_CACHE_TAGS,
  };
}
