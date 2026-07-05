// Locale routing helpers. The site is single-tree: block routes are injected
// once, without locale prefixes. A non-default language is expressed as a URL
// prefix (`/ru/...`) that the middleware strips before route matching while
// setting `locals.lang` (Odoo code, e.g. `ru_RU`) so the API returns localized
// data. The set of locales is data-driven from the Odoo site config
// (`languages`: {code, url_code, name}); a static fallback keeps routing alive
// when Odoo is unreachable.
import type { APIContext, AstroGlobal } from 'astro';
import { getSiteConfig, type SiteLanguage } from './api/base';

type Ctx = APIContext | AstroGlobal;

const FALLBACK: SiteLanguage[] = [{ code: 'en_US', url_code: 'en', name: 'English' }];

export interface LocaleInfo {
  languages: SiteLanguage[];
  defaultCode: string;
  defaultUrlCode: string;
  byUrlCode: Map<string, SiteLanguage>;
  byCode: Map<string, SiteLanguage>;
}

export async function getLocaleInfo(ctx: Ctx): Promise<LocaleInfo> {
  let languages = FALLBACK;
  let defaultCode = FALLBACK[0].code;
  try {
    const site = await getSiteConfig(ctx);
    if (site.languages?.length) {
      languages = site.languages;
      defaultCode = site.default_language || languages[0].code;
    }
  } catch {
    /* Odoo unreachable — fall back to the single default locale. */
  }
  const byUrlCode = new Map(languages.map((l) => [l.url_code, l]));
  const byCode = new Map(languages.map((l) => [l.code, l]));
  const def = byCode.get(defaultCode) ?? languages[0];
  return { languages, defaultCode: def.code, defaultUrlCode: def.url_code, byUrlCode, byCode };
}

/** Split a pathname into a leading locale prefix (any known url_code, incl. the
 * default) and the rest. The middleware rewrites non-default prefixes in place
 * and redirects the default prefix to the clean canonical path. */
export function splitLocale(
  pathname: string,
  info: LocaleInfo,
): { urlCode: string | null; rest: string } {
  const seg = pathname.split('/')[1] ?? '';
  if (info.byUrlCode.has(seg)) {
    return { urlCode: seg, rest: pathname.slice(seg.length + 1) || '/' };
  }
  return { urlCode: null, rest: pathname };
}

/** Build a path for a target locale (default locale ⇒ no prefix). */
export function localizePath(rest: string, urlCode: string, info: LocaleInfo): string {
  const clean = rest.startsWith('/') ? rest : `/${rest}`;
  if (urlCode === info.defaultUrlCode) return clean;
  return `/${urlCode}${clean === '/' ? '' : clean}`;
}
