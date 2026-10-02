import { describe, expect, it } from 'vitest';
import { formatDate, formatRupees } from './formatters';

describe('formatRupees', () => {
  it('formats zero paise as ₹0.00', () => {
    expect(formatRupees(0)).toBe('₹0.00');
  });

  it('formats a plain amount (50000 paise = ₹500.00)', () => {
    expect(formatRupees(50000)).toBe('₹500.00');
  });

  it('formats large amounts with en-IN grouping', () => {
    // 1,23,45,678 paise = ₹1,23,456.78 (Indian lakh/crore grouping).
    expect(formatRupees(12345678)).toBe('₹1,23,456.78');
  });

  it('formats negative amounts (overpaid balance) with a minus sign', () => {
    const result = formatRupees(-50000);
    expect(result).toContain('500.00');
    expect(result).toContain('-');
  });
});

describe('formatDate', () => {
  it('formats a plain YYYY-MM-DD date in IST', () => {
    expect(formatDate('2025-12-25')).toBe('25 Dec 2025');
  });

  it('formats a full ISO timestamp in IST', () => {
    // 2025-12-24T20:00:00Z is 2025-12-25 01:30 IST → still 25 Dec.
    expect(formatDate('2025-12-24T20:00:00Z')).toBe('25 Dec 2025');
  });
});
