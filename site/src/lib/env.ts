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
  ELEVENLABS_API_KEY?: string;
  ELEVENLABS_AGENT_ID?: string;
  // Optional Cloudflare Access service token, sent to Odoo when its Tunnel
  // hostname (or public origin) is locked down behind Access. See
  // docs/admin/topologies.md.
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;
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
    ELEVENLABS_API_KEY: cf.ELEVENLABS_API_KEY ?? import.meta.env.ELEVENLABS_API_KEY,
    ELEVENLABS_AGENT_ID: cf.ELEVENLABS_AGENT_ID ?? import.meta.env.ELEVENLABS_AGENT_ID,
    CF_ACCESS_CLIENT_ID: cf.CF_ACCESS_CLIENT_ID ?? import.meta.env.CF_ACCESS_CLIENT_ID,
    CF_ACCESS_CLIENT_SECRET:
      cf.CF_ACCESS_CLIENT_SECRET ?? import.meta.env.CF_ACCESS_CLIENT_SECRET,
    ODUSITE_CACHE_TAGS: cf.ODUSITE_CACHE_TAGS,
  };
}

/**
 * Cloudflare Access service-token headers for reaching Odoo through a
 * locked-down Tunnel hostname (or public origin) behind Access. Server-side
 * only — never returned to the browser. Empty object when not configured, so
 * spreading it is a no-op in the default (open origin) setup.
 */
export function odooAccessHeaders(env: OdusiteEnv): Record<string, string> {
  if (env.CF_ACCESS_CLIENT_ID && env.CF_ACCESS_CLIENT_SECRET) {
    return {
      'CF-Access-Client-Id': env.CF_ACCESS_CLIENT_ID,
      'CF-Access-Client-Secret': env.CF_ACCESS_CLIENT_SECRET,
    };
  }
  return {};
}
