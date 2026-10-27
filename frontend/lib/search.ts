/**
 * The one search rule every list screen shares.
 *
 * A query is matched against whatever text a row already shows: a name, a code,
 * a reference, a status label. Matching is deliberately forgiving — lower-cased,
 * whitespace-trimmed, and split into tokens that must all appear somewhere in
 * the row — so "jane dean" finds "Jane M. Dean" and "annual 2026" finds an
 * annual-leave application filed in 2026. An empty query matches everything,
 * which is what lets a search box start out showing the whole list.
 *
 * Pure and network-free on purpose: the screens that filter a fully loaded list
 * import this directly, so the behaviour is the same everywhere and can be
 * tested without rendering a component.
 */
export function matchesSearch(
  query: string,
  values: ReadonlyArray<string | number | null | undefined>
): boolean {
  const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return true;

  const haystack = values
    .filter((value) => value !== null && value !== undefined)
    .join(" ")
    .toLowerCase();

  return tokens.every((token) => haystack.includes(token));
}
