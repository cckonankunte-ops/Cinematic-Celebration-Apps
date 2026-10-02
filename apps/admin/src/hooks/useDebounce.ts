import { useEffect, useState } from 'react';

/**
 * Return a debounced copy of `value` that only updates after `delayMs` has
 * elapsed without further changes. Useful for search inputs on the booking
 * list so we don't fire a query on every keystroke.
 */
export function useDebounce<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
