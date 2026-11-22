import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  LANDING_KEY,
  attributionFromPage,
  captureLanding,
  hasCampaign,
  readLanding,
} from './landing';

const SITE = 'https://cinematiccelebration.in';
const T0 = new Date('2026-11-01T10:00:00Z');
const days = (n: number) => new Date(T0.getTime() + n * 24 * 60 * 60 * 1000);

function stored() {
  const raw = window.localStorage.getItem(LANDING_KEY);
  return raw ? JSON.parse(raw) : null;
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('captureLanding', () => {
  it('keeps homepage UTM attribution when the visitor moves on to /book', () => {
    captureLanding(`${SITE}/?utm_source=facebook&utm_medium=paid&utm_campaign=diwali`, '', T0);
    const later = captureLanding(`${SITE}/book?location=hulimavu`, `${SITE}/`, days(1));

    expect(later.utm_campaign).toBe('diwali');
    expect(later.landing_path).toBe('/');
    expect(stored().utm_source).toBe('facebook');
  });

  it('keeps stored attribution on a plain revisit within 30 days', () => {
    captureLanding(`${SITE}/?gclid=abc123`, 'https://www.google.com/', T0);
    const revisit = captureLanding(`${SITE}/locations`, '', days(20));
    expect(revisit.gclid).toBe('abc123');
    expect(revisit.referrer).toBe('https://www.google.com/');
  });

  it('replaces stored attribution when a new campaign arrives', () => {
    captureLanding(`${SITE}/?utm_source=google&utm_medium=cpc`, '', T0);
    const next = captureLanding(`${SITE}/?fbclid=IwAR9`, '', days(2));
    expect(next.fbclid).toBe('IwAR9');
    expect(next.utm_source).toBeUndefined();
    expect(stored().fbclid).toBe('IwAR9');
  });

  it('treats attribution older than 30 days as empty', () => {
    captureLanding(`${SITE}/?utm_source=instagram`, '', T0);
    const after = captureLanding(`${SITE}/contact`, '', days(31));
    expect(after.utm_source).toBeUndefined();
    expect(after.landing_path).toBe('/contact');
    expect(stored().landing_path).toBe('/contact');
  });

  it('stores a referrer-only visit when the store is empty', () => {
    const first = captureLanding(`${SITE}/`, 'https://l.instagram.com/?u=x', T0);
    expect(first.referrer).toBe('https://l.instagram.com/');
    expect(hasCampaign(first)).toBe(false);
    expect(stored().referrer).toBe('https://l.instagram.com/');
  });
});

describe('attributionFromPage', () => {
  it('strips query strings from the landing path and referrer', () => {
    const a = attributionFromPage(
      `${SITE}/book?location=hulimavu&utm_source=google`,
      'https://www.google.com/search?q=private+theatre',
      T0,
    );
    expect(a.landing_path).toBe('/book');
    expect(a.referrer).toBe('https://www.google.com/search');
  });

  it('ignores our own site as a referrer', () => {
    const a = attributionFromPage(`${SITE}/book`, `${SITE}/locations`, T0);
    expect(a.referrer).toBeUndefined();
  });

  it('never picks up personal data from the URL', () => {
    const a = attributionFromPage(
      `${SITE}/book?phone=9876543210&name=Asha&email=a%40example.com&utm_source=meta`,
      '',
      T0,
    );
    const text = JSON.stringify(a);
    expect(text).not.toContain('9876543210');
    expect(text).not.toContain('Asha');
    expect(text).not.toContain('example.com');
    expect(a.utm_source).toBe('meta');
  });

  it('cuts over-long values to the API limits', () => {
    const a = attributionFromPage(`${SITE}/?utm_campaign=${'x'.repeat(300)}`, '', T0);
    expect(a.utm_campaign).toHaveLength(200);
  });
});

describe('storage unavailable', () => {
  it('still works with the current page attribution only', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denied');
    });

    const a = captureLanding(`${SITE}/?utm_source=google&utm_medium=cpc`, '', T0);
    expect(a.utm_source).toBe('google');

    const current = readLanding(T0);
    expect(current?.landing_path).toBe(window.location.pathname);
  });

  it('readLanding returns the stored landing when present', () => {
    captureLanding(`${SITE}/?utm_campaign=diwali`, '', T0);
    expect(readLanding(days(1))?.utm_campaign).toBe('diwali');
  });

  it('ignores a corrupted store value', () => {
    window.localStorage.setItem(LANDING_KEY, '{not json');
    const a = captureLanding(`${SITE}/plans`, '', T0);
    expect(a.landing_path).toBe('/plans');
    expect(stored().landing_path).toBe('/plans');
  });
});
