// Block-local helpers for the courses block.
import type { CurriculumCategory, CurriculumSlide, SlideType } from './types';

/** Rewrite Odoo /web/image URLs inside trusted API HTML to the /img proxy. */
export function rewriteHtml(html: string | null | undefined): string {
  if (!html) return '';
  return html.replaceAll('="/web/image', '="/img');
}

/** slide.channel.description_short is an HTML field; flatten to plain text
 * for card and hero-subtitle slots. */
export function stripHtml(html: string | null | undefined): string {
  if (!html) return '';
  return html
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export const SLIDE_ICONS: Record<SlideType, string> = {
  video: '🎬',
  document: '📄',
  article: '📝',
  quiz: '❓',
  infographic: '🖼',
};

/** Duration is Odoo-native float hours → "2h 30m" / "45m". */
export function formatDuration(hours: number | null | undefined): string {
  if (!hours || hours <= 0) return '';
  const totalMinutes = Math.round(hours * 60);
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${String(m).padStart(2, '0')}m`;
}

/** Text stars for a 0..5 average, e.g. "★★★★☆". */
export function ratingStars(avg: number | null | undefined): string {
  const rounded = Math.min(5, Math.max(0, Math.round(avg ?? 0)));
  return '★'.repeat(rounded) + '☆'.repeat(5 - rounded);
}

/** Curriculum flattened in display order (prev/next navigation). */
export function flattenCurriculum(curriculum: CurriculumCategory[]): CurriculumSlide[] {
  return curriculum.flatMap((category) => category.slides);
}
