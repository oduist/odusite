// Data shapes for the blog block — mirror specs/modules/odusite_blog.md and
// the common field conventions in specs/02-api-conventions.md.

export interface BlogTag {
  id: number;
  slug: string;
  name: string;
}

/** Item of GET /blog/tags. */
export interface BlogTagSummary extends BlogTag {
  category: string | null;
  post_count: number;
}

export interface BlogAuthor {
  name: string;
  avatar: string | null;
}

export interface BlogRef {
  id: number;
  slug: string;
  name: string;
}

/** SEO block present on every detail entity (specs/02-api-conventions.md). */
export interface Seo {
  title: string | null;
  description: string | null;
  keywords: string | null;
  og_image: string | null;
}

/** Item of GET /blog/posts. */
export interface BlogPostListItem {
  id: number;
  slug: string;
  name: string;
  subtitle: string | null;
  teaser: string | null;
  cover: string | null;
  author: BlogAuthor;
  tags: BlogTag[];
  /** ISO 8601 UTC. */
  post_date: string;
  blog: BlogRef;
}

/** Prev/next post reference on the detail endpoint. */
export interface BlogPostNeighbor {
  id: number;
  slug: string;
  name: string;
}

/** GET /blog/posts/<id_or_slug>. */
export interface BlogPostDetail extends BlogPostListItem {
  /** Server-sanitized HTML. */
  content: string;
  seo: Seo;
  visits: number;
  prev: BlogPostNeighbor | null;
  next: BlogPostNeighbor | null;
  /** Related by tags (up to 4). */
  related: BlogPostListItem[];
}
