import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { captureLanding } from './landing';
import {
  buildWhatsappLink,
  registerEnquiryCode,
  whatsappMessage,
  whatsappNumber,
} from './whatsapp';

const BRANCH = {
  id: 2,
  name: 'Hulimavu',
  phone: '080 4123 4567',
  whatsapp_phone: '9000000001',
};

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('whatsappNumber', () => {
  it('prefers the branch WhatsApp number', () => {
    expect(whatsappNumber(BRANCH)).toBe('919000000001');
  });

  it('falls back to the branch phone', () => {
    expect(whatsappNumber({ ...BRANCH, whatsapp_phone: null, phone: '+91 98765 43210' })).toBe(
      '919876543210',
    );
  });

  it('returns null without a usable number', () => {
    expect(whatsappNumber({ ...BRANCH, whatsapp_phone: null, phone: null })).toBeNull();
    expect(whatsappNumber({ ...BRANCH, whatsapp_phone: '', phone: '123' })).toBeNull();
  });
});

describe('buildWhatsappLink', () => {
  it('puts the enquiry code in the pre-filled message', () => {
    const link = buildWhatsappLink(BRANCH, 'W4K7XQ');
    expect(link).not.toBeNull();
    const url = new URL(link as string);
    expect(url.origin + url.pathname).toBe('https://wa.me/919000000001');
    const text = url.searchParams.get('text') ?? '';
    expect(text).toContain('Hi Cinematic Celebration (Hulimavu)!');
    expect(text.endsWith('\nEnquiry code: W4K7XQ')).toBe(true);
  });

  it('still builds a link without a code', () => {
    expect(whatsappMessage('Ecity', null)).not.toContain('Enquiry code');
    expect(buildWhatsappLink(BRANCH, null)).toContain('wa.me/919000000001');
  });
});

describe('registerEnquiryCode', () => {
  it('sends code, branch and attribution with keepalive, and no personal data', () => {
    captureLanding(
      'https://cinematiccelebration.in/?utm_source=facebook&utm_medium=paid',
      '',
      new Date(),
    );
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });

    registerEnquiryCode('W4K7XQ', BRANCH.id, fetchMock as unknown as typeof fetch);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/v1\/public\/enquiry-codes$/);
    expect(init.method).toBe('POST');
    expect(init.keepalive).toBe(true);
    const body = JSON.parse(String(init.body));
    expect(Object.keys(body).sort()).toEqual(['attribution', 'code', 'location_id']);
    expect(body.code).toBe('W4K7XQ');
    expect(body.location_id).toBe(2);
    expect(body.attribution.utm_source).toBe('facebook');
    const raw = String(init.body);
    expect(raw).not.toContain('9000000001');
    expect(raw).not.toContain('Hulimavu');
  });

  it('never throws or waits when the request fails (WhatsApp still opens)', async () => {
    const rejecting = vi.fn().mockRejectedValue(new Error('offline'));
    expect(() =>
      registerEnquiryCode('W4K7XQ', 2, rejecting as unknown as typeof fetch),
    ).not.toThrow();

    const throwing = vi.fn(() => {
      throw new Error('no fetch');
    });
    expect(() =>
      registerEnquiryCode('W4K7XQ', 2, throwing as unknown as typeof fetch),
    ).not.toThrow();

    const hanging = vi.fn(() => new Promise<Response>(() => undefined));
    expect(registerEnquiryCode('W4K7XQ', 2, hanging as unknown as typeof fetch)).toBeUndefined();

    // Let the rejected promise settle; nothing should surface as unhandled.
    await Promise.resolve();
  });
});
