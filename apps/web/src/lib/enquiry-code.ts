/**
 * WhatsApp enquiry code (lead-crm R18.2): a short code generated in the
 * browser, kept for 30 days and reused for later WhatsApp taps, so staff can
 * match a chat to the visitor's landing attribution. It carries no personal data.
 */

/** No 0/O or 1/I/L, to avoid misreading over chat (matches the API pattern). */
export const ENQUIRY_CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
export const ENQUIRY_CODE_LENGTH = 6;
export const ENQUIRY_CODE_KEY = 'cc.enquiryCode.v1';
export const ENQUIRY_CODE_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

const CODE_PATTERN = new RegExp(`^[${ENQUIRY_CODE_ALPHABET}]{${ENQUIRY_CODE_LENGTH}}$`);

interface StoredCode {
  code: string;
  created_at: string;
}

type RandomFill = (bytes: Uint8Array) => Uint8Array;

const defaultRandom: RandomFill = (bytes) => crypto.getRandomValues(bytes);

/** A fresh code. Rejection sampling keeps every character equally likely. */
export function generateEnquiryCode(random: RandomFill = defaultRandom): string {
  const n = ENQUIRY_CODE_ALPHABET.length;
  const limit = 256 - (256 % n);
  let code = '';
  while (code.length < ENQUIRY_CODE_LENGTH) {
    for (const byte of random(new Uint8Array(16))) {
      if (byte < limit && code.length < ENQUIRY_CODE_LENGTH) {
        code += ENQUIRY_CODE_ALPHABET[byte % n];
      }
    }
  }
  return code;
}

export function isEnquiryCode(value: string): boolean {
  return CODE_PATTERN.test(value);
}

function safeStorage(): Storage | null {
  try {
    const storage = window.localStorage;
    storage.getItem(ENQUIRY_CODE_KEY);
    return storage;
  } catch {
    return null;
  }
}

/**
 * The visitor's code: the stored one when under 30 days old, else a new one
 * (stored when possible). Without storage a new code is returned each call.
 */
export function getOrCreateEnquiryCode(
  now: Date = new Date(),
  random: RandomFill = defaultRandom,
): string {
  const storage = safeStorage();
  if (storage) {
    try {
      const raw = storage.getItem(ENQUIRY_CODE_KEY);
      if (raw) {
        const stored = JSON.parse(raw) as Partial<StoredCode>;
        const created = Date.parse(stored.created_at ?? '');
        if (
          typeof stored.code === 'string' &&
          isEnquiryCode(stored.code) &&
          !Number.isNaN(created) &&
          now.getTime() - created <= ENQUIRY_CODE_MAX_AGE_MS
        ) {
          return stored.code;
        }
      }
    } catch {
      // Unreadable value: fall through and replace it.
    }
  }
  const code = generateEnquiryCode(random);
  if (storage) {
    try {
      const value: StoredCode = { code, created_at: now.toISOString() };
      storage.setItem(ENQUIRY_CODE_KEY, JSON.stringify(value));
    } catch {
      // Quota or privacy mode: the code still works for this tap.
    }
  }
  return code;
}
