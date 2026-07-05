// Block-local helpers for the events block.

/**
 * Rewrite Odoo image URLs (/web/image/...) inside an HTML string to the /img
 * proxy. The API contract says HTML arrives already rewritten
 * (specs/02-api-conventions.md); this is a cheap, idempotent safety net.
 */
export function rewriteImageUrls(html: string): string {
  return html.replace(/\/web\/image\//g, '/img/');
}

/** Validate an IANA timezone, falling back to UTC. */
export function safeTimezone(timezone: string | null | undefined): string {
  if (!timezone) return 'UTC';
  try {
    new Intl.DateTimeFormat('en', { timeZone: timezone });
    return timezone;
  } catch {
    return 'UTC';
  }
}

/** Day/month parts of a date in the event's timezone (for date blocks). */
export function eventDateParts(
  iso: string,
  timezone?: string | null,
): { day: string; month: string } {
  const date = new Date(iso);
  const tz = safeTimezone(timezone);
  const part = (options: Intl.DateTimeFormatOptions) =>
    new Intl.DateTimeFormat('en', { ...options, timeZone: tz }).format(date);
  return { day: part({ day: '2-digit' }), month: part({ month: 'short' }) };
}

/** Date range rendered in the event's timezone, timezone label appended. */
export function formatEventRange(
  begin: string,
  end: string,
  timezone?: string | null,
): string {
  const tz = safeTimezone(timezone);
  const start = new Date(begin);
  const stop = new Date(end);
  const format = new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: tz,
  });
  let range: string;
  try {
    range = format.formatRange(start, stop);
  } catch {
    range = `${format.format(start)} – ${format.format(stop)}`;
  }
  return `${range} (${tz})`;
}

/** Ticket price for display. */
export function formatMoney(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat('en', { style: 'currency', currency }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

/** Google Calendar basic date format (UTC): YYYYMMDDTHHMMSSZ. */
export function gcalDate(iso: string): string {
  return new Date(iso).toISOString().replace(/[-:]|\.\d{3}/g, '');
}
