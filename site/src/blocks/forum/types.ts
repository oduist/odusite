// Block-local types mirroring specs/modules/odusite_forum.md.

export interface ForumSummary {
  id: number;
  slug: string;
  name: string;
  description: string;
  mode: 'questions' | 'discussions';
  post_count: number;
}

export interface ForumRef {
  id: number;
  slug: string;
  name: string;
}

export interface ForumAuthor {
  id: number;
  name: string;
  avatar: string | null;
  karma: number;
}

export interface ForumTag {
  id: number;
  slug: string;
  name: string;
  post_count?: number;
}

export interface ForumPostListItem {
  id: number;
  slug: string;
  name: string;
  forum: ForumRef;
  tags: ForumTag[];
  votes: number;
  answer_count: number;
  has_validated_answer: boolean;
  views: number;
  author: ForumAuthor;
  last_activity: string;
}

export interface ForumComment {
  id: number;
  content_html: string;
  author: ForumAuthor;
  create_date: string;
}

export interface ForumAnswer {
  id: number;
  content_html: string;
  votes: number;
  is_correct: boolean;
  author: ForumAuthor;
  create_date: string;
  comments: ForumComment[];
}

/** Karma-derived capabilities of the JWT user (present only with a JWT). */
export interface ForumUserContext {
  vote: -1 | 0 | 1;
  is_favourite: boolean;
  can_answer: boolean;
  can_comment: boolean;
  can_upvote: boolean;
  can_downvote: boolean;
  can_accept: boolean;
  can_edit: boolean;
}

export interface ForumSeo {
  title: string | null;
  description: string | null;
  keywords: string | null;
  og_image: string | null;
}

export interface ForumPostDetail extends ForumPostListItem {
  content_html: string;
  answers: ForumAnswer[];
  comments: ForumComment[];
  user_context?: ForumUserContext | null;
  seo?: ForumSeo;
}

export interface ForumBadge {
  name: string;
  level: 'gold' | 'silver' | 'bronze';
  count: number;
}

export interface ForumUserProfile {
  id: number;
  name: string;
  avatar: string | null;
  karma: number;
  badges: ForumBadge[];
  joined: string;
  post_count: number;
  answer_count: number;
}

export type ForumFilter = 'all' | 'unanswered' | 'solved';
export type ForumOrder = 'relevance' | 'newest' | 'votes' | 'activity';
