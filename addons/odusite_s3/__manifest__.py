{
    'name': 'Odusite S3',
    'summary': 'Offload the ir.attachment filestore to S3-compatible object '
               'storage (AWS S3, Cloudflare R2)',
    'description': """
Offloads Odoo binary attachments (product images, blog/event covers, generated
PDFs, uploads) to S3-compatible object storage while keeping backend web-asset
bundles and small thumbnails on the local filestore for a fast admin UI
(see specs/modules/odusite_s3.md, ADR-008, ADR-012). Production techniques
(deferred dedup-aware GC, threaded time-windowed migration, presigned direct
download) are borrowed from an internal reference module and adapted to Odoo 19.

- s3:// store_fname marker routing (local + S3 coexist per record)
- selective, overridable offload policy (assets / small images stay local)
- deferred, reference-counted garbage collection of removed objects
- background migration cron (threaded, start/stop, time window, keyset paging)
- presigned GET URLs + 302 direct download for /web/content and /web/image
- hybrid public delivery: direct R2/CDN original + /img proxy for resized variants
""",
    'category': 'Website',
    'version': '19.0.1.0.0',
    'author': 'Odusite',
    'license': 'LGPL-3',
    'depends': ['odusite_base'],
    'external_dependencies': {'python': ['boto3']},
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
}
