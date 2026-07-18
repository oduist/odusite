// Local types for the "jobs" block, mirroring
// specs/modules/odusite_hr_recruitment.md.

export interface JobLocation {
  city: string | null;
  country: string | null;
}

/** A related record the API returns as `{id, name}` (department, contract type). */
export interface JobRef {
  id: number;
  name: string;
}

export interface JobListItem {
  id: number;
  slug: string;
  name: string;
  department: JobRef | null;
  location: JobLocation | null;
  employment_type: JobRef | null;
  is_remote: boolean;
  published_date: string | null;
}

export interface JobSeo {
  title?: string | null;
  description?: string | null;
}

export interface JobDetail extends JobListItem {
  /** website_description + job_details, HTML from Odoo. */
  description_html: string | null;
  seo?: JobSeo | null;
}
