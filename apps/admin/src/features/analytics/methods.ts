/**
 * Payment-method helpers for analytics. Known methods come first in a fixed
 * order (cash, upi, card, other); any method added later is appended
 * alphabetically, so new categories appear automatically.
 */

import type { MethodAmounts } from './types';

const KNOWN_ORDER = ['cash', 'upi', 'card', 'other'];

export function orderedMethods(...sources: MethodAmounts[]): string[] {
  const seen = new Set<string>();
  for (const source of sources) {
    for (const method of Object.keys(source)) {
      seen.add(method);
    }
  }
  const known = KNOWN_ORDER.filter((m) => seen.has(m));
  const extra = [...seen].filter((m) => !KNOWN_ORDER.includes(m)).sort();
  return [...known, ...extra];
}

export function methodLabel(method: string): string {
  return method === 'upi' ? 'UPI' : method.charAt(0).toUpperCase() + method.slice(1);
}
