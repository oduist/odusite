# odusite_slides

Depends: `odusite_base`, `odusite_portal`, `website_slides`. eLearning.
Phase 1: catalog, course page, join public courses, content viewing, progress.
Paid courses (website_sale_slides), certifications, reviews UI — phase 2.

## Endpoints

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/courses` | GET | Paginated published `slide.channel` (upstream `is_visible` semantics: members-only/connected channels are hidden from anonymous listings, visible to their audience). Filters: `?tag=&search=`. Item: `{id, slug, name, description_short, cover, channel_type, total_time, slide_count, members_count, rating_avg, tags[{id, name, group}], enroll(public\|invite\|payment), is_member (JWT)}`. |
| `/odusite/v1/courses/<id_or_slug>` | GET | Detail: + `description_html`, curriculum grouped by category: `[{category, slides: [{id, slug, name, type(video\|document\|article\|quiz\|infographic), duration, is_preview, is_locked, completed (JWT)}]}]`, completion % (JWT), prerequisites. |
| `/odusite/v1/courses/<id>/join` | POST | JWT. Public-enroll courses only → membership (`slide.channel.partner`). invite/payment → 403/409. |
| `/odusite/v1/courses/<id>/slides/<slide_id>` | GET | Content (member or is_preview or public course): `{name, type, html_content?, video: {provider(youtube\|vimeo\|drive), embed_url}?, binary_url? (streamed attachment endpoint), resources[{name, url}], likes, dislikes, user_vote (JWT)}`. |
| `/odusite/v1/courses/<id>/slides/<slide_id>/complete` | POST | JWT member → mark completed, returns updated completion. |
| `/odusite/v1/courses/<id>/slides/<slide_id>/quiz` | GET/POST | GET: questions+answers (without correctness). POST `{answers: {question_id: answer_id}}` → result + karma rewards (stock quiz submit logic). |

## Webhooks / sitemap

Watched: `slide.channel`, `slide.slide` (publish, name, content).
Tags: `courses`, `courses:<channel_id>`. Sitemap: course pages (public ones).

## Site block `courses`

`/courses` (cards, tags), `/courses/[course]` (hero, curriculum with lock
states, join CTA), `/courses/[course]/[slide]` (content viewer: video embed /
article / document, prev-next nav, completion toggle, quiz player).
