import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Marketing pages authored in the repo (ADR-006): src/content/pages/<slug>.mdx
const pages = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/pages' }),
  schema: z.object({
    title: z.string(),
    description: z.string().default(''),
    ogImage: z.string().optional(),
  }),
});

export const collections = { pages };
