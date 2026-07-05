// Atom feed for the blog: latest 20 published posts from the list endpoint.
import type { APIRoute } from 'astro';
import { apiFetch, type ApiListResult } from '@lib/api/client';
import { getEnv } from '@lib/env';
import type { BlogPostListItem } from '../types';

export const prerender = false;

function esc(value: string): string {
  return value.replace(/[&<>"']/g, (char) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[char] as string,
  );
}

function iso(date: string): string {
  const parsed = new Date(date);
  return Number.isNaN(parsed.getTime()) ? new Date().toISOString() : parsed.toISOString();
}

export const GET: APIRoute = async (context) => {
  const { data: posts } = await apiFetch<ApiListResult<BlogPostListItem>>(context, '/blog/posts', {
    query: { limit: 20 },
    auth: false,
    cart: false,
  });

  const env = getEnv(context);
  const origin = env.PUBLIC_SITE_URL || new URL(context.request.url).origin;
  const feedUrl = `${origin}/blog/feed.xml`;
  const first = posts[0];
  const updated = first ? iso(first.post_date) : new Date().toISOString();

  const entries = posts
    .map((post) => {
      const link = `${origin}/blog/${post.slug}`;
      return [
        '  <entry>',
        `    <title>${esc(post.name)}</title>`,
        `    <id>${esc(link)}</id>`,
        `    <link rel="alternate" type="text/html" href="${esc(link)}"/>`,
        `    <published>${iso(post.post_date)}</published>`,
        `    <updated>${iso(post.post_date)}</updated>`,
        `    <author><name>${esc(post.author?.name || 'Unknown')}</name></author>`,
        post.teaser ? `    <summary>${esc(post.teaser)}</summary>` : '',
        ...post.tags.map((tag) => `    <category term="${esc(tag.slug)}" label="${esc(tag.name)}"/>`),
        '  </entry>',
      ]
        .filter(Boolean)
        .join('\n');
    })
    .join('\n');

  const xml = [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<feed xmlns="http://www.w3.org/2005/Atom">',
    '  <title>Blog</title>',
    `  <id>${esc(feedUrl)}</id>`,
    `  <link rel="self" type="application/atom+xml" href="${esc(feedUrl)}"/>`,
    `  <link rel="alternate" type="text/html" href="${esc(`${origin}/blog`)}"/>`,
    `  <updated>${updated}</updated>`,
    entries,
    '</feed>',
  ].join('\n');

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/atom+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=0, s-maxage=600',
      'X-Odusite-Tags': 'blog',
    },
  });
};
