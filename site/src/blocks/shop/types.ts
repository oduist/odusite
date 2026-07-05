// Shop block — local response types mirroring specs/modules/odusite_sale.md
// (and specs/modules/odusite_base.md for /countries).

// ---------------------------------------------------------------------------
// Catalog

export interface ShopCategory {
  id: number;
  slug: string;
  name: string;
  parent_id: number | null;
  children: ShopCategory[];
  product_count: number;
  cover?: string | null;
}

export interface ProductListItem {
  id: number;
  slug: string;
  name: string;
  list_price: number;
  price: number;
  has_discounted_price: boolean;
  currency: string;
  rating?: number | null;
  image: string | null;
  second_image?: string | null;
  tags?: string[];
  category_ids?: number[];
}

/** `meta.facets` on /shop/products: attributes + value counts. */
export interface FacetValue {
  id: number;
  name: string;
  count?: number;
}

export interface Facet {
  id: number;
  name: string;
  values: FacetValue[];
}

export interface Seo {
  title?: string | null;
  description?: string | null;
  keywords?: string | null;
  og_image?: string | null;
}

export interface ProductImage {
  id: number;
  name?: string | null;
  image: string;
}

export interface AttributeValue {
  id: number;
  name: string;
  html_color?: string | null;
  price_extra?: number;
}

export interface AttributeLine {
  attribute: { id: number; name: string };
  /** Odoo display types: radio | pills | select | color | multi. */
  display_type: string;
  values: AttributeValue[];
}

/** Combination info (`_get_combination_info`) — single pricing source. */
export interface CombinationInfo {
  product_id: number | null;
  price: number;
  list_price: number;
  has_discounted_price: boolean;
  currency: string;
  display_name?: string;
  image?: string | null;
  is_combination_possible?: boolean;
  [key: string]: unknown;
}

export interface ProductDocument {
  id: number;
  name: string;
  url: string;
}

export interface ProductDetail {
  id: number;
  slug: string;
  name: string;
  description_html?: string | null;
  images: ProductImage[];
  attribute_lines: AttributeLine[];
  combination: CombinationInfo;
  alternatives?: ProductListItem[];
  accessories?: ProductListItem[];
  documents?: ProductDocument[];
  seo?: Seo | null;
  jsonld?: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Cart (stateless — ADR-007)

export interface CartProductRef {
  id: number;
  slug: string;
  name: string;
  image: string | null;
}

export interface CartLine {
  id: number;
  product: CartProductRef | null;
  description?: string | null;
  quantity: number;
  price_unit: number;
  price_subtotal: number;
  price_total: number;
  /** Delivery / reward lines are flagged and rendered read-only. */
  is_delivery?: boolean;
  is_reward?: boolean;
}

export interface CartAmounts {
  untaxed: number;
  tax: number;
  delivery: number;
  total: number;
  currency: string;
}

export type TaxMode = 'included' | 'excluded';

export interface Cart {
  id?: number;
  lines: CartLine[];
  amounts: CartAmounts;
  tax_mode: TaxMode;
}

/** POST /shop/cart/lines response: updated cart summary + line_id, warnings. */
export interface CartMutationResult extends Cart {
  line_id?: number;
  warnings?: string[];
}

// ---------------------------------------------------------------------------
// Checkout

export interface CheckoutAddress {
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  street?: string | null;
  street2?: string | null;
  city?: string | null;
  zip?: string | null;
  country_id?: number | null;
  state_id?: number | null;
  [key: string]: unknown;
}

export interface DeliveryMethod {
  id: number;
  name: string;
  description?: string | null;
  price: number;
  currency: string;
  free_over?: number | null;
}

export interface CheckoutState {
  cart_ok: boolean;
  addresses: {
    billing: CheckoutAddress | null;
    delivery: CheckoutAddress | null;
  };
  needs_delivery: boolean;
  delivery_methods: DeliveryMethod[];
  selected_delivery_id: number | null;
  payment_ready: boolean;
  errors: string[];
}

// ---------------------------------------------------------------------------
// Countries (odusite_base /countries — address forms)

export interface CountryState {
  id: number;
  code: string;
  name: string;
}

export interface Country {
  id: number;
  code: string;
  name: string;
  states: CountryState[];
  zip_required?: boolean;
  state_required?: boolean;
}

// ---------------------------------------------------------------------------
// Payment / confirmation

export interface PaymentTransactionState {
  state: 'draft' | 'pending' | 'authorized' | 'done' | 'cancel' | 'error';
  state_message?: string | null;
  document_state?: string | null;
}

/** GET /shop/orders/<id>/confirmation — thank-you page summary. */
export interface OrderConfirmation {
  id: number;
  name: string;
  date_order?: string | null;
  email?: string | null;
  lines?: CartLine[];
  amounts?: CartAmounts;
  tax_mode?: TaxMode;
  [key: string]: unknown;
}
