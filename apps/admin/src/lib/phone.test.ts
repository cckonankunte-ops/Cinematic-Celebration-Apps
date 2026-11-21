import { describe, expect, it } from 'vitest';

import { normaliseIndianMobile } from './phone';

describe('normaliseIndianMobile (mirrors the server rule)', () => {
  it.each([
    ['9876543210', '9876543210'],
    ['+91 98765 43210', '9876543210'],
    ['098765 43210', '9876543210'],
    ['91-98765-43210', '9876543210'],
    [' 98765-43210 ', '9876543210'],
  ])('normalises %s', (raw, expected) => {
    expect(normaliseIndianMobile(raw)).toBe(expected);
  });

  it.each(['', '12345', '1234567890', 'abcdefghij', '+1 202 555 0101'])('rejects %s', (raw) => {
    expect(normaliseIndianMobile(raw)).toBeNull();
  });

  it('handles null and undefined', () => {
    expect(normaliseIndianMobile(null)).toBeNull();
    expect(normaliseIndianMobile(undefined)).toBeNull();
  });
});
