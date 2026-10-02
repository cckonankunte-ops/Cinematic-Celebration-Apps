import { describe, expect, it } from 'vitest';

import {
  formatRupees,
  paiseToRupees,
  rupeesToPaise,
} from './money';

describe('formatRupees', () => {
  it('formats zero as ₹0.00', () => {
    expect(formatRupees(0)).toBe('₹0.00');
  });

  it('formats a large value with en-IN grouping', () => {
    // 12,34,567.89 rupees = 123456789 paise.
    expect(formatRupees(123456789)).toBe('₹12,34,567.89');
  });

  it('formats a negative/overpaid value with a leading minus', () => {
    const formatted = formatRupees(-50000);
    expect(formatted).toContain('-');
    expect(formatted).toContain('500.00');
  });

  it('formats a typical advance amount', () => {
    expect(formatRupees(50000)).toBe('₹500.00');
  });
});

describe('paise <-> rupees round trips', () => {
  it('round-trips whole-rupee values', () => {
    for (const paise of [0, 100, 50000, 123456700]) {
      expect(rupeesToPaise(paiseToRupees(paise))).toBe(paise);
    }
  });

  it('round-trips fractional-rupee paise values', () => {
    for (const paise of [1, 99, 12345, 123456789]) {
      expect(rupeesToPaise(paiseToRupees(paise))).toBe(paise);
    }
  });

  it('round-trips negative (overpaid) values', () => {
    expect(rupeesToPaise(paiseToRupees(-12345))).toBe(-12345);
  });

  it('converts rupees to paise with rounding', () => {
    expect(rupeesToPaise(500)).toBe(50000);
    expect(rupeesToPaise(123.45)).toBe(12345);
  });
});
