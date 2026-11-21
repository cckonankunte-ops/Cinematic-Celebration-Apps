import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ENQUIRY_CODE_ALPHABET,
  ENQUIRY_CODE_KEY,
  generateEnquiryCode,
  getOrCreateEnquiryCode,
  isEnquiryCode,
} from './enquiry-code';

const T0 = new Date('2026-11-01T10:00:00Z');
const days = (n: number) => new Date(T0.getTime() + n * 24 * 60 * 60 * 1000);

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('generateEnquiryCode', () => {
  it('makes a 6-character code from the unambiguous alphabet', () => {
    for (let i = 0; i < 50; i++) {
      const code = generateEnquiryCode();
      expect(code).toMatch(/^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$/);
      expect(isEnquiryCode(code)).toBe(true);
    }
    expect(ENQUIRY_CODE_ALPHABET).not.toMatch(/[01ILO]/);
  });

  it('skips biased bytes (rejection sampling)', () => {
    // 248+ would bias the modulo; they must be skipped, not mapped.
    const bytes = [255, 250, 0, 1, 2, 3, 4, 5];
    const random = (out: Uint8Array) => {
      out.fill(0);
      out.set(bytes.slice(0, out.length));
      return out;
    };
    expect(generateEnquiryCode(random)).toBe('ABCDEF');
  });
});

describe('getOrCreateEnquiryCode', () => {
  it('reuses the stored code for 30 days', () => {
    const first = getOrCreateEnquiryCode(T0);
    expect(getOrCreateEnquiryCode(days(1))).toBe(first);
    expect(getOrCreateEnquiryCode(days(29))).toBe(first);
  });

  it('creates a new code after 30 days', () => {
    window.localStorage.setItem(
      ENQUIRY_CODE_KEY,
      JSON.stringify({ code: 'ABC234', created_at: T0.toISOString() }),
    );
    const next = getOrCreateEnquiryCode(days(31), () => new Uint8Array([7, 7, 7, 7, 7, 7]));
    expect(next).toBe('HHHHHH');
    expect(JSON.parse(window.localStorage.getItem(ENQUIRY_CODE_KEY) ?? '{}').code).toBe(
      'HHHHHH',
    );
  });

  it('replaces an invalid stored value', () => {
    window.localStorage.setItem(ENQUIRY_CODE_KEY, JSON.stringify({ code: 'bad!', created_at: 'x' }));
    expect(isEnquiryCode(getOrCreateEnquiryCode(T0))).toBe(true);
  });

  it('still returns a valid code when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    expect(isEnquiryCode(getOrCreateEnquiryCode(T0))).toBe(true);
  });
});
