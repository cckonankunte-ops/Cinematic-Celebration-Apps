/**
 * Money helpers. The API exchanges integer paise; the UI converts to rupees
 * for display only. Never use floats for storage or transport.
 */

const PAISE_PER_RUPEE = 100;

const rupeeFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Convert integer paise to a rupee number (may be fractional). */
export function paiseToRupees(paise: number): number {
  return paise / PAISE_PER_RUPEE;
}

/** Convert a rupee number to integer paise, rounding to the nearest paisa. */
export function rupeesToPaise(rupees: number): number {
  return Math.round(rupees * PAISE_PER_RUPEE);
}

/**
 * Format integer paise as an INR currency string (en-IN).
 *
 * Handles zero, large values, and negative values (used to show an overpaid
 * balance, i.e. a negative amount due). `Intl.NumberFormat` renders the
 * leading minus sign for negative input.
 */
export function formatRupees(paise: number): string {
  return rupeeFormatter.format(paiseToRupees(paise));
}
