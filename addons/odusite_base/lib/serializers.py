"""Shared record → JSON serialization helpers (see specs/02-api-conventions.md)."""


def image_url(record, field, size=None):
    """Relative /web/image URL with a cache-busting `unique` checksum.

    `size` is an Odoo size string like '512x512' (empty height/width allowed).
    Returns None when the record has no value in `field`.
    """
    if not record:
        return None
    sudo_record = record.sudo()
    if not sudo_record[field]:
        return None
    return sudo_record.env['website'].sudo().image_url(sudo_record, field, size=size)


def seo(record):
    """SEO block from website.seo.metadata fields, with sane fallbacks."""
    sudo_record = record.sudo()
    og_image = None
    if sudo_record.website_meta_og_img:
        og_image = sudo_record.website_meta_og_img
    return {
        'title': sudo_record.website_meta_title or sudo_record.display_name,
        'description': sudo_record.website_meta_description or '',
        'keywords': sudo_record.website_meta_keywords or '',
        'og_image': og_image,
    }


def money(amount, currency):
    digits = currency.decimal_places if currency else 2
    return {
        'amount': round(amount or 0.0, digits),
        'currency': currency.name if currency else None,
    }


def datetime_utc(value):
    """Odoo datetimes are naive UTC — serialize as ISO 8601 with Z."""
    if not value:
        return None
    return value.replace(microsecond=0).isoformat() + 'Z'


def date_iso(value):
    return value.isoformat() if value else None


def html_field(record, field):
    """Html fields are already sanitized by Odoo; image URLs stay relative so
    the site can rewrite them to its /img proxy."""
    return record.sudo()[field] or ''


def slug(record):
    """Odoo-compatible slug '<name>-<id>' (Odoo 19: ir.http._slug)."""
    return record.env['ir.http']._slug(record)


def unslug(value):
    """Return (name, id) from a slug or a plain id string."""
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return None, int(value)
    from odoo.http import request
    return request.env['ir.http']._unslug(value)
