import { describe, expect, it } from 'vitest';
import { isValidIndianMobile } from './phone';

describe('isValidIndianMobile', () => {
  it('accepts a bare 10-digit mobile', () => {
    expect(isValidIndianMobile('9876543210')).toBe(true);
  });

  it('accepts a +91-prefixed number with spaces', () => {
    expect(isValidIndianMobile('+91 98765 43210')).toBe(true);
  });

  it('accepts a 0-prefixed number with a space', () => {
    expect(isValidIndianMobile('098765 43210')).toBe(true);
  });

  it('rejects a too-short number', () => {
    expect(isValidIndianMobile('12345')).toBe(false);
  });

  it('rejects a 10-digit number not starting with 6-9', () => {
    expect(isValidIndianMobile('1234567890')).toBe(false);
  });

  it('rejects an empty string', () => {
    expect(isValidIndianMobile('')).toBe(false);
  });

  it('rejects non-numeric input', () => {
    expect(isValidIndianMobile('abcd')).toBe(false);
  });
});
