{
    'name': 'Odusite Project',
    'summary': 'Portal projects & tasks API for the Odusite frontend',
    'description': """
Portal projects and tasks for the Odusite frontend
(see specs/modules/odusite_project.md):
- GET /odusite/v1/my/projects[/<id>]: portal-visible projects (+ task list)
- GET /odusite/v1/my/tasks[/<id>]: tasks across projects, detail with
  attachments (token-signed /web/content URLs), subtasks and timesheet
  summary (when hr_timesheet is installed)
- form whitelist for project.task (website suggestion form)
- portal counters 'projects'/'tasks' and chatter whitelist
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Oduist OÜ',
    'license': 'Other OSI approved licence',
    'depends': ['odusite_base', 'odusite_portal', 'project'],
    'installable': True,
}
