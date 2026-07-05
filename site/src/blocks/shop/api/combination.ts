// POST /api/shop/combination — variant picker support. Proxies
// POST /odusite/v1/shop/products/<template_id>/combination and returns the
// combination info (price, availability, image, product_id).
import type { APIRoute } from 'astro';
import { apiFetch } from '@lib/api/client';
import { jsonBadRequest, jsonError, jsonResponse } from '../lib';
import type { CombinationInfo } from '../types';

export const prerender = false;

export const POST: APIRoute = async (context) => {
  let body: { product_template_id?: unknown; product_id?: unknown; combination?: unknown; quantity?: unknown };
  try {
    body = (await context.request.json()) as typeof body;
  } catch {
    return jsonBadRequest('Invalid JSON body.');
  }

  const templateId = Number(body.product_template_id ?? body.product_id);
  if (!Number.isInteger(templateId) || templateId <= 0) {
    return jsonBadRequest('product_template_id is required.');
  }
  const combination = Array.isArray(body.combination)
    ? body.combination.map(Number).filter((id) => Number.isInteger(id) && id > 0)
    : [];
  const quantity =
    typeof body.quantity === 'number' && Number.isFinite(body.quantity) && body.quantity > 0
      ? body.quantity
      : 1;

  try {
    const info = await apiFetch<CombinationInfo>(
      context,
      `/shop/products/${templateId}/combination`,
      { method: 'POST', body: { combination, quantity } },
    );
    return jsonResponse(info);
  } catch (error) {
    return jsonError(error);
  }
};
