// POST /api/shop/cart/update — change a cart line quantity (quantity <= 0
// removes the line). Returns the refreshed cart contents.
import type { APIRoute } from 'astro';
import { apiFetch } from '@lib/api/client';
import { getCartBinding } from '@lib/auth/session';
import { cartLineCount, jsonBadRequest, jsonError, jsonResponse } from '../lib';
import type { Cart } from '../types';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  let body: { line_id?: unknown; quantity?: unknown };
  try {
    body = (await context.request.json()) as typeof body;
  } catch {
    return jsonBadRequest('Invalid JSON body.');
  }

  const lineId = Number(body.line_id);
  const quantity = Number(body.quantity);
  if (!Number.isInteger(lineId) || lineId <= 0 || !Number.isFinite(quantity)) {
    return jsonBadRequest('line_id and quantity are required.');
  }
  if (!getCartBinding(context)) {
    return jsonBadRequest('No active cart.');
  }

  try {
    if (quantity <= 0) {
      await apiFetch(context, `/shop/cart/lines/${lineId}`, { method: 'DELETE' });
    } else {
      await apiFetch(context, `/shop/cart/lines/${lineId}`, {
        method: 'PUT',
        body: { quantity },
      });
    }
    const cart = await apiFetch<Cart>(context, '/shop/cart');
    return jsonResponse({ ...cart, count: cartLineCount(cart) });
  } catch (error) {
    return jsonError(error);
  }
};
