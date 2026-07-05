// Facet helpers for list pages: normalize `meta.facets` groups into a
// uniform {value, label, count} shape, tolerating both plain strings and
// {id|value|code, name|label, count} objects from the API.
//
// NOTE: deliberately duplicated in blocks/jobs/lib/facets.ts — blocks must
// not import from each other (block contract, specs/site/01-blocks.md), and
// the helper is small enough that a copy beats a cross-block dependency.

export interface FacetEntry {
  value: string;
  label: string;
  count: number | null;
}

type RawFacetEntry =
  | string
  | number
  | {
      value?: string | number;
      id?: string | number;
      code?: string | number;
      label?: string;
      name?: string;
      count?: number;
    };

function normalize(entry: RawFacetEntry): FacetEntry | null {
  if (typeof entry === 'string' || typeof entry === 'number') {
    return { value: String(entry), label: String(entry), count: null };
  }
  if (!entry || typeof entry !== 'object') return null;
  const value = entry.value ?? entry.id ?? entry.code ?? entry.name;
  if (value === undefined || value === null) return null;
  return {
    value: String(value),
    label: String(entry.label ?? entry.name ?? value),
    count: typeof entry.count === 'number' ? entry.count : null,
  };
}

/** Return the first facet group found under any of the candidate keys. */
export function facetEntries(facets: unknown, keys: string[]): FacetEntry[] {
  if (!facets || typeof facets !== 'object') return [];
  const groups = facets as Record<string, unknown>;
  for (const key of keys) {
    const raw = groups[key];
    if (Array.isArray(raw)) {
      return raw
        .map((entry) => normalize(entry as RawFacetEntry))
        .filter((entry): entry is FacetEntry => entry !== null);
    }
  }
  return [];
}
