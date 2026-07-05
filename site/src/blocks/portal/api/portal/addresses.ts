// POST /api/portal/addresses — form proxy for the address book:
// action=create → POST /me/addresses, update → PUT /me/addresses/<id>,
// archive → DELETE /me/addresses/<id>. Errors redirect back with a packed
// error payload (?err=) so the form re-renders with messages and values.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';
import { formValues, packFormError, redirect303, safePath } from '../../lib';

export const prerender = false;

const ADDRESS_FIELDS = ['name', 'email', 'phone', 'street', 'street2', 'city', 'zip', 'country_id', 'state_id'];

export const POST: APIRoute = async (context) => {
  if (!context.locals.user) return redirect303(context, '/login?next=%2Fportal%2Faddresses');

  const form = await context.request.formData().catch(() => null);
  if (!form) return redirect303(context, '/portal/addresses');

  const action = form.get('action');
  const id = form.get('id');
  const back = safePath(form.get('return'), '/portal/addresses');

  try {
    if (action === 'archive') {
      if (typeof id !== 'string' || !/^\d+$/.test(id)) return redirect303(context, '/portal/addresses');
      await apiFetch(context, `/me/addresses/${id}`, { method: 'DELETE' });
      return redirect303(context, '/portal/addresses?archived=1');
    }

    const values = formValues(form, ADDRESS_FIELDS);
    const addressType = form.get('address_type');
    const body: Record<string, unknown> = {
      ...values,
      address_type: addressType === 'delivery' ? 'delivery' : 'billing',
      country_id: values.country_id ? Number(values.country_id) : null,
      state_id: values.state_id ? Number(values.state_id) : null,
    };

    if (action === 'update') {
      if (typeof id !== 'string' || !/^\d+$/.test(id)) return redirect303(context, '/portal/addresses');
      await apiFetch(context, `/me/addresses/${id}`, { method: 'PUT', body });
    } else {
      await apiFetch(context, '/me/addresses', { method: 'POST', body });
    }
    return redirect303(context, '/portal/addresses?saved=1');
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      if (error.status === 401) return redirect303(context, '/login?next=%2Fportal%2Faddresses');
      const values = formValues(form, ADDRESS_FIELDS);
      const separator = back.includes('?') ? '&' : '?';
      return redirect303(context, `${back}${separator}err=${packFormError(error, values)}`);
    }
    throw error;
  }
};
