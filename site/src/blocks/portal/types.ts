// Local response types for the portal block. They mirror the module specs
// (specs/modules/odusite_portal.md, odusite_sale.md, odusite_account.md,
// odusite_project.md) — fields the spec leaves open are typed optional.

// ---- odusite_portal ---------------------------------------------------

export interface MePartner {
  id: number;
  name: string;
  street?: string | null;
  street2?: string | null;
  city?: string | null;
  zip?: string | null;
  state_id?: number | null;
  country_id?: number | null;
  country?: string | null;
  vat?: string | null;
  company_name?: string | null;
}

export interface MeProfile {
  id: number;
  name: string;
  email: string;
  phone?: string | null;
  lang: string;
  partner: MePartner;
}

// Item as returned inside the /me/addresses {billing, delivery} groups.
export interface PortalAddressItem {
  id: number;
  name?: string | null;
  street?: string | null;
  street2?: string | null;
  city?: string | null;
  zip?: string | null;
  state?: string | null;
  country?: { id: number; code: string; name: string } | null;
  phone?: string | null;
  email?: string | null;
}

export interface PortalAddressBook {
  billing: PortalAddressItem[];
  delivery: PortalAddressItem[];
}

// Flattened, UI-facing address (one row per unique partner).
export interface PortalAddress {
  id: number;
  address_type: 'billing' | 'delivery';
  name?: string | null;
  street?: string | null;
  street2?: string | null;
  city?: string | null;
  zip?: string | null;
  state_id?: number | null;
  state?: string | null;
  country_id?: number | null;
  country?: string | null;
  phone?: string | null;
  email?: string | null;
}

export type Counters = Record<string, number>;

export interface SessionInfo {
  id: number;
  user_agent?: string | null;
  ip?: string | null;
  last_used_at?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
}

// ---- odusite_base -----------------------------------------------------

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
  zip_required: boolean;
  state_required: boolean;
}

// ---- chatter ----------------------------------------------------------

export interface ChatterAttachment {
  id?: number;
  name: string;
  url?: string | null;
  mimetype?: string | null;
}

export interface ChatterMessage {
  id: number;
  body: string;
  date: string;
  author: { name: string; avatar?: string | null };
  attachments?: ChatterAttachment[];
}

// ---- odusite_sale (portal orders) ---------------------------------------

export interface OrderListItem {
  id: number;
  name: string;
  date_order: string;
  state: string;
  amount_total: number;
  currency: string;
  invoice_status?: string | null;
}

export interface OrderLine {
  id?: number;
  name: string;
  quantity: number;
  price_unit: number;
  price_subtotal: number;
  price_total?: number;
}

export interface OrderAmounts {
  untaxed?: number;
  tax?: number;
  delivery?: number;
  total?: number;
  currency?: string;
}

export interface AddressSummary {
  name?: string | null;
  street?: string | null;
  street2?: string | null;
  city?: string | null;
  zip?: string | null;
  state?: string | null;
  country?: string | null;
}

export interface OrderDetail extends OrderListItem {
  lines: OrderLine[];
  amounts?: OrderAmounts;
  can_accept?: boolean;
  can_decline?: boolean;
  requires_payment?: boolean;
  amount_due?: number;
  delivery_address?: AddressSummary | null;
  expected_date?: string | null;
  invoices?: { id: number; name: string }[];
  pdf_url?: string | null;
  /** Present when the backend exposes the document token to its owner. */
  access_token?: string | null;
}

// ---- odusite_account (portal invoices) ----------------------------------

export interface InvoiceListItem {
  id: number;
  name: string;
  invoice_date: string | null;
  invoice_date_due: string | null;
  amount_total: number;
  amount_residual: number;
  currency: string;
  payment_state: string;
  is_overdue?: boolean;
}

export interface InvoiceLine {
  name: string;
  quantity: number;
  price_unit: number;
  price_subtotal: number;
  taxes?: string[];
}

export interface InvoiceDetail extends InvoiceListItem {
  lines: InvoiceLine[];
  amount_untaxed?: number;
  amount_tax?: number;
  requires_payment?: boolean;
  pdf_url?: string | null;
  access_token?: string | null;
}

// ---- odusite_project (portal projects & tasks) ---------------------------

export interface ProjectListItem {
  id: number;
  name: string;
  task_count: number;
  open_task_count: number;
}

export interface TaskListItem {
  id: number;
  name: string;
  project?: { id: number; name: string } | null;
  stage?: string | null;
  state?: string | null;
  deadline?: string | null;
  assignees?: string[];
  priority?: string | null;
}

export interface TaskAttachment {
  id: number;
  name: string;
  url: string;
  mimetype?: string | null;
}

export interface TaskDetail extends TaskListItem {
  description_html?: string | null;
  attachments?: TaskAttachment[];
  subtasks?: { id: number; name: string }[];
  timesheets?: {
    total_hours: number;
    lines: { date: string; name: string; hours: number }[];
  } | null;
}

// ---- auth ----------------------------------------------------------------

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: {
    id: number;
    name: string;
    email: string;
    partner_id: number;
    lang: string;
    is_portal: boolean;
  };
}
