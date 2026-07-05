// POST /api/shop/checkout/address — regular form POST from /checkout.
// Forwards the billing (and optional delivery) address to Odoo, then
// redirects 303 back to /checkout; validation errors (422) are carried
// back as query params rendered by the page.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { getCartBinding } from '@lib/auth/session';

export const prerender = false;

type AddressType = 'billing' | 'delivery';

export const POST: APIRoute = async (context) => {
  if (!getCartBinding(context)) {
    return context.redirect('/cart', 303);
  }

  let form: FormData;
  try {
    form = await context.request.formData();
  } catch {
    return context.redirect('/checkout?address_error=Invalid+form+submission', 303);
  }

  const field = (name: string): string => {
    const value = form.get(name);
    return typeof value === 'string' ? value.trim() : '';
  };
  const address = (prefix: AddressType) => ({
    name: field(`${prefix}_name`),
    email: field(`${prefix}_email`) || undefined,
    phone: field(`${prefix}_phone`),
    street: field(`${prefix}_street`),
    street2: field(`${prefix}_street2`),
    city: field(`${prefix}_city`),
    zip: field(`${prefix}_zip`),
    country_id: Number(field(`${prefix}_country_id`)) || undefined,
    state_id: Number(field(`${prefix}_state_id`)) || undefined,
  });

  const differentDelivery = form.get('different_delivery') === 'on';

  const fail = (type: AddressType, error: unknown): Response => {
    const params = new URLSearchParams();
    if (error instanceof OdusiteApiError && error.status === 422) {
      params.set('address_error', error.message);
      const fields = (error.details as { fields?: Record<string, unknown> }).fields;
      if (fields && typeof fields === 'object') {
        params.set(
          'address_error_fields',
          Object.keys(fields)
            .map((name) => `${type}_${name}`)
            .join(','),
        );
      }
    } else if (error instanceof OdusiteApiError) {
      params.set('address_error', error.message);
    } else {
      params.set('address_error', 'Could not save the address. Please try again.');
    }
    return context.redirect(`/checkout?${params.toString()}#address`, 303);
  };

  try {
    await apiFetch(context, '/shop/checkout/address', {
      method: 'POST',
      body: {
        address_type: 'billing',
        use_delivery_as_billing: !differentDelivery,
        ...address('billing'),
      },
    });
  } catch (error) {
    if (error instanceof OdusiteApiError) return fail('billing', error);
    throw error;
  }

  if (differentDelivery) {
    try {
      await apiFetch(context, '/shop/checkout/address', {
        method: 'POST',
        body: {
          address_type: 'delivery',
          use_delivery_as_billing: false,
          ...address('delivery'),
        },
      });
    } catch (error) {
      if (error instanceof OdusiteApiError) return fail('delivery', error);
      throw error;
    }
  }

  return context.redirect('/checkout', 303);
};
