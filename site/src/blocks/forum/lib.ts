// Block-local helpers for the forum block.

/** Rewrite Odoo /web/image URLs inside trusted API HTML to the /img proxy. */
export function rewriteHtml(html: string | null | undefined): string {
  if (!html) return '';
  return html.replaceAll('="/web/image', '="/img');
}

/** Human date from an ISO 8601 string. */
export function formatDate(iso: string | null | undefined, lang = 'en'): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(lang.replace('_', '-'), { dateStyle: 'medium' }).format(date);
}
