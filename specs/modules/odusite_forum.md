# odusite_forum

Depends: `odusite_base`, `odusite_portal`, `website_forum`
(brings `website_profile`, gamification).

## Endpoints

Read (public):

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/forum/forums` | GET | `[{id, slug, name, description, mode(questions\|discussions), post_count}]`. |
| `/odusite/v1/forum/posts` | GET | Paginated questions. Filters: `?forum=&tag=&filter=all\|unanswered\|solved&search=`. Order whitelist: `relevance` (default, relevancy), `newest`, `votes`, `activity`. Item: `{id, slug, name, forum, tags[], votes, answer_count, has_validated_answer, views, author: {id, name, avatar, karma}, last_activity}`. |
| `/odusite/v1/forum/posts/<id_or_slug>` | GET | Question detail: + `content_html`, answers `[{id, content_html, votes, is_correct, author, create_date, comments[]}]`, comments, `user_context` (with JWT): `{vote: -1\|0\|1, is_favourite, can_answer, can_comment, can_upvote, can_downvote, can_accept, can_edit}` (karma-derived `can_*`). |
| `/odusite/v1/forum/tags` | GET | `?forum=` → `[{id, slug, name, post_count}]`. |
| `/odusite/v1/forum/users/<id>` | GET | Public profile (website_profile): `{id, name, avatar, karma, badges[{name, level, count}], joined, post_count, answer_count}`. |

Actions (JWT; karma checks enforced by stock model methods, mapped to 403
`karma_required` with the needed karma in details):

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/forum/posts` | POST | `{forum_id, name, content, tags[]}` — ask. |
| `/odusite/v1/forum/posts/<id>/answers` | POST | `{content}` — answer. |
| `/odusite/v1/forum/posts/<id>` | PUT/DELETE | Edit / delete own (or karma-moderated). |
| `/odusite/v1/forum/posts/<id>/vote` | POST | `{vote: 1\|-1\|0}`. |
| `/odusite/v1/forum/posts/<id>/accept` | POST | Toggle accepted answer. |
| `/odusite/v1/forum/posts/<id>/comments` | POST | `{content}`. |
| `/odusite/v1/forum/posts/<id>/favourite` | POST | Toggle favourite. |

Moderation queues — backend only (not exposed).

## Webhooks / sitemap

Watched: `forum.post` (active state, content, votes → throttled), `forum.forum`.
Tags: `forum`, `forum:<id>`. Sitemap: question URLs.

## Site block `forum`

`/forum`, `/forum/[forum]` (question list + filters), `/forum/[forum]/[post]`
(Q&A thread, vote buttons, answer editor — markdown-lite → sanitized HTML),
`/forum/users/[id]` (profile). Read pages edge-cached; user context fetched
client-side.
