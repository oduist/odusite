// Local types for the "jobs" block, mirroring
// specs/modules/odusite_hr_recruitment.md.

export interface JobLocation {
  city: string | null;
  country: string | null;
}

export interface JobListItem {
  id: number;
  slug: string;
  name: string;
  department: string | null;
  location: JobLocation | null;
  employment_type: string | null;
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
