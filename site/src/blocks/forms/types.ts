// Local types for the "forms" block, mirroring specs/modules/odusite_crm.md.

export interface ContactMeta {
  page?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
}

/** Payload forwarded to POST /odusite/v1/forms/contact. */
export interface ContactPayload {
  name: string;
  email: string;
  phone?: string;
  company?: string;
  subject?: string;
  message: string;
  /** Honeypot passthrough — Odoo rejects submissions with a non-empty value. */
  website_hp?: string;
  meta?: ContactMeta;
}
