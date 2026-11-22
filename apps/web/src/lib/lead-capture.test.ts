import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { publicApi } from './api';
import { captureLanding } from './landing';
import { LEAD_TOKEN_KEY, getLeadToken, sendStep1Lead } from './lead-capture';

const DETAILS = {
  locationId: 1,
  phone: '+91 98765 43210',
  name: '  Priya ',
  preferredDate: '2026-12-01',
  planId: 3,
  startTime: '11:00:00',
  durationMinutes: 120,
  guests: 4,
};

beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('sendStep1Lead', () => {
  it('posts the Step 1 details with attribution and keeps the token', async () => {
    captureLanding('https://cinematiccelebration.in/?utm_source=google&gclid=g1', '', new Date());
    const spy = vi.spyOn(publicApi, 'createLead').mockResolvedValue({ lead_token: 'tok-1' });

    await sendStep1Lead(DETAILS);

    const body = spy.mock.calls[0][0];
    expect(body).toMatchObject({
      location_id: 1,
      phone: '9876543210',
      name: 'Priya',
      preferred_date: '2026-12-01',
      plan_id: 3,
      start_time: '11:00:00',
      duration_minutes: 120,
      guests: 4,
    });
    expect(body.lead_token).toBeUndefined();
    expect(body.attribution?.gclid).toBe('g1');
    expect(getLeadToken()).toBe('tok-1');
    expect(window.sessionStorage.getItem(LEAD_TOKEN_KEY)).toBe('tok-1');
  });

  it('reuses the token on the next Next tap', async () => {
    const spy = vi
      .spyOn(publicApi, 'createLead')
      .mockResolvedValueOnce({ lead_token: 'tok-1' })
      .mockResolvedValueOnce({ lead_token: 'tok-1' });

    await sendStep1Lead(DETAILS);
    await sendStep1Lead({ ...DETAILS, guests: 6 });

    expect(spy.mock.calls[1][0].lead_token).toBe('tok-1');
    expect(spy.mock.calls[1][0].guests).toBe(6);
  });

  it('never rejects when the request fails, and keeps no token', async () => {
    vi.spyOn(publicApi, 'createLead').mockRejectedValue(new Error('offline'));
    await expect(sendStep1Lead(DETAILS)).resolves.toBeUndefined();
    expect(getLeadToken()).toBeNull();
  });

  it('sends nothing for an invalid phone', async () => {
    const spy = vi.spyOn(publicApi, 'createLead');
    await sendStep1Lead({ ...DETAILS, phone: '12345' });
    expect(spy).not.toHaveBeenCalled();
  });

  it('works when session storage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    vi.spyOn(publicApi, 'createLead').mockResolvedValue({ lead_token: 'tok-1' });
    await expect(sendStep1Lead(DETAILS)).resolves.toBeUndefined();
    expect(getLeadToken()).toBeNull();
  });
});
