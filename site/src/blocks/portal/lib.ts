// Shared helpers for the portal block: guarded API access, form-proxy
// utilities and display formatting. Server-side only.
import type { APIContext, AstroGlobal } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';

interface PortalApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  query?: Record<string, string | number | undefined>;
}

export function loginRedirect(astro: AstroGlobal): Response {
  return astro.redirect(`/login?next=${encodeURIComponent(astro.url.pathname)}`, 303);
}

/**
 * apiFetch wrapper for portal pages: 401 (token expired beyond refresh)
 * → redirect to /login, 404 → rewrite to the 404 page. Callers must check
 * `instanceof Response` and return it from the page frontmatter.
 */
export async function portalApi<T>(
  astro: AstroGlobal,
  path: string,
  options: PortalApiOptions = {},
): Promise<T | Response> {
  try {
    return await apiFetch<T>(astro, path, options);
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 401) return loginRedirect(astro);
      if (error.status === 404) return await astro.rewrite('/404');
    }
    throw error;
  }
}

// ---- form proxy helpers ----------------------------------------------

/** Only allow same-site relative redirect targets. */
export function safePath(raw: FormDataEntryValue | string | null, fallback: string): string {
  const value = typeof raw === 'string' ? raw : '';
  if (value.startsWith('/') && !value.startsWith('//') && !value.includes('\\')) return value;
  return fallback;
}

export function redirect303(context: APIContext, location: string): Response {
  return context.redirect(location, 303);
}

/** Normalize 422 `details.fields` into a flat field → message map. */
export function fieldErrors(details: Record<string, unknown>): Record<string, string> {
  const raw = details['fields'];
  const out: Record<string, string> = {};
  if (raw && typeof raw === 'object') {
    for (const [field, message] of Object.entries(raw as Record<string, unknown>)) {
      out[field] = Array.isArray(message) ? message.join(' ') : String(message);
    }
  }
  return out;
}

export interface FormErrorPayload {
  message: string;
  fields?: Record<string, string>;
  values?: Record<string, string>;
}

/** Serialize a form error (+ submitted values) into a query param. */
export function packFormError(
  error: OdusiteApiError,
  values?: Record<string, string>,
): string {
  const payload: FormErrorPayload = { message: error.message };
  const fields = fieldErrors(error.details);
  if (Object.keys(fields).length) payload.fields = fields;
  if (values) payload.values = values;
  return encodeURIComponent(JSON.stringify(payload));
}

export function unpackFormError(raw: string | null): FormErrorPayload | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(decodeURIComponent(raw)) as FormErrorPayload;
    if (typeof parsed.message !== 'string') return null;
    return parsed;
  } catch {
    return null;
  }
}

/** Collect string fields of a FormData into a plain record (skips files). */
export function formValues(form: FormData, keys: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const key of keys) {
    const value = form.get(key);
    if (typeof value === 'string') out[key] = value;
  }
  return out;
}

// ---- formatting --------------------------------------------------------

export function formatMoney(amount: number | undefined | null, currency: string | undefined): string {
  const value = amount ?? 0;
  if (!currency) return value.toFixed(2);
  try {
    return new Intl.NumberFormat('en', { style: 'currency', currency }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency}`;
  }
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium' }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

// ---- status → badge tone maps ------------------------------------------

type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info';

export function orderStateTone(state: string): Tone {
  switch (state) {
    case 'sale':
    case 'done':
      return 'success';
    case 'sent':
      return 'info';
    case 'cancel':
      return 'danger';
    default:
      return 'neutral';
  }
}

export function orderStateLabel(state: string): string {
  switch (state) {
    case 'sale':
      return 'Confirmed';
    case 'done':
      return 'Locked';
    case 'sent':
      return 'Quotation';
    case 'cancel':
      return 'Cancelled';
    case 'draft':
      return 'Draft';
    default:
      return state;
  }
}

export function invoiceTone(paymentState: string, isOverdue?: boolean): Tone {
  if (isOverdue) return 'danger';
  switch (paymentState) {
    case 'paid':
    case 'in_payment':
      return 'success';
    case 'partial':
      return 'warning';
    case 'reversed':
      return 'neutral';
    default:
      return 'info'; // not_paid / open
  }
}

export function invoiceStateLabel(paymentState: string, isOverdue?: boolean): string {
  if (isOverdue) return 'Overdue';
  switch (paymentState) {
    case 'paid':
      return 'Paid';
    case 'in_payment':
      return 'In payment';
    case 'partial':
      return 'Partial';
    case 'reversed':
      return 'Reversed';
    case 'not_paid':
      return 'Open';
    default:
      return paymentState;
  }
}

export function taskStateTone(state: string | null | undefined): Tone {
  if (!state) return 'neutral';
  const s = state.toLowerCase();
  if (s.includes('done') || s.includes('closed')) return 'success';
  if (s.includes('cancel')) return 'danger';
  return 'info';
}
