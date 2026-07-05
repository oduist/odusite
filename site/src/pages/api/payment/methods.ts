// Same-origin proxy: payment methods for a payable document.
import type { APIRoute } from 'astro';
import { apiFetch, OdusiteApiError } from '@lib/api/client';

export const prerender = false;

export const GET: APIRoute = async (context) => {
  const url = new URL(context.request.url);
  try {
    const data = await apiFetch(context, '/payment/methods', {
      query: {
        document: url.searchParams.get('document') ?? undefined,
        access_token: url.searchParams.get('access_token') ?? undefined,
      },
    });
    return new Response(JSON.stringify({ data }), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    if (error instanceof OdusiteApiError) {
      return new Response(JSON.stringify({ error: { code: error.code, message: error.message } }), {
        status: error.status,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    throw error;
  }
};
