import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import config from 'virtual:odusite/config';
import { getEnv } from '@lib/env';
import { getSitemapEntries } from '@lib/api/base';

export const prerender = false;

export const GET: APIRoute = async (context) => {
  const env = getEnv(context);
  const origin = env.PUBLIC_SITE_URL || new URL(context.request.url).origin;

  const urls: { loc: string; lastmod?: string }[] = [{ loc: '/' }];
  for (const page of await getCollection('pages')) {
    urls.push({ loc: `/${page.id.replace(/\.mdx?$/, '')}` });
  }
  for (const item of config.nav) {
    urls.push({ loc: item.href });
  }
  try {
    for (const entry of await getSitemapEntries(context)) {
      urls.push({ loc: entry.url, lastmod: entry.lastmod ?? undefined });
    }
  } catch {
    // Odoo unreachable — ship the static part rather than failing.
  }

  const seen = new Set<string>();
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .filter((u) => (seen.has(u.loc) ? false : seen.add(u.loc)))
  .map(
    (u) =>
      `  <url><loc>${origin}${u.loc}</loc>${u.lastmod ? `<lastmod>${u.lastmod}</lastmod>` : ''}</url>`,
  )
  .join('\n')}
</urlset>`;

  return new Response(body, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'public, max-age=0, s-maxage=3600',
    },
  });
};
