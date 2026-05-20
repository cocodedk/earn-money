// Diverging fallbacks (short UUID, raw slug, etc.) become a callable
// parameter so each consumer doesn't need its own lookup helper.
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
