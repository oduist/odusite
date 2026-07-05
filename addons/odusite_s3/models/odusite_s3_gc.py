from odoo import fields, models


class OdusiteS3Gc(models.Model):
    """Deferred-deletion queue for S3-backed attachment objects.

    Equivalent of the core filestore "checklist" directory, but stored in the
    database (there is no on-disk file to spool). Rows are inserted in a
    *separate* cursor on ``ir.attachment._file_delete`` — so the deletion intent
    survives a rollback of the current transaction (object stores are not
    transactional with PostgreSQL) — and consumed by the ``_gc_odusite_s3_store``
    autovacuum, which only removes an object when no ``ir.attachment`` still
    references the same ``store_fname`` (deduplication guard).
    """
    _name = 'odusite.s3.gc'
    _description = 'Odusite S3 GC Queue'

    store_fname = fields.Char('Stored Filename', required=True, index=True)

    _store_fname_uniq = models.Constraint(
        'unique(store_fname)',
        'A garbage-collection entry already exists for this stored filename.',
    )
