# odusite_project

Depends: `odusite_base`, `odusite_portal`, `project`. Portal projects & tasks.

## Endpoints (JWT; detail also via `?access_token=`)

| Route | Method | Description |
|---|---|---|
| `/odusite/v1/my/projects` | GET | Paginated portal-visible projects: `{id, name, task_count, open_task_count}`. |
| `/odusite/v1/my/projects/<id>` | GET | Project header + its task list (same filters as tasks endpoint). |
| `/odusite/v1/my/tasks` | GET | Paginated tasks across projects. Filters: `?project=<id>&state=open\|closed&search=`. Groupable client-side by `stage`. Item: `{id, name, project: {id, name}, stage, state, deadline, assignees[names], priority}`. |
| `/odusite/v1/my/tasks/<id>` | GET | Detail: + `description_html`, attachments `[{id, name, url, mimetype}]` (token-signed URLs), subtask refs, timesheet summary (if hr_timesheet installed: `{total_hours, lines[{date, name, hours}]}`). |

Task creation from the website (suggestion form) goes through
`odusite_crm`'s generic form endpoint with `project.task` registered
(fields: name, description, email — like website_project).

Chatter: `project.task`, `project.project` in the whitelist.
Counters: `projects`, `tasks`.

## Webhooks / sitemap

None (portal-only).

## Site part

Portal sections `/portal/projects`, `/portal/tasks[/id]` (stage chips,
deadline, description, attachments, chatter/comments).
