// POST /api/shop/cart/add — add a product to the cart, creating the cart
// (and the od_cart cookie binding) on first use. Returns the updated cart
// summary plus `count` for the header badge.
import type { APIRoute } from 'astro';
import { apiFetch } from '@lib/api/client';
import { getCartBinding, setCartBinding } from '@lib/auth/session';
import { cartLineCount, jsonBadRequest, jsonError, jsonResponse } from '../lib';
import type { CartMutationResult } from '../types';

export const prerender = false;

interface AddPayload {
  product_template_id?: unknown;
  product_id?: unknown;
  combination?: unknown;
  quantity?: unknown;
  no_variant_attribute_value_ids?: unknown;
  custom_values?: unknown;
}

export const POST: APIRoute = async (context) => {
  let body: AddPayload;
  try {
    body = (await context.request.json()) as AddPayload;
  } catch {
    return jsonBadRequest('Invalid JSON body.');
  }

  const templateId = Number(body.product_template_id);
  if (!Number.isInteger(templateId) || templateId <= 0) {
    return jsonBadRequest('product_template_id is required.');
  }
  const quantity =
    typeof body.quantity === 'number' && Number.isFinite(body.quantity) && body.quantity > 0
      ? body.quantity
      : 1;
  const productId = Number(body.product_id);
  const combination = Array.isArray(body.combination)
    ? body.combination.map(Number).filter((id) => Number.isInteger(id) && id > 0)
    : undefined;

  try {
    // First add ever: create the draft sale.order and bind it to the cookie.
    if (!getCartBinding(context)) {
      const created = await apiFetch<{ id: number; token: string }>(context, '/shop/cart', {
        method: 'POST',
        cart: false,
      });
      setCartBinding(context, created.id, created.token);
    }

    const data = await apiFetch<CartMutationResult>(context, '/shop/cart/lines', {
      method: 'POST',
      body: {
        product_template_id: templateId,
        product_id: Number.isInteger(productId) && productId > 0 ? productId : undefined,
        combination,
        quantity,
        no_variant_attribute_value_ids: Array.isArray(body.no_variant_attribute_value_ids)
          ? body.no_variant_attribute_value_ids
          : undefined,
        custom_values: body.custom_values,
      },
    });

    return jsonResponse({ ...data, count: cartLineCount(data) });
  } catch (error) {
    return jsonError(error);
  }
};
