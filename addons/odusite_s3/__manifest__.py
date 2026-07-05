{
    'name': 'Odusite S3',
    'summary': 'Offload the ir.attachment filestore to S3-compatible object '
               'storage (AWS S3, Cloudflare R2)',
    'description': """
Offloads Odoo binary attachments (product images, blog/event covers, generated
PDFs, uploads) to S3-compatible object storage while keeping backend web-asset
bundles on the local filestore for a fast admin UI (see specs/modules/odusite_s3.md,
ADR-008, ADR-012).

- ir.attachment _storage/_file_read/_file_write/_file_delete offload via boto3
- selective, overridable offload policy (assets stay local)
- presigned GET URLs for private documents
- hybrid public delivery: direct R2/CDN original + /img proxy for resized variants
- lazy migration of the existing filestore (server action + optional cron)
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Odusite',
    'license': 'LGPL-3',
    'depends': ['odusite_base'],
    'external_dependencies': {'python': ['boto3']},
    'data': [
        'security/ir.model.access.csv',
        'data/odusite_s3_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
}
