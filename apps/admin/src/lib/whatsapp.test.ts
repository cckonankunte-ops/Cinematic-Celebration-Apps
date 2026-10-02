import { describe, expect, it } from 'vitest';

import { buildWhatsappUrl, type BookingLike } from './whatsapp';

const booking: BookingLike = {
  booking_name: 'Priya S',
  booking_reference: 'CC-HUL-20251225-A1B2',
  plan_title: 'Starlight Package',
  occasion_name: 'Birthday',
  booking_date: '2025-12-25',
  slot_description: '9 AM - 12 PM',
  cake_name: 'Chocolate Truffle',
  location_url: 'https://maps.example.com/hulimavu',
};

function decodedText(url: string): string {
  const prefix = 'https://wa.me/?text=';
  expect(url.startsWith(prefix)).toBe(true);
  return decodeURIComponent(url.slice(prefix.length));
}

describe('buildWhatsappUrl', () => {
  it('returns a wa.me URL', () => {
    expect(buildWhatsappUrl(booking)).toMatch(/^https:\/\/wa\.me\/\?text=/);
  });

  it('encodes all booking fields in the message', () => {
    const text = decodedText(buildWhatsappUrl(booking));
    expect(text).toContain('Priya S');
    expect(text).toContain('CC-HUL-20251225-A1B2');
    expect(text).toContain('Starlight Package');
    expect(text).toContain('Birthday');
    expect(text).toContain('9 AM - 12 PM');
    expect(text).toContain('Chocolate Truffle');
    expect(text).toContain('https://maps.example.com/hulimavu');
    // Date is rendered in IST display format.
    expect(text).toContain('Dec 2025');
  });

  it('URL-encodes spaces and special characters', () => {
    const url = buildWhatsappUrl(booking);
    // Raw spaces must not appear in the encoded query string.
    expect(url).not.toContain(' ');
    expect(url).toContain('%20');
  });

  it('omits optional fields when absent', () => {
    const minimal: BookingLike = {
      booking_name: 'Ravi',
      booking_reference: 'CC-ECY-20250101-ZZZZ',
      plan_title: 'Basic',
      booking_date: '2025-01-01',
      slot_description: '6 PM - 9 PM',
    };
    const text = decodedText(buildWhatsappUrl(minimal));
    expect(text).not.toContain('Occasion:');
    expect(text).not.toContain('Cake:');
    expect(text).not.toContain('Location:');
  });
});
