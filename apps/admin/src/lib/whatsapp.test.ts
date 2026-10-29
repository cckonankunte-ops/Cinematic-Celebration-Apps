import { describe, expect, it } from 'vitest';

import {
  buildWhatsappMessage,
  buildWhatsappUrl,
  waPhoneDigits,
  type BookingLike,
} from './whatsapp';

const booking: BookingLike = {
  booking_name: 'vinutha',
  booking_reference: 'OCTOBER4GOA1M',
  plan_title: 'Lavender Dream Theatre',
  combos: ['Combo2'],
  occasion_name: 'Birthday',
  booking_date: '2026-10-28',
  special_person_name: 'tarun',
  cakes: ['Strawberry'],
  name_on_cake: 'Happy B',
  cake_weight_half_kg: 1,
  slot_description: '6:30 PM - 7:30 PM',
  phone: '9876543210',
  map_url: 'https://maps.app.goo.gl/yfpJdW4z1t6mpW7w6',
};

function decodedText(url: string): string {
  const q = url.indexOf('?text=');
  expect(q).toBeGreaterThan(-1);
  return decodeURIComponent(url.slice(q + '?text='.length));
}

describe('buildWhatsappMessage', () => {
  it('renders the legacy confirmation format with bold fields', () => {
    const msg = buildWhatsappMessage(booking);
    expect(msg).toContain(`Your Booking is confirmed${'\u{1F973}'}`);
    expect(msg).toContain('Booking name: *vinutha*');
    expect(msg).toContain('Booking Id: *OCTOBER4GOA1M*');
    expect(msg).toContain('Space: *Lavender Dream Theatre + Combo2 Package*');
    expect(msg).toContain('Occasion: *Birthday*');
    expect(msg).toContain('Date: *28 Oct 2026*');
    expect(msg).toContain('Special person name: *tarun*');
    expect(msg).toContain('Cake details: *Strawberry | Happy B 1/2 KG*');
    expect(msg).toContain('Slot: *6:30 PM - 7:30 PM*');
    expect(msg).toContain(
      'Location: https://maps.app.goo.gl/yfpJdW4z1t6mpW7w6',
    );
    expect(msg).toContain(
      '*Note: Party Poppers (Blasters) and Spray not allowed from outside.*',
    );
    expect(msg).toContain(
      'Refund Policy: https://cinematiccelebration.in/refund-policy',
    );
    expect(msg).toContain('Cinematic Celebration Team');
  });

  it('renders whole-kg cake weights without the "/2" form', () => {
    const msg = buildWhatsappMessage({ ...booking, cake_weight_half_kg: 2 });
    expect(msg).toContain('Cake details: *Strawberry | Happy B 1 KG*');
  });

  it('falls back to the special person name when name on cake is blank', () => {
    const msg = buildWhatsappMessage({
      ...booking,
      name_on_cake: null,
      special_person_name: 'tarun',
    });
    expect(msg).toContain('Cake details: *Strawberry | tarun 1/2 KG*');
  });

  it('uses only the cake name when neither name on cake nor person is set', () => {
    const msg = buildWhatsappMessage({
      ...booking,
      name_on_cake: '  ',
      special_person_name: null,
    });
    expect(msg).toContain('Cake details: *Strawberry | 1/2 KG*');
  });

  it('shows "No Cake" when the booking has no cake', () => {
    const msg = buildWhatsappMessage({ ...booking, cakes: [] });
    expect(msg).toContain('Cake details: *No Cake*');
  });

  it('treats the catalog "No" cake row as no cake (case-insensitive)', () => {
    expect(buildWhatsappMessage({ ...booking, cakes: ['No'] })).toContain(
      'Cake details: *No Cake*',
    );
    expect(buildWhatsappMessage({ ...booking, cakes: ['NO'] })).toContain(
      'Cake details: *No Cake*',
    );
  });

  it('trims values so stray spaces do not break WhatsApp bold', () => {
    const msg = buildWhatsappMessage({
      ...booking,
      special_person_name: 'Somalisa singha ',
      booking_name: '  vinutha ',
    });
    // No space between the asterisk and the text (WhatsApp would not bold it).
    expect(msg).toContain('Special person name: *Somalisa singha*');
    expect(msg).toContain('Booking name: *vinutha*');
    expect(msg).not.toContain('*Somalisa singha *');
  });

  it('omits optional lines when absent', () => {
    const minimal: BookingLike = {
      booking_name: 'Ravi',
      booking_reference: 'CC-ECY-1',
      plan_title: 'Basic',
      booking_date: '2026-01-01',
      slot_description: '6 PM - 9 PM',
    };
    const msg = buildWhatsappMessage(minimal);
    expect(msg).not.toContain('Occasion:');
    expect(msg).not.toContain('Special person name:');
    expect(msg).not.toContain('Cake details:');
    expect(msg).not.toContain('Location:');
    // Space line with no combos is just the plan + " Package".
    expect(msg).toContain('Space: *Basic Package*');
  });
});

describe('waPhoneDigits', () => {
  it('prefixes 91 to a bare 10-digit number', () => {
    expect(waPhoneDigits('9876543210')).toBe('919876543210');
  });
  it('drops a leading national 0', () => {
    expect(waPhoneDigits('09876543210')).toBe('919876543210');
  });
  it('keeps an already-prefixed number', () => {
    expect(waPhoneDigits('+91 98765 43210')).toBe('919876543210');
  });
  it('returns empty for missing phone', () => {
    expect(waPhoneDigits(null)).toBe('');
    expect(waPhoneDigits(undefined)).toBe('');
  });
});

describe('buildWhatsappUrl', () => {
  it('targets the customer number when present', () => {
    expect(buildWhatsappUrl(booking)).toMatch(
      /^https:\/\/wa\.me\/919876543210\?text=/,
    );
  });

  it('falls back to no number when phone is absent', () => {
    const { phone, ...rest } = booking;
    void phone;
    expect(buildWhatsappUrl(rest)).toMatch(/^https:\/\/wa\.me\/\?text=/);
  });

  it('URL-encodes spaces and special characters', () => {
    const url = buildWhatsappUrl(booking);
    expect(url).not.toContain(' ');
    expect(decodedText(url)).toContain('vinutha');
  });
});
