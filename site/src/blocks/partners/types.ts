// Local types for the "partners" block, mirroring
// specs/modules/odusite_partner.md.

export type PartnerKind = 'customers' | 'resellers';

export interface PartnerTag {
  id: number;
  name: string;
  class: string | null;
}

export interface PartnerListItem {
  id: number;
  slug: string;
  name: string;
  logo: string | null;
  short_description: string | null;
  city: string | null;
  country: string | null;
  grade?: string | null;
  tags?: PartnerTag[];
}

export interface PartnerReference {
  id: number;
  slug: string;
  name: string;
}

export interface PartnerSeo {
  title?: string | null;
  description?: string | null;
}

export interface PartnerDetail extends PartnerListItem {
  /** website_description, HTML from Odoo. */
  description_html: string | null;
  website: string | null;
  industry: string | null;
  /** Implemented references — present when website_crm_partner_assign is installed. */
  references?: PartnerReference[];
  seo?: PartnerSeo | null;
}
