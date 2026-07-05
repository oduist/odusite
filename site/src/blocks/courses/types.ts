// Block-local types mirroring specs/modules/odusite_slides.md.

export interface CourseTag {
  id: number;
  name: string;
  group: string | null;
}

export type CourseEnroll = 'public' | 'invite' | 'payment';

export type SlideType = 'video' | 'document' | 'article' | 'quiz' | 'infographic';

export interface CourseListItem {
  id: number;
  slug: string;
  name: string;
  description_short: string;
  cover: string | null;
  channel_type: string;
  /** Float hours (Odoo-native `total_time`). */
  total_time: number;
  slide_count: number;
  members_count: number;
  rating_avg: number;
  tags: CourseTag[];
  enroll: CourseEnroll;
  /** Present with a JWT. */
  is_member?: boolean;
}

export interface CurriculumSlide {
  id: number;
  slug: string;
  name: string;
  type: SlideType;
  /** Float hours (Odoo-native `completion_time`). */
  duration: number;
  is_preview: boolean;
  is_locked: boolean;
  /** Present with a JWT. */
  completed?: boolean;
}

export interface CurriculumCategory {
  category: string | null;
  slides: CurriculumSlide[];
}

export interface CourseRef {
  id: number;
  slug: string;
  name: string;
}

export interface CourseSeo {
  title: string | null;
  description: string | null;
  keywords: string | null;
  og_image: string | null;
}

export interface CourseDetail extends CourseListItem {
  description_html: string;
  curriculum: CurriculumCategory[];
  /** Completion percentage 0..100 (JWT members only). */
  completion?: number;
  prerequisites?: CourseRef[];
  seo?: CourseSeo;
}

export interface SlideVideo {
  provider: 'youtube' | 'vimeo' | 'drive';
  embed_url: string;
}

export interface SlideResource {
  name: string;
  url: string;
}

export interface SlideContent {
  name: string;
  type: SlideType;
  html_content?: string | null;
  video?: SlideVideo | null;
  binary_url?: string | null;
  resources: SlideResource[];
  likes: number;
  dislikes: number;
  /** Present with a JWT. */
  user_vote?: -1 | 0 | 1;
}

export interface QuizAnswerOption {
  id: number;
  text: string;
}

export interface QuizQuestion {
  id: number;
  question: string;
  answers: QuizAnswerOption[];
}
