// POST /api/shop/checkout/delivery — select a delivery method on the cart.
// Proxies PUT /odusite/v1/shop/checkout/delivery, returns recomputed amounts.
import type { APIRoute } from 'astro';
import { getCartBinding } from '@lib/auth/session';
import { jsonBadRequest, jsonError, jsonResponse, setDeliveryMethod } from '../lib';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  let body: { delivery_method_id?: unknown };
  try {
    body = (await context.request.json()) as typeof body;
  } catch {
    return jsonBadRequest('Invalid JSON body.');
  }

  const deliveryMethodId = Number(body.delivery_method_id);
  if (!Number.isInteger(deliveryMethodId) || deliveryMethodId <= 0) {
    return jsonBadRequest('delivery_method_id is required.');
  }
  if (!getCartBinding(context)) {
    return jsonBadRequest('No active cart.');
  }

  try {
    const amounts = await setDeliveryMethod(context, deliveryMethodId);
    return jsonResponse(amounts);
  } catch (error) {
    return jsonError(error);
  }
};
