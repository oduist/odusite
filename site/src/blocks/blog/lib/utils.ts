// Block-local helpers for the blog block.

/**
 * Rewrite Odoo image URLs (/web/image/...) inside an HTML string to the /img
 * proxy. The API contract says content HTML arrives already rewritten
 * (specs/02-api-conventions.md); this is a cheap, idempotent safety net.
 */
export function rewriteImageUrls(html: string): string {
  return html.replace(/\/web\/image\//g, '/img/');
}

/** Format an ISO 8601 date for display, e.g. "Jul 5, 2026". */
export function formatDate(iso: string, locale = 'en'): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}
