import { describe, expect, it } from 'vitest';
import { isValidIndianMobile, normaliseIndianMobile, telHref } from './phone';

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

describe('telHref', () => {
  it('prefixes a bare 10-digit number with +91', () => {
    expect(telHref('9876543210')).toBe('tel:+919876543210');
  });

  it('strips formatting characters', () => {
    expect(telHref('+91 98765 43210')).toBe('tel:+919876543210');
  });

  it('drops a leading 0 trunk prefix and re-applies +91', () => {
    expect(telHref('09876543210')).toBe('tel:+919876543210');
  });

  it('drops an explicit 91 country code and keeps a single +91', () => {
    expect(telHref('919876543210')).toBe('tel:+919876543210');
  });

  it('returns null when there are no digits', () => {
    expect(telHref('')).toBeNull();
    expect(telHref(null)).toBeNull();
    expect(telHref(undefined)).toBeNull();
  });

  it('returns null for a number that is not a 10-digit mobile', () => {
    expect(telHref('12345')).toBeNull();
  });
});

describe('normaliseIndianMobile (mirrors the server rule)', () => {
  it.each([
    ['9876543210', '9876543210'],
    ['+91 98765 43210', '9876543210'],
    ['098765 43210', '9876543210'],
    ['91-98765-43210', '9876543210'],
    ['  9876543210 ', '9876543210'],
  ])('normalises %s', (raw, expected) => {
    expect(normaliseIndianMobile(raw)).toBe(expected);
  });

  it.each(['12345', '1234567890', '', 'abcd'])('rejects %s', (raw) => {
    expect(normaliseIndianMobile(raw)).toBeNull();
  });

  it('handles null and undefined', () => {
    expect(normaliseIndianMobile(null)).toBeNull();
    expect(normaliseIndianMobile(undefined)).toBeNull();
  });
});
