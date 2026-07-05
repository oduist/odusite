// Shop block — server-side helpers: typed Odoo calls (via apiFetch),
// catalog query parsing, money formatting, endpoint response helpers.
import type { APIContext, AstroGlobal } from 'astro';
import { apiFetch, OdusiteApiError, type ApiListResult } from '@lib/api/client';
import type {
  Cart,
  CartAmounts,
  CheckoutState,
  Country,
  OrderConfirmation,
  ProductDetail,
  ProductListItem,
  ShopCategory,
} from './types';

type Ctx = APIContext | AstroGlobal;

// ---------------------------------------------------------------------------
// Catalog queries

export const PAGE_SIZE = 24;

export const SORT_OPTIONS = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'price_asc', label: 'Price: low to high' },
  { value: 'price_desc', label: 'Price: high to low' },
  { value: 'name', label: 'Name' },
  { value: 'newest', label: 'Newest' },
] as const;

const SORT_KEYS: string[] = SORT_OPTIONS.map((option) => option.value);

export interface CatalogQuery {
  page?: number;
  search?: string;
  order?: string;
  category?: number;
  min_price?: number;
  max_price?: number;
  attribs?: string;
}

export function catalogQueryFromUrl(url: URL): CatalogQuery {
  const params = url.searchParams;
  const num = (value: string | null): number | undefined => {
    if (value === null || value === '') return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  };
  const page = num(params.get('page'));
  const order = params.get('order');
  return {
    page: page !== undefined && page >= 1 ? Math.floor(page) : undefined,
    search: params.get('search') || undefined,
    order: order && SORT_KEYS.includes(order) ? order : undefined,
    min_price: num(params.get('min_price')),
    max_price: num(params.get('max_price')),
    attribs: params.get('attribs') || undefined,
  };
}

/** Toggle one `<attr>-<value>` facet token in ?attribs=, resetting the page. */
export function toggleAttribUrl(url: URL, token: string): string {
  const current = (url.searchParams.get('attribs') ?? '').split(',').filter(Boolean);
  const next = current.includes(token)
    ? current.filter((t) => t !== token)
    : [...current, token];
  const target = new URL(url);
  if (next.length) target.searchParams.set('attribs', next.join(','));
  else target.searchParams.delete('attribs');
  target.searchParams.delete('page');
  return target.pathname + target.search;
}

/** Locate a category by slug (with `<name>-<id>` fallback); returns the trail
 * from the root for breadcrumbs. */
export function findCategory(
  tree: ShopCategory[],
  slug: string,
): { category: ShopCategory; trail: ShopCategory[] } | null {
  const idMatch = /-(\d+)$/.exec(slug);
  const id = idMatch ? Number(idMatch[1]) : null;
  for (const node of tree) {
    if (node.slug === slug || (id !== null && node.id === id)) {
      return { category: node, trail: [node] };
    }
    const inChild = findCategory(node.children ?? [], slug);
    if (inChild) return { category: inChild.category, trail: [node, ...inChild.trail] };
  }
  return null;
}

// ---------------------------------------------------------------------------
// Typed Odoo calls

export function fetchProducts(
  ctx: Ctx,
  query: CatalogQuery,
): Promise<ApiListResult<ProductListItem>> {
  return apiFetch(ctx, '/shop/products', {
    query: {
      page: query.page,
      limit: PAGE_SIZE,
      search: query.search,
      order: query.order,
      category: query.category,
      min_price: query.min_price,
      max_price: query.max_price,
      attribs: query.attribs,
    },
  });
}

export function fetchCategories(ctx: Ctx): Promise<ShopCategory[]> {
  return apiFetch(ctx, '/shop/categories');
}

export function fetchProduct(ctx: Ctx, idOrSlug: string): Promise<ProductDetail> {
  return apiFetch(ctx, `/shop/products/${encodeURIComponent(idOrSlug)}`);
}

export function fetchCart(ctx: Ctx): Promise<Cart> {
  return apiFetch(ctx, '/shop/cart');
}

export function fetchCheckout(ctx: Ctx): Promise<CheckoutState> {
  return apiFetch(ctx, '/shop/checkout');
}

export function fetchCountries(ctx: Ctx): Promise<Country[]> {
  return apiFetch(ctx, '/countries', { auth: false, cart: false });
}

export function fetchOrderConfirmation(
  ctx: Ctx,
  orderId: number,
  accessToken: string,
): Promise<OrderConfirmation> {
  return apiFetch(ctx, `/shop/orders/${orderId}/confirmation`, {
    query: { access_token: accessToken },
  });
}

export function setDeliveryMethod(ctx: Ctx, deliveryMethodId: number): Promise<CartAmounts> {
  return apiFetch(ctx, '/shop/checkout/delivery', {
    method: 'PUT',
    body: { delivery_method_id: deliveryMethodId },
  });
}

// ---------------------------------------------------------------------------
// Formatting

export function localeOf(lang: string | undefined | null): string {
  return (lang ?? 'en_US').replace('_', '-');
}

export function formatMoney(amount: number, currency: string, lang?: string | null): string {
  try {
    return new Intl.NumberFormat(localeOf(lang), { style: 'currency', currency }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

/** JSON serialized safely for inline <script> embedding. */
export function jsonScript(value: unknown): string {
  return JSON.stringify(value ?? null).replace(/</g, '\\u003c');
}

/** Cart badge count: sum of product line quantities (delivery/reward excluded). */
export function cartLineCount(cart: Pick<Cart, 'lines'> | null | undefined): number {
  if (!cart || !Array.isArray(cart.lines)) return 0;
  return cart.lines
    .filter((line) => !line.is_delivery && !line.is_reward)
    .reduce((sum, line) => sum + (Number(line.quantity) || 0), 0);
}

// ---------------------------------------------------------------------------
// Endpoint response helpers (same envelope as the payment endpoints)

export function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ data }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export function jsonBadRequest(message: string): Response {
  return new Response(
    JSON.stringify({ error: { code: 'bad_request', message } }),
    { status: 400, headers: { 'Content-Type': 'application/json' } },
  );
}

/** Map OdusiteApiError to a JSON error response; rethrow anything else. */
export function jsonError(error: unknown): Response {
  if (error instanceof OdusiteApiError) {
    return new Response(
      JSON.stringify({
        error: { code: error.code, message: error.message, details: error.details },
      }),
      { status: error.status, headers: { 'Content-Type': 'application/json' } },
    );
  }
  throw error;
}
