// Build a lookup function from an iterable: O(n) build + O(1) reads.
// Used by list pages that join a foreign-key column (e.g. project name,
// stub title) against a cached query result. Diverging fallbacks
// (short UUIDs vs raw slugs) become a callable parameter, not a
// duplicated helper per call site.
export function byKey<T, V = string>(
  items: T[] | undefined,
  keyOf: (item: T) => string,
  valueOf: (item: T) => V,
  fallback: (key: string) => V,
): (key: string) => V {
  const map = new Map<string, V>();
  for (const item of items ?? []) map.set(keyOf(item), valueOf(item));
  return (key) => map.get(key) ?? fallback(key);
}
