/** Shared draft state for the multi-step booking wizard. */
import type {
  Cake,
  Combo,
  Occasion,
  Plan,
  SpecialDecor,
} from '../../lib/api';

export interface BookingDraft {
  plan: Plan | null;
  bookingDate: string;
  slotId: number | null;
  showCombos: boolean;
  cakeId: number | null;
  /** Cake weight in half-kg units (1 = 0.5kg). Defaults to 1. */
  cakeWeightHalfKg: number;
  /** Decor selections as `{ id, quantity }`; quantity is always >= 1. */
  specialDecor: Array<{ id: number; quantity: number }>;
  comboIds: number[];
  bookingName: string;
  /** Email is optional on the public contract. */
  email: string;
  /** Phone is required (valid Indian mobile). */
  phone: string;
  /** Free-text LED name (₹40 per letter, priced server-side). */
  ledName: string;
  /** Optional coupon code; the server validates and computes the discount. */
  couponCode: string;
  people: number;
  occasionId: number | null;
  specialPersonName: string;
  nameOnCake: string;
  message: string;
}

export interface Catalog {
  plans: Plan[];
  cakes: Cake[];
  specialDecor: SpecialDecor[];
  combos: Combo[];
  occasions: Occasion[];
}

export function emptyDraft(bookingDate: string): BookingDraft {
  return {
    plan: null,
    bookingDate,
    slotId: null,
    showCombos: true,
    cakeId: null,
    cakeWeightHalfKg: 1,
    specialDecor: [],
    comboIds: [],
    bookingName: '',
    email: '',
    phone: '',
    ledName: '',
    couponCode: '',
    people: 1,
    occasionId: null,
    specialPersonName: '',
    nameOnCake: '',
    message: '',
  };
}
