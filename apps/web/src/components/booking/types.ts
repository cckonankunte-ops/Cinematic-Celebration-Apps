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
  specialDecorIds: number[];
  comboIds: number[];
  bookingName: string;
  email: string;
  phone: string;
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
    specialDecorIds: [],
    comboIds: [],
    bookingName: '',
    email: '',
    phone: '',
    people: 1,
    occasionId: null,
    specialPersonName: '',
    nameOnCake: '',
    message: '',
  };
}
