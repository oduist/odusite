# odusite_blog

Depends: `odusite_base`, `website_blog`.

## Data source

`blog.blog`, `blog.post`, `blog.tag` (+ `blog.tag.category`). Published filter:
`is_published` + `post_date <= now` + website domain.

## Endpoints

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/blog/blogs` | GET | `[{id, slug, name, subtitle, post_count}]`. |
| `/odusite/v1/blog/posts` | GET | Paginated. Filters: `?blog=<id\|slug>&tag=<id\|slug>&search=&date_from=&date_to=`. Item: `{id, slug, name, subtitle, teaser, cover, author: {name, avatar}, tags[{id, slug, name}], post_date, blog: {id, slug, name}}`. Order whitelist: `published_desc` (default), `name`, `visits`. |
| `/odusite/v1/blog/posts/<id_or_slug>` | GET | Detail: list fields + `content` (HTML), `seo`, `visits`, prev/next post refs, related by tags (4). Increments `visits` (write-through, non-blocking). |
| `/odusite/v1/blog/tags` | GET | `[{id, slug, name, category, post_count}]`. |
| `/odusite/v1/blog/posts/<id>/comments` | GET/POST | Via generic chatter endpoints (blog.post registered in chatter whitelist); anonymous commenting disabled in v1 — POST requires JWT. |

## Webhooks / sitemap

- Watched: `blog.post` (name, content, tags, publish state, post_date),
  `blog.tag`. Tags: `blog`, `blog:<post_id>`.
- Sitemap hook contributes `/blog/<post_slug>` URLs (single segment — matches the
  site's `/blog/[post]` route).

## Site block `blog`

Routes: `/blog` (grid + tag/blog filter + pagination), `/blog/[post]` (detail:
cover, content, author, tags, comments, related), Atom feed `/blog/feed.xml`
(from the list endpoint). Edge-cached with tags `blog`, `blog:<id>`.
